import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Annotated

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.instructions import get_system_prompt, RAG_PROMPT_TEMPLATE
from app.core.database import get_async_db, get_session_factory
from app.client import client
from app.services.rag import get_query_embedding, search_chunks
from app.services.context_manager import trim_history
from app.services.tools.definitions import TOOLS
from app.services.tools.executor import execute_tool
from app.schemas.chats import ChatRequest
from app.models.chats import ChatMessage, ChatRole, ChatSession
from app.models.user import User
from app.dependencies.auth import get_current_user, current_school_id
from app.services.ai_cache import ai_cache, _lock

logger = logging.getLogger(__name__)
router = APIRouter(prefix='/sessions', tags=['Chats'])


@asynccontextmanager
async def _noop_lock():
    """Used for non-cacheable requests — zero Redis overhead."""
    yield False


async def _get_session_or_404(session_id: str, db: AsyncSession) -> ChatSession:
    result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
    session = result.scalars().first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Session not found')
    return session


async def _update_session_title(gen_db: AsyncSession, session_id: str, title: str) -> None:
    stmt = select(ChatSession).where(ChatSession.id == session_id).with_for_update()
    session_to_update = (await gen_db.execute(stmt)).scalars().first()
    if session_to_update and session_to_update.title == 'New Chat':
        session_to_update.title = title[:60]


# ---------------------------------------------------------------------------
# Session CRUD — unchanged
# ---------------------------------------------------------------------------

@router.post('', status_code=201)
async def create_session(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: User = Depends(get_current_user),
):
    session = ChatSession(id=str(uuid.uuid4()), user_id=current_user.id, title='New Chat')
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.get('')
async def get_sessions(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.created_at.desc())
    )
    return list(result.scalars().all())


@router.delete('/{session_id}')
async def delete_session(
    session_id: str,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: User = Depends(get_current_user),
):
    session = await _get_session_or_404(session_id, db)
    if session.user_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, 'Not your session')
    await db.execute(ChatMessage.__table__.delete().where(ChatMessage.session_id == session_id))
    await db.delete(session)
    await db.commit()
    return {'message': 'Session deleted successfully'}


@router.get('/{session_id}/messages')
async def get_session_messages(
    session_id: str,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    session = await _get_session_or_404(session_id, db)
    if session.user_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, 'Not your session')
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Send message
# ---------------------------------------------------------------------------

