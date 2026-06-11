from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from app.core.redis import get_redis

logger = logging.getLogger(__name__)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


async def _get(key: str) -> Any | None:
    redis = get_redis()
    if redis is None:
        return None
    try:
        raw = await redis.get(key)
        return json.loads(raw) if raw is not None else None
    except Exception as exc:
        logger.debug("Cache GET failed for %s: %s", key, exc)
        return None


async def _set(key: str, value: Any, ttl: int) -> None:
    redis = get_redis()
    if redis is None:
        return
    try:
        await redis.setex(key, ttl, json.dumps(value, default=str))
    except Exception as exc:
        logger.debug("Cache SET failed for %s: %s", key, exc)


async def _delete(*keys: str) -> None:
    redis = get_redis()
    if redis is None:
        return
    try:
        await redis.delete(*keys)
    except Exception as exc:
        logger.debug("Cache DELETE failed: %s", exc)


async def _delete_pattern(pattern: str) -> None:
    redis = get_redis()
    if redis is None:
        return
    try:
        cursor = 0
        while True:
            cursor, keys = await redis.scan(cursor, match=pattern, count=100)
            if keys:
                await redis.delete(*keys)
            if cursor == 0:
                break
    except Exception as exc:
        logger.debug("Cache DELETE pattern %s failed: %s", pattern, exc)


class _Keys:
    @staticmethod
    def school_branding(school_id: int) -> str:
        return f"school_branding:{school_id}"

    @staticmethod
    def school_branding_by_code(school_code: str) -> str:
        return f"school_branding_code:{school_code}"

    @staticmethod
    def school(school_id: int) -> str:
        return f"school:{school_id}"

    @staticmethod
    def current_session(school_id: int) -> str:
        return f"current_session:{school_id}"

    @staticmethod
    def dashboard_admin(school_id: int, session_id: int) -> str:
        return f"dashboard:admin:{school_id}:{session_id}"

    @staticmethod
    def dashboard_teacher(school_id: int, user_id: int, session_id: int) -> str:
        return f"dashboard:teacher:{school_id}:{user_id}:{session_id}"

    @staticmethod
    def dashboard_student(school_id: int, user_id: int, session_id: int) -> str:
        return f"dashboard:student:{school_id}:{user_id}:{session_id}"

    @staticmethod
    def dashboard_parent(school_id: int, user_id: int, session_id: int) -> str:
        return f"dashboard:parent:{school_id}:{user_id}:{session_id}"

    @staticmethod
    def user_profile(user_id: int) -> str:
        return f"user_profile:{user_id}"

    @staticmethod
    def teacher_profile(school_id: int, user_id: int) -> str:
        return f"teacher_profile:{school_id}:{user_id}"

    @staticmethod
    def student_profile(school_id: int, user_id: int) -> str:
        return f"student_profile:{school_id}:{user_id}"

    @staticmethod
    def course_meta(school_id: int) -> str:
        return f"course_meta:{school_id}"

    @staticmethod
    def embedding(text: str) -> str:
        return f"embedding:{_sha256(text)}"


CacheKeys = _Keys()


