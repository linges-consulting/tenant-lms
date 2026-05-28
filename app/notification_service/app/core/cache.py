import functools
import json
import logging
from datetime import timedelta
from typing import Any, Callable, Optional, TypeVar, List

from redis.asyncio import Redis
from app.core.config import settings

logger = logging.getLogger(__name__)

# Global redis client
_redis: Optional[Redis] = None

async def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.REDIS_URL, decode_responses=False)
    return _redis

def cache_response(key_prefix: str, expire: int = settings.CACHE_TTL_SHORT, namespace: str = "notification", include_user_id: bool = False):
    """
    Decorator to cache FastAPI endpoint responses in Redis.
    expire: TTL in seconds (default 5 minutes)
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Try to build a unique key based on arguments
            cache_args = {k: v for k, v in kwargs.items() if not k.startswith("db") and k != "current_user" and k != "tenant_id"}
            
            tenant_id = kwargs.get("tenant_id", "default")
            user_id = ""
            if include_user_id and "current_user" in kwargs:
                user_obj = kwargs["current_user"]
                user_id = getattr(user_obj, "id", "")
            
            # generate unique key
            arg_str = json.dumps(cache_args, sort_keys=True)
            cache_key = f"{namespace}:{key_prefix}:{tenant_id}:{user_id}:{arg_str}"
            
            redis = await get_redis()
            
            # Try to get from cache
            try:
                cached_val = await redis.get(cache_key)
                if cached_val:
                    return json.loads(cached_val)
            except Exception as e:
                logger.error(f"Redis get error: {e}")

            # Call the original function
            result = await func(*args, **kwargs)

            # Store in cache
            try:
                if isinstance(result, list):
                    serializable_result = [r.model_dump(mode='json') if hasattr(r, 'model_dump') else r for r in result]
                elif hasattr(result, 'model_dump'):
                    serializable_result = result.model_dump(mode='json')
                else:
                    serializable_result = result

                await redis.setex(
                    cache_key,
                    expire,
                    json.dumps(serializable_result)
                )
            except Exception as e:
                logger.error(f"Redis set error: {e}")

            return result
        return wrapper
    return decorator

async def invalidate_cache(key_prefix: str, tenant_id: str, namespace: str = "notification", user_id: str = ""):
    """Invalidate all keys matching the prefix for a tenant (and optionally user)."""
    redis = await get_redis()
    user_part = f"{user_id}" if user_id else "*"
    pattern = f"{namespace}:{key_prefix}:{tenant_id}:{user_part}:*"
    keys = await redis.keys(pattern)
    if keys:
        await redis.delete(*keys)
        logger.info(f"Invalidated {len(keys)} keys with pattern {pattern}")
