import json
import logging
from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from app.core.config import settings
from app.instructions import get_system_prompt
from app.core.database import get_async_db, get_session_factory
from app.client import client
from app.services.rag import retrieve_context
from app.instructions import RAG_PROMPT_TEMPLATE
from app.services.context_manager import trim_history
from app.services.tools.definitions import TOOLS
from app.services.tools.executor import execute_tool
from app.schemas.chats import ChatRequest
from app.models.chats import ChatMessage, ChatRole, ChatSession
from app.models.user import User
from app.dependencies.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/sessions",
    tags=["Chats"]
)


async def _get_session_or_404(session_id: str, db: AsyncSession) -> ChatSession:
    result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
    session = result.scalars().first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session


async def _update_session_title(gen_db: AsyncSession, session_id: str, title: str) -> None:
    stmt = select(ChatSession).where(ChatSession.id == session_id).with_for_update()
    session_to_update = (await gen_db.execute(stmt)).scalars().first()
    if session_to_update and session_to_update.title == "New Chat":
        session_to_update.title = title[:60]


# Creates new session
@router.post("/{user_id}/sessions", status_code=201)
async def create_session(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: User = Depends(get_current_user),
):
    if user_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your session")

    session = ChatSession(
        id=str(uuid.uuid4()),
        user_id=user_id,
        title="New Chat"
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


# Get all user sessions
@router.get("/{user_id}/sessions")
async def get_sessions(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: User = Depends(get_current_user),
):
    if user_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your session")

    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .order_by(ChatSession.created_at.desc())
    )
    return list(result.scalars().all())


# Delete a session
@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: User = Depends(get_current_user),
):
    session = await _get_session_or_404(session_id, db)

    if session.user_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your session")

    await db.execute(
        ChatMessage.__table__.delete().where(ChatMessage.session_id == session_id)
    )
    await db.delete(session)
    await db.commit()

    return {"message": "Session deleted successfully"}


