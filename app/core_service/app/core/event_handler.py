import json
import asyncio
import logging
from typing import Any, Dict
import redis.asyncio as redis
from app.core.config import settings
from app.core.cache import invalidate_cache

logger = logging.getLogger(__name__)

async def handle_user_event(event_type: str, payload: Dict[str, Any]):
    """Handle user lifecycle events from auth_service."""
    user_id = payload.get("user_id")
    tenant_id = payload.get("tenant_id")
    
    logger.info(f"Processing {event_type} for user {user_id} in tenant {tenant_id}")
    
    if event_type in ["USER_DELETED", "USER_DEACTIVATED"]:
        # Invalidate core caches for this user
        # We invalidade training assignments and user stats
        await invalidate_cache("assigned_trainings", tenant_id, user_id=user_id)
        await invalidate_cache("user_stats", tenant_id, user_id=user_id)
        
        # If it's a global delete or broad removal, we might want to clear the whole tenant's user-related lists
        # but for now, specific user invalidation should be enough if the core service caches are user-scoped.
        if payload.get("global_delete") or not tenant_id:
             # If no tenant_id, we might need to find which tenants the user was in, 
             # but auth_service already emits events per tenant or with global_delete=True.
             pass

    elif event_type == "USER_UPDATED":
        # Name or other profile changes
        await invalidate_cache("user_stats", tenant_id, user_id=user_id)

async def consume_events():
    """Background task to consume events from Redis."""
    while True:
        try:
            r = await redis.from_url(settings.REDIS_URL, decode_responses=True)
            pubsub = r.pubsub()
            await pubsub.subscribe("lms_events")
            
            logger.info("Started event consumer for lms_events")
            
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        event_type = data.get("event_type")
                        payload = data.get("payload", {})
                        
                        if event_type in ["USER_DELETED", "USER_DEACTIVATED", "USER_REACTIVATED", "USER_UPDATED"]:
                            await handle_user_event(event_type, payload)
                    except Exception as e:
                        logger.error(f"Error processing event message: {e}")
        except Exception as e:
            logger.error(f"Event consumer connection error: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)
