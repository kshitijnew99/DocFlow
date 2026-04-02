import redis
from app.core.config import get_settings

settings = get_settings()

_redis_client = None


def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


def get_pubsub_channel(job_id: str) -> str:
    return f"{settings.REDIS_PUBSUB_CHANNEL_PREFIX}{job_id}"


def publish_event(job_id: str, event: dict) -> None:
    """Publish a progress event to Redis Pub/Sub."""
    import json
    client = get_redis()
    channel = get_pubsub_channel(job_id)
    client.publish(channel, json.dumps(event))


def set_job_status(job_id: str, status_data: dict, ttl: int = 3600) -> None:
    """Cache job status in Redis for fast reads."""
    import json
    client = get_redis()
    key = f"docflow:status:{job_id}"
    client.setex(key, ttl, json.dumps(status_data))


def get_job_status(job_id: str) -> dict | None:
    """Read cached job status from Redis."""
    import json
    client = get_redis()
    key = f"docflow:status:{job_id}"
    data = client.get(key)
    return json.loads(data) if data else None
