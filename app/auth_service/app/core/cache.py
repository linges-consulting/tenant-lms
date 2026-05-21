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

def cache_response(key_prefix: str, expire: int = 300, namespace: str = "auth", include_user_id: bool = False):
    """
    Decorator to cache FastAPI endpoint responses in Redis.
    expire: TTL in seconds (default 5 minutes)
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Try to build a unique key based on arguments
            # Filter out common dependency-injected objects that are not directly JSON serializable
            cache_args = {
                k: v for k, v in kwargs.items() 
                if not k.startswith("db") 
                and k not in ["current_user", "current_manager", "current_sysadmin", "current_employee", "tenant_id", "session"]
                and not hasattr(v, "__dict__") # Basic check for complex objects
                and not isinstance(v, (list, dict)) # We only want primitives for the key hash for now
            }
            
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
                    # logger.info(f"Cache hit: {cache_key}")
                    return json.loads(cached_val)
            except Exception as e:
                logger.error(f"Redis get error: {e}")

            # Call the original function
            result = await func(*args, **kwargs)

            # Store in cache
            try:
                # In Pydantic V2, model_dump(mode='json') includes computed fields by default
                # provided they are properly decorated with @computed_field.
                # If result is a list of models, we dump each one.
                if isinstance(result, list):
                    serializable_result = [r.model_dump(mode='json') if hasattr(r, 'model_dump') else r for r in result]
                elif hasattr(result, 'model_dump'):
                    serializable_result = result.model_dump(mode='json')
                else:
                    serializable_result = result

                # Log if role is missing in first element for debugging
                if isinstance(serializable_result, list) and len(serializable_result) > 0:
                    first = serializable_result[0]
                    if isinstance(first, dict) and "members" in first:
                        m0 = first["members"][0] if first["members"] else {}
                        if "role" not in m0:
                            logger.warning(f"Cache serialization warning: 'role' field missing in membership for user {first.get('id')}")

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

async def invalidate_cache(key_prefix: str, tenant_id: str, namespace: str = "auth", user_id: str = ""):
    """Invalidate all keys matching the prefix for a tenant (and optionally user)."""
    try:
        redis = await get_redis()
        # Ensure tenant_id is stringified
        tid = str(tenant_id) if tenant_id else "*"
        user_part = str(user_id) if user_id else "*"
        
        # Use a more flexible pattern that matches the segments more reliably.
        # Key format: namespace:key_prefix:tenant_id:user_id:arg_str
        # If user_id is provided, match that specific branch.
        # If not, match all across the tenant.
        pattern = f"{namespace}:{key_prefix}:{tid}:{user_part}:*"
        
        keys = await redis.keys(pattern)
        if keys:
            await redis.delete(*keys)
            logger.info(f"Invalidated {len(keys)} keys with pattern: {pattern}")
        else:
            # Fallback to even broader pattern if segments mismatch
            # This handles cases where user_id part might be empty in different ways
            broad_pattern = f"{namespace}:{key_prefix}:{tid}:*"
            keys = await redis.keys(broad_pattern)
            if keys:
                await redis.delete(*keys)
                logger.info(f"Invalidated {len(keys)} keys with broad pattern: {broad_pattern}")
            else:
                logger.debug(f"No keys found to invalidate with pattern: {pattern}")
    except Exception as e:
        logger.error(f"Error invalidating cache: {e}")