@router.post('/{session_id}/messages')
async def send_message_stream(
    session_id: str,
    request: ChatRequest,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    session_factory: Annotated[async_sessionmaker, Depends(get_session_factory)],
    current_user: User = Depends(get_current_user),
    school_id: int = Depends(current_school_id),
):
    if not request.content or not request.content.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Message content cannot be empty',
        )

    session = await _get_session_or_404(session_id, db)
    if session.user_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, 'Not your session')

    # Redirect keywords — unchanged
    BLOCK_KEYWORDS = ['summarize', 'summary', 'overview', 'key points', 'summarise', 'quiz']
    if any(kw in request.content.lower() for kw in BLOCK_KEYWORDS):
        async def redirect_generator():
            msg = "Use the **Summary** and **Quiz** feature for this lesson to get a full structured summary and quiz respectively. I'm here to answer specific questions about the lesson content!"
            yield f"data: {json.dumps({'token': msg})}\n\n"
            yield f"data: {json.dumps({'status': 'done'})}\n\n"
        return StreamingResponse(redirect_generator(), media_type='text/event-stream')

    # Parallel pre-processing — unchanged
    try:
        async def _get_embedding() -> list[float] | None:
            if request.lesson_id is None:
                return None
            try:
                return await get_query_embedding(request.content)
            except Exception as e:
                logger.error(f'Embedding failed: {e}')
                return None

        async def _get_history() -> list[ChatMessage]:
            result = await db.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at)
            )
            return list(result.scalars().all())

        async def _enhance() -> str:
            try:
                enhance_response = await client.chat.completions.create(
                    model=settings.MODEL,
                    messages=[
                        {
                            'role': 'system',
                            'content': "You are a prompt enhancer. Rewrite the student's questions to be clearer, more specific, and more detailed. Return ONLY the rewritten question, nothing else.",
                        },
                        {'role': 'user', 'content': request.content},
                    ],
                    stream=False,
                )
                result = enhance_response.choices[0].message.content.strip()
                return result if result else request.content
            except Exception as e:
                logger.warning(f'Prompt enhancement failed, falling back to original: {e}')
                return request.content

        async def _maybe_enhance() -> str:
            if not request.enhance_prompt:
                return request.content
            return await _enhance()

        embedding, history, enhanced_content = await asyncio.gather(
            _get_embedding(),
            _get_history(),
            _maybe_enhance(),
        )

    except Exception as e:
        logger.warning(f'Pre-processing failed, falling back: {e}')
        enhanced_content = request.content
        embedding = None
        history = []

    # ------------------------------------------------------------------
    # Cache gate
    # ------------------------------------------------------------------
    cacheable = ai_cache.is_chat_cacheable(
        lesson_id=request.lesson_id,
        history_len=len(history),
        web_search=request.web_search,
        enhance_prompt=request.enhance_prompt,
    )

    # FIX: always define lock_key so event_generator() closure never hits
    # a NameError when cacheable=False. When not cacheable, the value is
    # never actually used — _noop_lock() is selected instead.
    lock_key: str | None = (
        ai_cache.get_chat_lock_key(
            school_id, request.lesson_id, request.language, request.content
        )
        if cacheable else None
    )

    if cacheable:
        # Cache hit — zero embedding cost, zero LLM cost
        cached_response = await ai_cache.get_chat(
            school_id=school_id,
            lesson_id=request.lesson_id,
            language=request.language,
            question=request.content,
        )
        if cached_response is not None:
            # Persist messages so chat history stays consistent
            db.add(ChatMessage(
                session_id=session_id, role=ChatRole.USER,
                content=request.content, user_id=current_user.id, is_enhanced=False,
            ))
            db.add(ChatMessage(
                session_id=session_id, role=ChatRole.ASSISTANT,
                content=cached_response, user_id=current_user.id,
            ))
            await db.commit()

            async def _cached_stream():
                yield f"data: {json.dumps({'token': cached_response, 'from_cache': True})}\n\n"
                yield f"data: {json.dumps({'status': 'done'})}\n\n"
            return StreamingResponse(_cached_stream(), media_type='text/event-stream')

        # Coalescing — check if another worker is already computing
        from app.core.redis import get_redis as _get_redis
        _redis = _get_redis()
        if _redis is not None and await _redis.exists(lock_key):
            logger.info("[AI_LOCK WAIT] key=%s waiting for concurrent worker", lock_key)
            waited = await ai_cache.wait_for_chat(
                school_id, request.lesson_id, request.language, request.content
            )
            if waited is not None:
                # FIX: also save user_msg here — was missing in previous version
                db.add(ChatMessage(
                    session_id=session_id, role=ChatRole.USER,
                    content=request.content, user_id=current_user.id, is_enhanced=False,
                ))
                db.add(ChatMessage(
                    session_id=session_id, role=ChatRole.ASSISTANT,
                    content=waited, user_id=current_user.id,
                ))
                await db.commit()

                async def _waited_stream():
                    yield f"data: {json.dumps({'token': waited, 'from_cache': True})}\n\n"
                    yield f"data: {json.dumps({'status': 'done'})}\n\n"
                return StreamingResponse(_waited_stream(), media_type='text/event-stream')
            # Lock holder crashed — fall through to compute independently

    # Save user message — original position, unchanged
    user_msg = ChatMessage(
        session_id=session_id,
        role=ChatRole.USER,
        content=enhanced_content,
        user_id=current_user.id,
        is_enhanced=request.enhance_prompt,
    )
    db.add(user_msg)
    await db.commit()

    # RAG — unchanged
    context = None
    if embedding is not None:
        try:
            async with session_factory() as rag_db:
                context = await search_chunks(
                    embedding=embedding,
                    db=rag_db,
                    lesson_id=request.lesson_id,
                    top_k=6,
                )
        except Exception as e:
            logger.error(f'RAG chunk search failed for lesson_id={request.lesson_id}: {e}')
            context = None

    logger.debug(
        'CONTEXT: %s',
        str(context)[:200] if context else 'NO CONTEXT — lesson_id was not provided',
    )

    if context:
        user_content = RAG_PROMPT_TEMPLATE.format(context=context, query=enhanced_content)
    else:
        user_content = enhanced_content

    # Build message history — unchanged
    raw_history = []
    for msg in history:
        if msg.role == ChatRole.ASSISTANT and msg.tool_calls is not None:
            raw_history.append({
                'role': 'assistant',
                'content': msg.content,
                'tool_calls': msg.tool_calls,
            })
        elif msg.role == ChatRole.TOOL:
            raw_history.append({
                'role': 'tool',
                'tool_call_id': msg.tool_call_id,
                'content': msg.content,
            })
        else:
            raw_history.append({'role': msg.role.value, 'content': msg.content})

    raw_history.append({'role': 'user', 'content': user_content})

    system_prompt = get_system_prompt(request.language)
    trimmed_history = trim_history(
        history=raw_history,
        system_prompt=system_prompt,
        rag_context=context,
        max_tokens=8000,
    )
    messages = [{'role': 'system', 'content': system_prompt}] + trimmed_history
    logger.debug('MESSAGES: %s', json.dumps(messages, indent=2))

    # Streaming generator
    async def event_generator():
        async with session_factory() as gen_db:
            # FIX: lock_key is always defined above (None when not cacheable)
            # _noop_lock() used when not cacheable — zero Redis overhead
            lock_ctx = _lock(lock_key) if cacheable else _noop_lock()
            async with lock_ctx as lock_acquired:
                try:
                    full_response = []

                    if request.enhance_prompt:
                        yield f"data: {json.dumps({'enhanced_prompt': enhanced_content})}\n\n"

                    active_tools = TOOLS if request.web_search else []
                    stream = await client.chat.completions.create(
                        model=settings.MODEL,
                        messages=messages,
                        max_tokens=600,
                        **({'tools': active_tools, 'tool_choice': 'auto'} if active_tools else {}),
                        stream=True,
                    )

                    finish_reason = None
                    tool_call_id = None
                    tool_call_name = None
                    tool_call_args_parts: list[str] = []

                    async for chunk in stream:
                        choice = chunk.choices[0]
                        delta = choice.delta
                        finish_reason = choice.finish_reason or finish_reason
                        if delta.tool_calls:
                            tc = delta.tool_calls[0]
                            if tc.id:
                                tool_call_id = tc.id
                            if tc.function and tc.function.name:
                                tool_call_name = tc.function.name
                            if tc.function and tc.function.arguments:
                                tool_call_args_parts.append(tc.function.arguments)
                        elif delta.content:
                            full_response.append(delta.content)
                            yield f"data: {json.dumps({'token': delta.content})}\n\n"

                    # Tool call branch — unchanged, never cached
                    if finish_reason == 'tool_calls' and tool_call_name and tool_call_id:
                        tool_args = json.loads(''.join(tool_call_args_parts))
                        yield f"data: {json.dumps({'status': 'thinking', 'tool': tool_call_name})}\n\n"
                        tool_calls_payload = [{
                            'id': tool_call_id,
                            'type': 'function',
                            'function': {
                                'name': tool_call_name,
                                'arguments': ''.join(tool_call_args_parts),
                            },
                        }]
                        assistant_tool_msg = ChatMessage(
                            session_id=session_id,
                            role=ChatRole.ASSISTANT,
                            content=None,
                            user_id=current_user.id,
                            tool_calls=tool_calls_payload,
                        )
                        gen_db.add(assistant_tool_msg)
                        await gen_db.commit()

                        tool_result = await execute_tool(tool_call_name, tool_args, gen_db)
                        tool_result_msg = ChatMessage(
                            session_id=session_id,
                            role=ChatRole.TOOL,
                            content=tool_result,
                            user_id=current_user.id,
                            tool_call_id=tool_call_id,
                        )
                        gen_db.add(tool_result_msg)
                        await gen_db.commit()

                        messages_with_result = messages + [
                            {'role': 'assistant', 'content': None, 'tool_calls': tool_calls_payload},
                            {'role': 'tool', 'tool_call_id': tool_call_id, 'content': tool_result},
                        ]
                        final_stream = await client.chat.completions.create(
                            model=settings.MODEL,
                            max_tokens=600,
                            messages=messages_with_result,
                            stream=True,
                        )
                        async for chunk in final_stream:
                            token = chunk.choices[0].delta.content
                            if token:
                                full_response.append(token)
                                yield f"data: {json.dumps({'token': token})}\n\n"

                        final_assistant_msg = ChatMessage(
                            session_id=session_id,
                            role=ChatRole.ASSISTANT,
                            content=''.join(full_response),
                            user_id=current_user.id,
                            tool_calls=None,
                        )
                        gen_db.add(final_assistant_msg)
                        await _update_session_title(gen_db, session_id, enhanced_content)
                        await gen_db.commit()
                        yield f"data: {json.dumps({'status': 'done'})}\n\n"

                    else:
                        # Normal response branch
                        assembled = ''.join(full_response)
                        final_assistant_msg = ChatMessage(
                            session_id=session_id,
                            role=ChatRole.ASSISTANT,
                            content=assembled, 
                            user_id=current_user.id,
                        )
                        gen_db.add(final_assistant_msg)
                        await _update_session_title(gen_db, session_id, enhanced_content)
                        await gen_db.commit()

                        # Store in cache only when this worker is the lock holder
                        if cacheable and lock_acquired and assembled:
                            await ai_cache.set_chat(
                                school_id=school_id,
                                lesson_id=request.lesson_id,
                                language=request.language,
                                question=request.content,
                                response=assembled,
                            )

                        yield f"data: {json.dumps({'status': 'done'})}\n\n"

                except asyncio.CancelledError:
                    await gen_db.rollback()
                    logger.info(f"Stream cancelled by client: session={session_id}")

                except Exception as e:
                    await gen_db.rollback()
                    logger.error(
                        f'[chat error] session={session_id} error={e}', exc_info=True
                    )
                    yield f"data: {json.dumps({'error': 'Something went wrong. Please try again.'})}\n\n"

    return StreamingResponse(event_generator(), media_type='text/event-stream')
