from app.core.config import settings
import os
from app.models.lesson import LessonChunk, Lesson

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.client import client


def format_timestamp(seconds: float | None) -> str | None:
    if seconds is None:
        return None
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}:{secs:02d}"

async def retrieve_context(
        query: str,
        db: AsyncSession,
        lesson_id: int | None = None,
        source: str | None = None,
        top_k: int = 6
) -> str:

    response = await client.embeddings.create(
        model=settings.EMBEDDING_MODEL,
        input=query
    )

    query_embedding = response.data[0].embedding

    stmt = (
        select(LessonChunk, Lesson.order, Lesson.title)
        .join(Lesson, LessonChunk.lesson_id == Lesson.id)
        .order_by(LessonChunk.embedding.cosine_distance(query_embedding))
        .limit(top_k)
    )

    if lesson_id:
        stmt = stmt.where(LessonChunk.lesson_id == lesson_id)

    if source:
        stmt = stmt.where(LessonChunk.source == source)

    rows = (await db.execute(stmt)).all()

    if not rows:
        return ""
    
    context_parts = []

    for chunk, lesson_order, lesson_title in rows:

        timestamp = ""
        if chunk.start_time is not None:
            start = format_timestamp(chunk.start_time)
            end = format_timestamp(chunk.end_time)

            if chunk.source == "transcript":
                timestamp = f" | ⏱ {start} - {end}"
            elif chunk.source == "visual":
                timestamp = f" | 🎬 {start} - {end}"

        context_parts.append(
            f"[Lesson {lesson_order}: {lesson_title} | {chunk.source}{timestamp}]\n{chunk.content}"
        )
    return "\n\n---\n\n".join(context_parts)


