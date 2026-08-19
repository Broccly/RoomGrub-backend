import json
import logging
import redis

STREAM_NAME = "rg:emails"

logger = logging.getLogger(__name__)


def publish_event(client: redis.Redis, event_type: str, payload: dict) -> None:
    try:
        client.xadd(STREAM_NAME, {"type": event_type, "payload": json.dumps(payload)})
    except Exception:
        logger.exception("Failed to publish event %r to stream %r", event_type, STREAM_NAME)

