from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.client import client
from app.models.lesson import LessonChunk
import json
from app.core.config import settings

# async def summarize_lesson(lesson_id: int, db: AsyncSession) -> dict:


#     result = await db.execute(
#         select(models.LessonChunk)
#         .where(models.LessonChunk.lesson_id == lesson_id)
#         .order_by(models.LessonChunk.chunk_index)
#         )
    
#     chunks = result.scalars.all()

#     if not chunks:
#         return {"error": f"No content found for lesson {lesson_id}"}
    
#     combined_text = "\n\n".join(chunk.content for chunk in chunks)

#     return {
#         "lesson_id": lesson_id,
#         "content": combined_text
#     }


async def summarize_lesson(
    lesson_id: int,
    lesson_order: int,
    lesson_title: str,
    source: str | None,
    db: AsyncSession
):
    
    """
    Fetch all chunks for a lesson and return them for summarization
    """

    stmt = (
        select(LessonChunk)
        .where(LessonChunk.lesson_id == lesson_id)
        .order_by(LessonChunk.chunk_index)
    )

    if source:
        stmt = stmt.where(LessonChunk.source == source)


    result = (await db.execute(stmt))

    chunks = result.scalars().all()

    if not chunks:
        return {"error": f"No content found for lesson {lesson_id}"}
    
    combined_text = "\n\n".join(chunk.content for chunk in chunks)

    response = await client.chat.completions.create(
        model=settings.MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are a lesson summarizer. Always respond with valid JSON only. No markdown, no explanation."
            },
            {
                "role": "user",
                "content": f"""Summarize this lesson content.

                Lesson: {lesson_order}: {lesson_title}

                Content:
                {combined_text}

                Return this exact JSON structure:
                {{
                    "lesson_order": {lesson_order},
                    "lesson_title": "{lesson_title}",
                    "overview": "2-3 sentence overview of what the lesson covers",
                    "key_concepts": [
                        "concept 1",
                        "concept 2"
                    ],
                    "key_takeaway": "one essential sentence the student should remember"
                }}"""
            }
        ]
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    return json.loads(raw)