class CacheService:
    TTL_BRANDING = 900
    TTL_SCHOOL = 600
    TTL_SESSION = 600
    TTL_DASHBOARD = 300
    TTL_DASHBOARD_ROLE = 180
    TTL_USER_PROFILE = 300
    TTL_TEACHER_PROFILE = 300
    TTL_STUDENT_PROFILE = 300
    TTL_COURSE_META = 300
    TTL_EMBEDDING = 86400

    # School branding
    async def get_branding(self, school_id: int) -> dict | None:
        return await _get(CacheKeys.school_branding(school_id))

    async def set_branding(self, school_id: int, data: dict) -> None:
        await _set(CacheKeys.school_branding(school_id), data, self.TTL_BRANDING)

    async def get_branding_by_code(self, school_code: str) -> dict | None:
        return await _get(CacheKeys.school_branding_by_code(school_code))

    async def set_branding_by_code(self, school_code: str, data: dict) -> None:
        await _set(CacheKeys.school_branding_by_code(school_code), data, self.TTL_BRANDING)

    async def invalidate_branding(self, school_id: int, school_code: str | None = None) -> None:
        keys = [CacheKeys.school_branding(school_id)]
        if school_code:
            keys.append(CacheKeys.school_branding_by_code(school_code))
        await _delete(*keys)

    # School record
    async def get_school(self, school_id: int) -> dict | None:
        return await _get(CacheKeys.school(school_id))

    async def set_school(self, school_id: int, data: dict) -> None:
        await _set(CacheKeys.school(school_id), data, self.TTL_SCHOOL)

    async def invalidate_school(self, school_id: int) -> None:
        await _delete(CacheKeys.school(school_id))

    # Current academic session
    async def get_current_session(self, school_id: int) -> dict | None:
        return await _get(CacheKeys.current_session(school_id))

    async def set_current_session(self, school_id: int, data: dict | None) -> None:
        await _set(CacheKeys.current_session(school_id), data, self.TTL_SESSION)

    async def invalidate_session(self, school_id: int) -> None:
        await _delete(CacheKeys.current_session(school_id))
        await self.invalidate_all_dashboards(school_id)

    # Dashboard
    async def get_admin_dashboard(self, school_id: int, session_id: int) -> dict | None:
        return await _get(CacheKeys.dashboard_admin(school_id, session_id))

    async def set_admin_dashboard(self, school_id: int, session_id: int, data: dict) -> None:
        await _set(CacheKeys.dashboard_admin(school_id, session_id), data, self.TTL_DASHBOARD)

    async def get_teacher_dashboard(self, school_id: int, user_id: int, session_id: int) -> dict | None:
        return await _get(CacheKeys.dashboard_teacher(school_id, user_id, session_id))

    async def set_teacher_dashboard(self, school_id: int, user_id: int, session_id: int, data: dict) -> None:
        await _set(CacheKeys.dashboard_teacher(school_id, user_id, session_id), data, self.TTL_DASHBOARD_ROLE)

    async def get_student_dashboard(self, school_id: int, user_id: int, session_id: int) -> dict | None:
        return await _get(CacheKeys.dashboard_student(school_id, user_id, session_id))

    async def set_student_dashboard(self, school_id: int, user_id: int, session_id: int, data: dict) -> None:
        await _set(CacheKeys.dashboard_student(school_id, user_id, session_id), data, self.TTL_DASHBOARD_ROLE)

    async def get_parent_dashboard(self, school_id: int, user_id: int, session_id: int) -> dict | None:
        return await _get(CacheKeys.dashboard_parent(school_id, user_id, session_id))

    async def set_parent_dashboard(self, school_id: int, user_id: int, session_id: int, data: dict) -> None:
        await _set(CacheKeys.dashboard_parent(school_id, user_id, session_id), data, self.TTL_DASHBOARD_ROLE)

    async def invalidate_admin_dashboard(self, school_id: int, session_id: int) -> None:
        await _delete(CacheKeys.dashboard_admin(school_id, session_id))

    async def invalidate_teacher_dashboard(self, school_id: int, user_id: int, session_id: int) -> None:
        await _delete(CacheKeys.dashboard_teacher(school_id, user_id, session_id))

    async def invalidate_student_dashboard(self, school_id: int, user_id: int, session_id: int) -> None:
        await _delete(CacheKeys.dashboard_student(school_id, user_id, session_id))

    async def invalidate_parent_dashboard(self, school_id: int, user_id: int, session_id: int) -> None:
        await _delete(CacheKeys.dashboard_parent(school_id, user_id, session_id))

    async def invalidate_all_dashboards(self, school_id: int) -> None:
        """
        Wipe all dashboard caches for a school.
        Uses SCAN-based pattern delete — no session_id needed.
        BUG FIX: original code called CacheKeys.dashboard_admin(school_id)
        without session_id, which crashes because the key builder requires
        two arguments. Replaced with pattern-only deletion.
        """
        await _delete_pattern(f"dashboard:*:{school_id}:*")

    # User / teacher / student profiles
    async def get_user_profile(self, user_id: int) -> dict | None:
        return await _get(CacheKeys.user_profile(user_id))

    async def set_user_profile(self, user_id: int, data: dict) -> None:
        await _set(CacheKeys.user_profile(user_id), data, self.TTL_USER_PROFILE)

    async def invalidate_user_profile(self, user_id: int) -> None:
        await _delete(CacheKeys.user_profile(user_id))

    async def get_teacher_profile(self, school_id: int, user_id: int) -> dict | None:
        return await _get(CacheKeys.teacher_profile(school_id, user_id))

    async def set_teacher_profile(self, school_id: int, user_id: int, data: dict) -> None:
        await _set(CacheKeys.teacher_profile(school_id, user_id), data, self.TTL_TEACHER_PROFILE)

    async def invalidate_teacher_profile(self, school_id: int, user_id: int) -> None:
        await _delete(CacheKeys.teacher_profile(school_id, user_id))

    async def get_student_profile(self, school_id: int, user_id: int) -> dict | None:
        return await _get(CacheKeys.student_profile(school_id, user_id))

    async def set_student_profile(self, school_id: int, user_id: int, data: dict) -> None:
        await _set(CacheKeys.student_profile(school_id, user_id), data, self.TTL_STUDENT_PROFILE)

    async def invalidate_student_profile(self, school_id: int, user_id: int) -> None:
        await _delete(CacheKeys.student_profile(school_id, user_id))

    # Course meta
    async def get_course_meta(self, school_id: int) -> dict | None:
        return await _get(CacheKeys.course_meta(school_id))

    async def set_course_meta(self, school_id: int, data: dict) -> None:
        await _set(CacheKeys.course_meta(school_id), data, self.TTL_COURSE_META)

    async def invalidate_course_meta(self, school_id: int) -> None:
        await _delete(CacheKeys.course_meta(school_id))

    # Embedding cache
    async def get_embedding(self, text: str) -> list[float] | None:
        return await _get(CacheKeys.embedding(text))

    async def set_embedding(self, text: str, embedding: list[float]) -> None:
        await _set(CacheKeys.embedding(text), embedding, self.TTL_EMBEDDING)


cache = CacheService()
