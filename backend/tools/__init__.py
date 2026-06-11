import json
from typing import Any

from redis.asyncio import Redis

from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)


def get_redis_client() -> Redis:  # type: ignore[type-arg]
    return Redis.from_url(settings.REDIS_URL, decode_responses=True)


async def redis_get_cached(client: Redis | None, key: str) -> Any:  # type: ignore[type-arg]
    if client is None:
        return None
    try:
        raw = await client.get(key)
        return json.loads(raw) if raw else None
    except Exception as exc:
        logger.warning("redis_get_failed", key=key, error=str(exc))
        return None


async def redis_set_cached(client: Redis | None, key: str, value: Any, ttl: int) -> None:
    if client is None:
        return
    try:
        await client.set(key, json.dumps(value), ex=ttl)
    except Exception as exc:
        logger.warning("redis_set_failed", key=key, error=str(exc))
