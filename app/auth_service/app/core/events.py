import json
import uuid
import logging
import redis.asyncio as redis
from datetime import datetime
from typing import Any, Dict, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

class EventPublisher:
    def __init__(self, redis_url: str = settings.REDIS_URL):
        self._redis_url = redis_url
        self._redis = None

    async def connect(self):
        if not self._redis:
            self._redis = await redis.from_url(self._redis_url, decode_responses=True)
            logger.info(f"Connected to Redis for event publishing: {self._redis_url}")

    async def close(self):
        if self._redis:
            await self._redis.close()
            self._redis = None

    async def publish(self, event_type: str, payload: Dict[str, Any], event_id: Optional[str] = None):
        """
        Publish an event to the 'lms_events' channel.
        """
        if not self._redis:
            await self.connect()

        event_id = event_id or str(uuid.uuid4())
        message = {
            "event_id": event_id,
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "payload": payload
        }

        try:
            await self._redis.publish("lms_events", json.dumps(message))
            logger.info(f"Published event {event_type} (ID: {event_id}) to lms_events")
        except Exception as e:
            logger.error(f"Failed to publish event {event_type}: {e}")

# Global instance
event_publisher = EventPublisher()
