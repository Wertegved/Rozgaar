import logging
from functools import lru_cache

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_redis_client() -> Redis:
    """Return the process-wide lazy Redis client configured for this app."""
    return Redis.from_url(get_settings().redis_url, decode_responses=True)


def is_redis_available() -> bool:
    """Check Redis availability without making it a startup requirement."""
    try:
        return bool(get_redis_client().ping())
    except (RedisError, OSError):
        return False


def consume_rate_limit(key: str, limit: int, window_seconds: int, *, fail_closed: bool = True) -> bool:
    try:
        client = get_redis_client()
        count = client.incr(key)
        if count == 1:
            client.expire(key, window_seconds)
        return count <= limit
    except (RedisError, OSError):
        logger.exception("Redis rate-limit check failed for key %s", key)
        return not fail_closed


def close_redis_client() -> None:
    """Release the shared client, primarily for controlled shutdown and tests."""
    client = get_redis_client()
    client.close()
    get_redis_client.cache_clear()