# Get all messages from a session
@router.get("/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    session = await _get_session_or_404(session_id, db)

    if session.user_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your session")

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    return result.scalars().all()


# Send a message and stream AI response
@router.post("/{session_id}/messages")
async def send_message_stream(
    session_id: str,
    request: ChatRequest,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    session_factory: Annotated[async_sessionmaker, Depends(get_session_factory)],
    current_user: User = Depends(get_current_user),
):
    if not request.content or not request.content.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Message content cannot be empty")

    session = await _get_session_or_404(session_id, db)

    if session.user_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your session")

    # Intercept summary and quiz before RAG and LLM
    BLOCK_KEYWORDS = ["summarize", "summary", "overview", "key points", "summarise", "quiz"]
    if any(kw in request.content.lower() for kw in BLOCK_KEYWORDS):
        async def redirect_generator():
            msg = "Use the **Summary** and **Quiz** feature for this lesson to get a full structured summary and quiz respectively. I'm here to answer specific questions about the lesson content!"
            yield f"data: {json.dumps({'token': msg})}\n\n"
            yield f"data: {json.dumps({'status': 'done'})}\n\n"
        return StreamingResponse(redirect_generator(), media_type="text/event-stream")

    try:
        if request.enhance_prompt:
            enhance_response = await client.chat.completions.create(
                model=settings.MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a prompt enhancer. Rewrite the student's questions to be clearer, more specific, and more detailed. Return ONLY the rewritten question, nothing else."
                    },
                    {
                        "role": "user",
                        "content": request.content
                    }
                ],
                stream=False
            )
            enhanced_content = enhance_response.choices[0].message.content.strip()
            if not enhanced_content:
                enhanced_content = request.content
        else:
            enhanced_content = request.content
    except Exception as e:
        logger.warning(f"Prompt enhancement failed, falling back to original: {e}")
        enhanced_content = request.content

    user_msg = ChatMessage(
        session_id=session_id,
        role=ChatRole.USER,
        content=enhanced_content,
        user_id=current_user.id,
        is_enhanced=request.enhance_prompt,
    )
    db.add(user_msg)
    await db.commit()

    # RAG pipeline
    context = None
    if request.lesson_id is not None:
        try:
            context = await retrieve_context(
                query=enhanced_content,
                db=db,
                lesson_id=request.lesson_id,
                top_k=6
            )
        except Exception as e:
            logger.error(f"RAG retrieval failed for lesson_id={request.lesson_id}: {e}")

        if context:
            user_content = RAG_PROMPT_TEMPLATE.format(
                context=context,
                query=enhanced_content
            )
        else:
            user_content = enhanced_content
    else:
        user_content = enhanced_content

    logger.debug("CONTEXT: %s", str(context)[:200] if context else "NO CONTEXT — lesson_id was not provided")

    # Build history
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    history = result.scalars().all()

    raw_history = []
    for i, msg in enumerate(history):
        if i == len(history) - 1 and msg.role == ChatRole.USER:
            raw_history.append({"role": "user", "content": user_content})
        elif msg.role == ChatRole.ASSISTANT and msg.tool_calls is not None:
            raw_history.append({
                "role": "assistant",
                "content": msg.content,
                "tool_calls": msg.tool_calls
            })
        elif msg.role == ChatRole.TOOL:
            raw_history.append({
                "role": "tool",
                "tool_call_id": msg.tool_call_id,
                "content": msg.content,
            })
        else:
            raw_history.append({"role": msg.role.value, "content": msg.content})

    system_prompt = get_system_prompt(request.language)

    trimmed_history = trim_history(
        history=raw_history,
        system_prompt=system_prompt,
        rag_context=context,
        max_tokens=50000
    )

    messages = [{"role": "system", "content": system_prompt}] + trimmed_history

    logger.debug("MESSAGES: %s", json.dumps(messages, indent=2))

    async def event_generator():
        # prevent shared state across concurrent requests from different users
        full_response = []

        async with session_factory() as gen_db:
            try:
                if request.enhance_prompt:
                    yield f"data: {json.dumps({'enhanced_prompt': enhanced_content})}\n\n"

                active_tools = TOOLS if request.web_search else []

                first_response = await client.chat.completions.create(
                    model=settings.MODEL,
                    messages=messages,
                    **({"tools": active_tools, "tool_choice": "auto"} if active_tools else {}),
                    stream=False
                )

                choice = first_response.choices[0]

                if choice.finish_reason == "tool_calls":
                    tool_call = choice.message.tool_calls[0]
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)

                    yield f"data: {json.dumps({'status': 'thinking', 'tool': tool_name})}\n\n"

                    assistant_tool_msg = ChatMessage(
                        session_id=session_id,
                        role=ChatRole.ASSISTANT,
                        content=None,
                        user_id=current_user.id,
                        tool_calls=[tc.model_dump() for tc in choice.message.tool_calls],
                    )
                    gen_db.add(assistant_tool_msg)
                    await gen_db.commit()

                    tool_result = await execute_tool(tool_name, tool_args, gen_db)

                    tool_result_msg = ChatMessage(
                        session_id=session_id,
                        role=ChatRole.TOOL,
                        content=tool_result,
                        user_id=current_user.id,
                        tool_call_id=tool_call.id,
                    )
                    gen_db.add(tool_result_msg)
                    await gen_db.commit()

                    messages_with_result = messages + [
                        choice.message.model_dump(exclude_none=True),
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": tool_result
                        }
                    ]

                    final_stream = await client.chat.completions.create(
                        model=settings.MODEL,
                        messages=messages_with_result,
                        stream=True
                    )

                    async for chunk in final_stream:
                        token = chunk.choices[0].delta.content
                        if token:
                            full_response.append(token)
                            yield f"data: {json.dumps({'token': token})}\n\n"

                    final_assistant_msg = ChatMessage(
                        session_id=session_id,
                        role=ChatRole.ASSISTANT,
                        content="".join(full_response),
                        user_id=current_user.id,
                        tool_calls=None,
                    )
                    gen_db.add(final_assistant_msg)

                    await _update_session_title(gen_db, session_id, enhanced_content)
                    await gen_db.commit()

                    yield f"data: {json.dumps({'status': 'done'})}\n\n"

                else:
                    stream = await client.chat.completions.create(
                        model=settings.MODEL,
                        messages=messages,
                        stream=True
                    )

                    async for chunk in stream:
                        token = chunk.choices[0].delta.content
                        if token:
                            full_response.append(token)
                            yield f"data: {json.dumps({'token': token})}\n\n"

                    final_assistant_msg = ChatMessage(
                        session_id=session_id,
                        role=ChatRole.ASSISTANT,
                        content="".join(full_response),
                        user_id=current_user.id,
                    )
                    gen_db.add(final_assistant_msg)

                    await _update_session_title(gen_db, session_id, enhanced_content)
                    await gen_db.commit()

                    yield f"data: {json.dumps({'status': 'done'})}\n\n"

            except Exception as e:
                await gen_db.rollback()
                logger.error(f"[chat error] session={session_id} error={e}", exc_info=True)
                yield f"data: {json.dumps({'error': 'Something went wrong. Please try again.'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")