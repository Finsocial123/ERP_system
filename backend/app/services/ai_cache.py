"""
ai_cache.py — Enterprise-grade AI response cache with request coalescing.

Architecture
------------
This module is the single authority for all AI response caching.
It extends the existing CacheService pattern from cache.py without
modifying it — keeping concerns cleanly separated.

What is cached
--------------
  SAFE (content-addressed, deterministic given the same lesson chunks):
  • Lesson summaries          — keyed by lesson_id + content_hash
  • Quiz generations          — keyed by lesson_id + num_q + difficulty + content_hash
  • Curriculum plans          — keyed by topic + audience + weeks + lessons + lang

  NEVER cached:
  • Chat/tutor conversations  — multi-turn, context-dependent, user-specific
  • Prompt enhancement        — per-user personalisation
  • Notice/announcement AI    — school-operational, not content
  • Frame analysis            — one-time processing step during upload

Key design
----------
  ai:summary:{school_id}:{lesson_id}:{content_hash}
  ai:quiz:{school_id}:{lesson_id}:{num_q}:{difficulty}:{content_hash}
  ai:curriculum:{school_id}:{topic_hash}

  school_id is always part of the key → cross-school leakage is impossible.
  content_hash captures the actual lesson content → stale responses after
  re-upload are impossible.

Request coalescing
------------------
When N concurrent requests arrive for the same uncached key:
  1. First request acquires a Redis lock (SETNX-based, 60 s TTL).
  2. Remaining N-1 requests poll for the result (0.2 s interval, 55 s max).
  3. Once stored, polling requests return cached data — no duplicate LLM calls.

Observability
-------------
All cache events emit structured log lines at INFO level:
  [AI_CACHE HIT]   key=ai:quiz:1:42:5:medium:abc123
  [AI_CACHE MISS]  key=ai:quiz:1:42:5:medium:abc123
  [AI_CACHE STORE] key=ai:quiz:1:42:5:medium:abc123  ttl=3600
  [AI_LOCK ACQUIRED] key=lock:ai:quiz:…
  [AI_LOCK WAIT]   key=lock:ai:quiz:… attempt=3
  [AI_LOCK RELEASED] key=lock:ai:quiz:…
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Any

from app.core.redis import get_redis

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TTL_SUMMARY    = 7 * 24 * 3600   # 7 days  — summary is regenerated only when lesson content changes
TTL_QUIZ       = 3 * 24 * 3600   # 3 days  — quiz variants per difficulty; fresh enough
TTL_CURRICULUM = 24 * 3600       # 1 day   — curriculum plan for a given topic spec
TTL_CHAT       = 24 * 3600       # 24 hours — chat responses for identical lesson questions

LOCK_TTL       = 60              # seconds — lock expires if holder crashes
LOCK_POLL_INTERVAL = 0.25        # seconds — how often waiters check for result
LOCK_MAX_WAIT  = 55              # seconds — give up waiting after this


# ---------------------------------------------------------------------------
# Internal low-level helpers (mirrors cache.py style)
# ---------------------------------------------------------------------------

def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]   # 16 hex chars is plenty for keys


async def _get(key: str) -> Any | None:
    redis = get_redis()
    if redis is None:
        return None
    try:
        raw = await redis.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as exc:
        logger.debug("[AI_CACHE] GET error key=%s: %s", key, exc)
        return None


async def _set(key: str, value: Any, ttl: int) -> None:
    redis = get_redis()
    if redis is None:
        return
    try:
        await redis.setex(key, ttl, json.dumps(value, default=str))
        logger.info("[AI_CACHE STORE] key=%s ttl=%d", key, ttl)
    except Exception as exc:
        logger.debug("[AI_CACHE] SET error key=%s: %s", key, exc)


async def _delete_pattern(pattern: str) -> None:
    redis = get_redis()
    if redis is None:
        return
    try:
        cursor = 0
        total = 0
        while True:
            cursor, keys = await redis.scan(cursor, match=pattern, count=200)
            if keys:
                await redis.delete(*keys)
                total += len(keys)
            if cursor == 0:
                break
        if total:
            logger.info("[AI_CACHE INVALIDATE] pattern=%s keys_deleted=%d", pattern, total)
    except Exception as exc:
        logger.debug("[AI_CACHE] DELETE pattern error %s: %s", pattern, exc)


# ---------------------------------------------------------------------------
# Request coalescing via Redis lock
# ---------------------------------------------------------------------------

@asynccontextmanager
async def _lock(lock_key: str):
    """
    Async context manager that acquires a Redis lock.

    Usage:
        async with _lock("lock:ai:quiz:...") as acquired:
            if acquired:
                # we are the one who must compute
                ...
    """
    redis = get_redis()
    if redis is None:
        # No Redis — just yield True and let the caller compute normally
        yield True
        return

    acquired = await redis.set(lock_key, "1", nx=True, ex=LOCK_TTL)
    if acquired:
        logger.info("[AI_LOCK ACQUIRED] key=%s", lock_key)
    try:
        yield bool(acquired)
    finally:
        if acquired:
            try:
                await redis.delete(lock_key)
                logger.info("[AI_LOCK RELEASED] key=%s", lock_key)
            except Exception:
                pass


async def _wait_for_result(cache_key: str, lock_key: str) -> Any | None:
    """
    Poll until the lock holder stores the result or the lock expires.
    Returns the cached value if it appears, None if we timed out.
    """
    redis = get_redis()
    deadline = time.monotonic() + LOCK_MAX_WAIT
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        await asyncio.sleep(LOCK_POLL_INTERVAL)

        # Check if result is now available
        result = await _get(cache_key)
        if result is not None:
            logger.info("[AI_LOCK WAIT] key=%s resolved_after_attempts=%d", lock_key, attempt)
            return result

        # Check if lock is gone (holder crashed without storing)
        lock_exists = await redis.exists(lock_key)
        if not lock_exists:
            logger.warning("[AI_LOCK WAIT] key=%s lock_gone_without_result attempt=%d", lock_key, attempt)
            return None

        logger.debug("[AI_LOCK WAIT] key=%s attempt=%d", lock_key, attempt)

    logger.warning("[AI_LOCK WAIT] key=%s timed_out_after=%ds", lock_key, LOCK_MAX_WAIT)
    return None


# ---------------------------------------------------------------------------
# Key builders
# ---------------------------------------------------------------------------

class _AIKeys:

    @staticmethod
    def summary(school_id: int, lesson_id: int, content_hash: str) -> str:
        return f"ai:summary:{school_id}:{lesson_id}:{content_hash}"

    @staticmethod
    def summary_lock(school_id: int, lesson_id: int, content_hash: str) -> str:
        return f"lock:ai:summary:{school_id}:{lesson_id}:{content_hash}"

    @staticmethod
    def quiz(school_id: int, lesson_id: int, num_questions: int, difficulty: str, content_hash: str) -> str:
        return f"ai:quiz:{school_id}:{lesson_id}:{num_questions}:{difficulty}:{content_hash}"

    @staticmethod
    def quiz_lock(school_id: int, lesson_id: int, num_questions: int, difficulty: str, content_hash: str) -> str:
        return f"lock:ai:quiz:{school_id}:{lesson_id}:{num_questions}:{difficulty}:{content_hash}"

    @staticmethod
    def curriculum(school_id: int, topic: str, audience: str, weeks: int, num_lessons: int, language: str) -> str:
        spec = f"{topic}|{audience}|{weeks}|{num_lessons}|{language}"
        return f"ai:curriculum:{school_id}:{_sha256(spec)}"

    @staticmethod
    def curriculum_lock(school_id: int, spec_hash: str) -> str:
        return f"lock:ai:curriculum:{school_id}:{spec_hash}"

    # Chat response cache
    @staticmethod
    def chat_response(school_id: int, lesson_id: int, language: str, question_hash: str) -> str:
        return f"ai:chat:{school_id}:{lesson_id}:{language}:{question_hash}"

    @staticmethod
    def chat_lock(school_id: int, lesson_id: int, language: str, question_hash: str) -> str:
        return f"lock:ai:chat:{school_id}:{lesson_id}:{language}:{question_hash}"

    # Invalidation patterns
    @staticmethod
    def lesson_pattern(school_id: int, lesson_id: int) -> str:
        return f"ai:*:{school_id}:{lesson_id}:*"


AIKeys = _AIKeys()


def normalize_question(text: str) -> str:
    """
    Normalize a question for stable cache key generation.

    Rules:
    - Lowercase
    - Collapse all whitespace to a single space
    - Strip leading/trailing whitespace
    - Strip trailing punctuation (? ! .)

    This means "explain FastAPI?", "Explain FastAPI", and "  explain  fastapi  "
    all map to the same cache key.
    """
    import re
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = text.rstrip("?.! ")
    return text


def question_hash(text: str) -> str:
    """SHA-256 of the normalized question text (first 16 hex chars)."""
    return _sha256(normalize_question(text))


# ---------------------------------------------------------------------------
# Public content-hash helper
# ---------------------------------------------------------------------------

def compute_content_hash(chunks_text: list[str]) -> str:
    """
    Hash the concatenated content of lesson chunks.
    Used to detect when lesson content changes (re-upload invalidates cache).
    """
    combined = "\n".join(chunks_text)
    return _sha256(combined)


# ---------------------------------------------------------------------------
# AI Cache Service
# ---------------------------------------------------------------------------

class AICacheService:
    """
    Public API for AI response caching.
    All methods are safe to call even when Redis is down.
    """

    # ------------------------------------------------------------------
    # Lesson Summary
    # ------------------------------------------------------------------

    async def get_summary(self, school_id: int, lesson_id: int, content_hash: str) -> dict | None:
        key = AIKeys.summary(school_id, lesson_id, content_hash)
        result = await _get(key)
        if result is not None:
            logger.info("[AI_CACHE HIT] key=%s", key)
        else:
            logger.info("[AI_CACHE MISS] key=%s", key)
        return result

    async def set_summary(self, school_id: int, lesson_id: int, content_hash: str, data: dict) -> None:
        key = AIKeys.summary(school_id, lesson_id, content_hash)
        await _set(key, data, TTL_SUMMARY)

    async def get_summary_lock(self, school_id: int, lesson_id: int, content_hash: str):
        """Returns an async context manager for the summary compute lock."""
        lock_key = AIKeys.summary_lock(school_id, lesson_id, content_hash)
        return _lock(lock_key)

    async def wait_for_summary(self, school_id: int, lesson_id: int, content_hash: str) -> dict | None:
        cache_key = AIKeys.summary(school_id, lesson_id, content_hash)
        lock_key = AIKeys.summary_lock(school_id, lesson_id, content_hash)
        return await _wait_for_result(cache_key, lock_key)

    # ------------------------------------------------------------------
    # Quiz Generation
    # ------------------------------------------------------------------

    async def get_quiz(
        self, school_id: int, lesson_id: int,
        num_questions: int, difficulty: str, content_hash: str
    ) -> dict | None:
        key = AIKeys.quiz(school_id, lesson_id, num_questions, difficulty, content_hash)
        result = await _get(key)
        if result is not None:
            logger.info("[AI_CACHE HIT] key=%s", key)
        else:
            logger.info("[AI_CACHE MISS] key=%s", key)
        return result

    async def set_quiz(
        self, school_id: int, lesson_id: int,
        num_questions: int, difficulty: str, content_hash: str,
        data: dict
    ) -> None:
        key = AIKeys.quiz(school_id, lesson_id, num_questions, difficulty, content_hash)
        await _set(key, data, TTL_QUIZ)

    def get_quiz_lock_key(
        self, school_id: int, lesson_id: int,
        num_questions: int, difficulty: str, content_hash: str
    ) -> str:
        return AIKeys.quiz_lock(school_id, lesson_id, num_questions, difficulty, content_hash)

    async def wait_for_quiz(
        self, school_id: int, lesson_id: int,
        num_questions: int, difficulty: str, content_hash: str
    ) -> dict | None:
        cache_key = AIKeys.quiz(school_id, lesson_id, num_questions, difficulty, content_hash)
        lock_key = AIKeys.quiz_lock(school_id, lesson_id, num_questions, difficulty, content_hash)
        return await _wait_for_result(cache_key, lock_key)

    # ------------------------------------------------------------------
    # Curriculum Generation
    # ------------------------------------------------------------------

    async def get_curriculum(
        self, school_id: int, topic: str, audience: str,
        weeks: int, num_lessons: int, language: str
    ) -> dict | None:
        key = AIKeys.curriculum(school_id, topic, audience, weeks, num_lessons, language)
        result = await _get(key)
        if result is not None:
            logger.info("[AI_CACHE HIT] key=%s", key)
        else:
            logger.info("[AI_CACHE MISS] key=%s", key)
        return result

    async def set_curriculum(
        self, school_id: int, topic: str, audience: str,
        weeks: int, num_lessons: int, language: str, data: dict
    ) -> None:
        key = AIKeys.curriculum(school_id, topic, audience, weeks, num_lessons, language)
        await _set(key, data, TTL_CURRICULUM)

    def _curriculum_spec_hash(self, topic: str, audience: str, weeks: int, num_lessons: int, language: str) -> str:
        spec = f"{topic}|{audience}|{weeks}|{num_lessons}|{language}"
        return _sha256(spec)

    def get_curriculum_lock_key(
        self, school_id: int, topic: str, audience: str,
        weeks: int, num_lessons: int, language: str
    ) -> str:
        spec_hash = self._curriculum_spec_hash(topic, audience, weeks, num_lessons, language)
        return AIKeys.curriculum_lock(school_id, spec_hash)

    async def wait_for_curriculum(
        self, school_id: int, topic: str, audience: str,
        weeks: int, num_lessons: int, language: str
    ) -> dict | None:
        cache_key = AIKeys.curriculum(school_id, topic, audience, weeks, num_lessons, language)
        lock_key = self.get_curriculum_lock_key(school_id, topic, audience, weeks, num_lessons, language)
        return await _wait_for_result(cache_key, lock_key)

    # ------------------------------------------------------------------
    # Chat Response Cache
    # ------------------------------------------------------------------

    def is_chat_cacheable(
        self,
        lesson_id: int | None,
        history_len: int,
        web_search: bool,
        enhance_prompt: bool,
    ) -> bool:
        """
        Returns True only when all safety conditions are met.

        Rules (per spec):
          - lesson_id must be present  (content-grounded response)
          - history_len <= 1           (only first message in session; 1 = the
                                        user message we are about to add, meaning
                                        prior turns = 0)
          - web_search must be False   (web results are time-sensitive)
          - enhance_prompt must be False (prompt was rewritten — non-deterministic)
        """
        if lesson_id is None:
            return False
        if history_len > 1:
            return False
        if web_search:
            return False
        if enhance_prompt:
            return False
        return True

    def _chat_key(self, school_id: int, lesson_id: int, language: str, q: str) -> str:
        return AIKeys.chat_response(school_id, lesson_id, language, question_hash(q))

    def _chat_lock_key(self, school_id: int, lesson_id: int, language: str, q: str) -> str:
        return AIKeys.chat_lock(school_id, lesson_id, language, question_hash(q))

    async def get_chat(
        self, school_id: int, lesson_id: int, language: str, question: str
    ) -> str | None:
        key = self._chat_key(school_id, lesson_id, language, question)
        # BUG FIX: chat responses are stored as raw strings via redis.setex,
        # NOT as JSON. Using _get() would call json.loads() on plain text
        # and always raise JSONDecodeError, returning None even on cache hits.
        # We must read directly from Redis to get the raw string.
        redis = get_redis()
        if redis is None:
            return None
        try:
            raw = await redis.get(key)
            if raw is not None:
                logger.info("[AI_CACHE HIT] key=%s", key)
                return raw
            logger.info("[AI_CACHE MISS] key=%s", key)
            return None
        except Exception as exc:
            logger.debug("[AI_CACHE] GET error key=%s: %s", key, exc)
            return None

    async def set_chat(
        self, school_id: int, lesson_id: int, language: str, question: str, response: str
    ) -> None:
        key = self._chat_key(school_id, lesson_id, language, question)
        # Store as plain string (not JSON-wrapped dict) for simplicity
        redis = get_redis()
        if redis is None:
            return
        try:
            await redis.setex(key, TTL_CHAT, response)
            logger.info("[AI_CACHE STORE] key=%s ttl=%d", key, TTL_CHAT)
        except Exception as exc:
            logger.debug("[AI_CACHE] SET error key=%s: %s", key, exc)

    def get_chat_lock_key(
        self, school_id: int, lesson_id: int, language: str, question: str
    ) -> str:
        return self._chat_lock_key(school_id, lesson_id, language, question)

    async def wait_for_chat(
        self, school_id: int, lesson_id: int, language: str, question: str
    ) -> str | None:
        cache_key = self._chat_key(school_id, lesson_id, language, question)
        lock_key = self._chat_lock_key(school_id, lesson_id, language, question)
        # _wait_for_result returns parsed JSON; for chat we stored a raw string
        # so we read directly from Redis
        redis = get_redis()
        if redis is None:
            return None
        deadline = time.monotonic() + LOCK_MAX_WAIT
        attempt = 0
        while time.monotonic() < deadline:
            attempt += 1
            await asyncio.sleep(LOCK_POLL_INTERVAL)
            try:
                raw = await redis.get(cache_key)
                if raw is not None:
                    logger.info(
                        "[AI_LOCK WAIT] key=%s resolved_after_attempts=%d", lock_key, attempt
                    )
                    return raw
                lock_exists = await redis.exists(lock_key)
                if not lock_exists:
                    logger.warning(
                        "[AI_LOCK WAIT] key=%s lock_gone_without_result attempt=%d",
                        lock_key, attempt,
                    )
                    return None
            except Exception as exc:
                logger.debug("[AI_CACHE] wait_for_chat error: %s", exc)
                return None
            logger.debug("[AI_LOCK WAIT] key=%s attempt=%d", lock_key, attempt)
        logger.warning("[AI_LOCK WAIT] key=%s timed_out_after=%ds", lock_key, LOCK_MAX_WAIT)
        return None

    # ------------------------------------------------------------------
    # Cache Invalidation
    # ------------------------------------------------------------------

    async def invalidate_lesson(self, school_id: int, lesson_id: int) -> None:
        """
        Called when lesson content changes (video/PDF re-upload, chunk regeneration).
        Wipes all AI responses derived from this lesson's content.
        """
        pattern = AIKeys.lesson_pattern(school_id, lesson_id)
        await _delete_pattern(pattern)
        logger.info("[AI_CACHE INVALIDATE] school=%d lesson=%d", school_id, lesson_id)

    async def invalidate_course_lessons(self, school_id: int, course_id: int, lesson_ids: list[int]) -> None:
        """
        Called when a course is deleted or archived.
        Wipes AI caches for all provided lesson IDs.
        """
        for lesson_id in lesson_ids:
            await self.invalidate_lesson(school_id, lesson_id)


ai_cache = AICacheService()
