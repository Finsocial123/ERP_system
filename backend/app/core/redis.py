"""
Central Redis client for School ERP.

Single async connection pool shared across all workers.
Configure via REDIS_URL in .env (defaults to localhost for local dev).
If Redis is unavailable, all cache operations degrade gracefully — the
application continues to work, just without caching.
"""

from __future__ import annotations

import logging
import os

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Single pool shared by the whole process.
_redis_client: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis | None:
    """Return the shared Redis client, or None if not yet initialised."""
    return _redis_client


async def init_redis() -> None:
    """Create the connection pool.  Call once at application startup."""
    global _redis_client
    try:
        client = aioredis.from_url(
            REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
            retry_on_timeout=False,
            max_connections=20,
        )
        await client.ping()
        _redis_client = client
        logger.info("Redis connected: %s", REDIS_URL)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis unavailable — caching disabled. %s", exc)
        _redis_client = None


async def close_redis() -> None:
    """Close the connection pool.  Call once at application shutdown."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
        logger.info("Redis connection closed.")
