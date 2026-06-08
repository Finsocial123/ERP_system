"""
rag.py — patched to cache query embeddings in Redis.

Changes vs original
--------------------
* `get_query_embedding` checks Redis before calling the embedding API.
  Cache key: embedding:{sha256(query_text)}  TTL 24 h
* `search_chunks` and `retrieve_context` are unchanged.
* If Redis is down, the original API call is made transparently.

Why caching embeddings is safe here
-------------------------------------
Student AI-tutor queries repeat frequently ("What is photosynthesis?",
"Explain Newton's second law", etc.).  Embeddings are deterministic for a
given model — the same text always produces the same vector.  We cache by
text hash so identical queries skip the embedding API call entirely.

The embedding model is identified in settings.EMBEDDING_MODEL.  If the
model changes, flush the pattern "embedding:*" from Redis manually.
"""

from __future__ import annotations

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.lesson import LessonChunk, Lesson
from app.core.config import settings
from app.client import client
from app.services.cache import cache                        # ← NEW

logger = logging.getLogger(__name__)


def format_timestamp(seconds: float | None) -> str | None:
    if seconds is None:
        return None
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}:{secs:02d}"


async def get_query_embedding(query: str) -> list[float]:
    """
    Step 1 of RAG — return the embedding vector for *query*.

    Checks Redis first.  On a cache hit the OpenRouter embedding API is
    not called, saving ~50-80 ms and API cost.
    """
    # Cache hit
    cached = await cache.get_embedding(query)
    if cached is not None:
        logger.debug("Embedding cache hit for query (len=%d)", len(query))
        return cached

    # Cache miss — call embedding API
    response = await client.embeddings.create(
        model=settings.EMBEDDING_MODEL,
        input=query,
    )
    embedding = response.data[0].embedding

    # Store — fire and forget (no await needed for correctness)
    await cache.set_embedding(query, embedding)

    return embedding


async def search_chunks(
    embedding: list[float],
    db: AsyncSession,
    lesson_id: int | None = None,
    source: str | None = None,
    top_k: int = 6,
) -> str:
    """
    Step 2 of RAG — pgvector cosine search using a pre-computed embedding.
    Unchanged from original.  Vector search results are NOT cached because:
    - New chunks are added as teachers upload lessons.
    - TTL-based invalidation would be complex and error-prone.
    - pgvector with HNSW index makes this fast enough (~10-20 ms).
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
    Original all-in-one function — public API unchanged.
    Now benefits from embedding cache on the first step.
    """
    embedding = await get_query_embedding(query)
    return await search_chunks(
        embedding=embedding,
        db=db,
        lesson_id=lesson_id,
        source=source,
        top_k=top_k,
    )
