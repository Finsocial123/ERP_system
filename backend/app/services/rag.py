import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.lesson import LessonChunk, Lesson
from app.core.config import settings
from app.client import client

logger = logging.getLogger(__name__)


def format_timestamp(seconds: float | None) -> str | None:
    if seconds is None:
        return None
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}:{secs:02d}"


async def get_query_embedding(query: str) -> list[float]:
    """
    Step 1 of RAG — call the embedding API only.
    Returns the raw embedding vector.
    Kept separate so callers can run this concurrently with other I/O.
    """
    response = await client.embeddings.create(
        model=settings.EMBEDDING_MODEL,
        input=query,
    )
    return response.data[0].embedding


async def search_chunks(
    embedding: list[float],
    db: AsyncSession,
    lesson_id: int | None = None,
    source: str | None = None,
    top_k: int = 6,
) -> str:
    """
    Step 2 of RAG — pgvector cosine search using a pre-computed embedding.
    Kept separate so callers can supply an embedding obtained in parallel.
    """
    stmt = (
        select(LessonChunk, Lesson.order, Lesson.title)
        .join(Lesson, LessonChunk.lesson_id == Lesson.id)
        .order_by(LessonChunk.embedding.cosine_distance(embedding))
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


async def retrieve_context(
    query: str,
    db: AsyncSession,
    lesson_id: int | None = None,
    source: str | None = None,
    top_k: int = 6,
) -> str:
    """
    Original all-in-one function — unchanged public API.
    Still usable anywhere that doesn't need the parallelised path
    (e.g. quiz/summary routes that call it directly).
    """
    embedding = await get_query_embedding(query)
    return await search_chunks(
        embedding=embedding,
        db=db,
        lesson_id=lesson_id,
        source=source,
        top_k=top_k,
    )
