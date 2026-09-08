from functools import lru_cache

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings


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


def close_redis_client() -> None:
    """Release the shared client, primarily for controlled shutdown and tests."""
    client = get_redis_client()
    client.close()
    get_redis_client.cache_clear()