import json
import logging
from typing import Any, Dict
import redis.asyncio as redis
from app.core.config import settings

logger = logging.getLogger(__name__)

class EventPublisher:
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._redis = None

    async def get_redis(self):
        if self._redis is None:
            self._redis = await redis.from_url(self.redis_url, decode_responses=True)
        return self._redis

    async def publish_event(self, event_type: str, payload: Dict[str, Any]):
        import uuid
        try:
            r = await self.get_redis()
            message = {
                "event_id": str(uuid.uuid4()),
                "event_type": event_type,
                "payload": payload
            }
            # We use a single 'lms_events' channel for all event types in this phase
            await r.publish("lms_events", json.dumps(message))
            logger.info(f"Published {event_type} event to lms_events with ID {message['event_id']}")
        except Exception as e:
            logger.error(f"Failed to publish event {event_type}: {e}")

publisher = EventPublisher(settings.REDIS_URL)
