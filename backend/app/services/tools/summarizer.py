"""
summarizer.py — patched to add AI response caching + request coalescing.

Changes vs original
--------------------
* `summarize_lesson` now checks ai_cache before calling the LLM.
* Content hash is computed from the lesson chunks — changing the lesson
  content automatically invalidates the cached summary.
* Request coalescing: concurrent requests for the same summary share one LLM call.
* `generate_and_save_summary` passes school_id through for tenant-safe keys.
* All cache events are logged.

Note on existing DB storage
----------------------------
The original code stores the summary in `lesson.summary` (a JSON column).
This is KEPT as the source of truth for persistence across Redis restarts.
Redis is an acceleration layer on top of DB storage:
  1. Check Redis (fast, in-memory)
  2. Fall back to lesson.summary in DB (already the existing logic)
  3. If neither, generate + store in both DB and Redis
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.client import client
from app.models.lesson import LessonChunk, Lesson
from app.services.ai_cache import ai_cache, compute_content_hash, _lock  # ← NEW
import json
from app.core.config import settings
import re
import logging

logger = logging.getLogger(__name__)

SUMMARY_SOURCE = {"transcript", "pdf"}


async def summarize_lesson(
    lesson_id: int,
    lesson_title: str,
    lesson_order: int,
    db: AsyncSession,
    school_id: int = 0,       # ← NEW: required for tenant-safe cache keys
) -> dict | None:
    """
    Generate (or return cached) summary for a lesson.

    Cache strategy
    --------------
    Key: ai:summary:{school_id}:{lesson_id}:{content_hash}
    TTL: 7 days
    Coalescing: only 1 LLM call for concurrent identical requests
    Invalidation: triggered by lesson content changes (chunk re-generation)
    """

    # 1. Fetch chunks (needed for cache key AND prompt)                  #
    stmt = (
        select(LessonChunk)
        .where(
            LessonChunk.lesson_id == lesson_id,
            LessonChunk.source.in_(SUMMARY_SOURCE),
        )
        .order_by(LessonChunk.chunk_index)
    )
    chunks = (await db.execute(stmt)).scalars().all()

    if not chunks:
        logger.warning("No chunks found for lesson %d, skipping summary", lesson_id)
        return None

    chunk_texts = [c.content for c in chunks]
    content_hash = compute_content_hash(chunk_texts)
    combined_text = "\n\n".join(chunk_texts)

    MAX_CHARS = 80_000
    if len(combined_text) > MAX_CHARS:
        combined_text = combined_text[:MAX_CHARS]
        logger.warning("Lesson %d content truncated for summarization", lesson_id)

    # 2. Cache hit?                                                       #
    cached = await ai_cache.get_summary(school_id, lesson_id, content_hash)
    if cached is not None:
        return cached

    # 3. Request coalescing via distributed lock                         #
    lock_key_str = f"lock:ai:summary:{school_id}:{lesson_id}:{content_hash}"

    async with _lock(lock_key_str) as acquired:
        if not acquired:
            # Another worker is computing — wait for it
            result = await ai_cache.wait_for_summary(school_id, lesson_id, content_hash)
            if result is not None:
                return result
            logger.warning(
                "[AI_CACHE] Lock wait timed out for summary lesson=%d, computing independently",
                lesson_id,
            )

        # Double-check after acquiring lock
        cached = await ai_cache.get_summary(school_id, lesson_id, content_hash)
        if cached is not None:
            return cached

        # 4. Call LLM                                                         #
        response = await client.chat.completions.create(
            model=settings.MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a lesson summarizer. Always respond with valid JSON only. No markdown, no explanation.",
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
            ],
        )

        raw = re.sub(
            r"^```(?:json)?\s*|\s*```$",
            "",
            response.choices[0].message.content.strip(),
        )

        try:
            result = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(
                "Summary JSON parse failed for lesson %d: %s\nRaw: %s",
                lesson_id, e, raw[:200],
            )
            return None

        # 5. Store in Redis cache                                             #
        await ai_cache.set_summary(school_id, lesson_id, content_hash, result)

        return result


async def generate_and_save_summary(
    lesson_id: int,
    lesson_order: int,
    lesson_title: str,
    session_factory,
    school_id: int = 0,       # ← NEW: passed through for cache keys
) -> dict | None:
    """
    Generate summary, store in DB (lesson.summary), and store in Redis cache.
    Called as a background task after lesson upload, and as a fallback on GET.
    """
    async with session_factory() as db:
        result = await db.execute(select(Lesson).where(Lesson.id == lesson_id))
        lesson = result.scalars().first()

        if not lesson:
            return None

        summary = await summarize_lesson(
            lesson_id=lesson_id,
            lesson_order=lesson.order,
            lesson_title=lesson.title,
            db=db,
            school_id=school_id,
        )

        if summary is not None:
            # Persist to DB (original behaviour kept)
            lesson.summary = json.dumps(summary)
            await db.commit()

        return summary
