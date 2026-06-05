from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.client import client
from app.models.lesson import LessonChunk, Lesson
import json
from app.core.config import settings
import re
import logging

logger = logging.getLogger(__name__)

# async def summarize_lesson(
#     lesson_id: int,
#     lesson_order: int,
#     lesson_title: str,
#     source: str | None,
#     db: AsyncSession
# ):
    
#     """
#     Fetch all chunks for a lesson and return them for summarization
#     """

#     stmt = (
#         select(LessonChunk)
#         .where(LessonChunk.lesson_id == lesson_id)
#         .order_by(LessonChunk.chunk_index)
#     )

#     if source:
#         stmt = stmt.where(LessonChunk.source == source)


#     result = (await db.execute(stmt))

#     chunks = result.scalars().all()

#     if not chunks:
#         return {"error": f"No content found for lesson {lesson_id}"}
    
#     combined_text = "\n\n".join(chunk.content for chunk in chunks)

#     response = await client.chat.completions.create(
#         model=settings.MODEL,
#         messages=[
#             {
#                 "role": "system",
#                 "content": "You are a lesson summarizer. Always respond with valid JSON only. No markdown, no explanation."
#             },
#             {
#                 "role": "user",
#                 "content": f"""Summarize this lesson content.

#                 Lesson: {lesson_order}: {lesson_title}

#                 Content:
#                 {combined_text}

#                 Return this exact JSON structure:
#                 {{
#                     "lesson_order": {lesson_order},
#                     "lesson_title": "{lesson_title}",
#                     "overview": "2-3 sentence overview of what the lesson covers",
#                     "key_concepts": [
#                         "concept 1",
#                         "concept 2"
#                     ],
#                     "key_takeaway": "one essential sentence the student should remember"
#                 }}"""
#             }
#         ]
#     )

#     raw = response.choices[0].message.content.strip()
#     if raw.startswith("```"):
#         raw = raw.split("```")[1]
#         if raw.startswith("json"):
#             raw = raw[4:]

#     return json.loads(raw)




SUMMARY_SOURCE = {"transcript", "pdf"}

async def summarize_lesson(
    lesson_id: int,
    lesson_title: str,
    lesson_order: int,
    db: AsyncSession
):
    stmt = (
        select(LessonChunk)
            .where(
                LessonChunk.lesson_id == lesson_id,
                LessonChunk.source.in_(SUMMARY_SOURCE)
            )
            .order_by(LessonChunk.chunk_index)
    )

    chunks = (await db.execute(stmt)).scalars().all()

    if not chunks:
        logger.warning(f"No chunks found for lesson {lesson_id}, skipping summary")
        return None
    
    combined_text = "\n\n".join(chunk.content for chunk in chunks)

    MAX_CHARS = 80_000  
    if len(combined_text) > MAX_CHARS:
        combined_text = combined_text[:MAX_CHARS]
        logger.warning(f"Lesson {lesson_id} content truncated for summarization")

    response = await client.chat.completions.create(
        model=settings.MODEL,   
        messages=[
            {
                "role": "system",
                "content": "You are a lesson summarizer. Always respond with valid JSON only. No markdown, no explanation."
            },
            {
                "role": "user",
                "content": f"""
                Summarize this lesson content.

                Lesson: {lesson_order}: {lesson_title}

                Content:
                {combined_text}

                Return this exact JSON structure:
                {{
                    "lesson_order": {lesson_order},
                    "lesson_title": "{lesson_title}",
                    "overview": "2-3 sentence overview of what the lesson covers",
                    "key_concepts": ["concept 1", "concept 2"],
                    "key_takeaway": "one essential sentence the student should remember"
                }}
                """,
            },
        ]
    )

    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", response.choices[0].message.content.strip())

    try: 
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"Summary JSON parse failed for lesson {lesson_id}: {e}\nRaw: {raw[:200]}")
        return None
    


async def generate_and_save_summary(
        lesson_id: int, 
        lesson_order: int,
        lesson_title: str,
        session_factory
    ):
    async with session_factory() as db:

        result = await db.execute(select(Lesson).where(Lesson.id == lesson_id))
        lesson = result.scalars().first()
        
        if not lesson:
            return None

        summary = await summarize_lesson(
            lesson_id=lesson_id,
            lesson_order=lesson.order,
            lesson_title=lesson.title,
            db=db
        )
        if summary is not None:
            lesson.summary = json.dumps(summary)
            await db.commit()

        return summary