"""Redis client for AlphaStack – caching, pub/sub, and stream helpers."""

from __future__ import annotations

import json
from typing import Any

from redis.asyncio import Redis

from alphastack.core.config import get_settings
from alphastack.utils.logger import get_logger

logger = get_logger(__name__)

_client: Redis | None = None


def get_redis() -> Redis:
    """Return (and lazily create) the singleton Redis client."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = Redis.from_url(
            settings.redis.url,
            max_connections=settings.redis.pool_size,
            decode_responses=True,
        )
        logger.info("redis.client_created", host=settings.redis.host, port=settings.redis.port)
    return _client


async def close_redis() -> None:
    """Close the Redis connection pool."""
    global _client
    if _client:
        await _client.aclose()
        _client = None
        logger.info("redis.client_closed")


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

async def cache_get(key: str) -> Any | None:
    """Get a JSON-serialised value from cache. Returns None on miss."""
    client = get_redis()
    raw = await client.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


async def cache_set(key: str, value: Any, ttl: int | None = None) -> None:
    """Set a JSON-serialisable value in cache with optional TTL (seconds)."""
    client = get_redis()
    payload = json.dumps(value, default=str)
    if ttl is None:
        ttl = get_settings().redis.cache_default_ttl
    await client.set(key, payload, ex=ttl)


async def cache_delete(key: str) -> None:
    """Delete a key from cache."""
    client = get_redis()
    await client.delete(key)


async def cache_exists(key: str) -> bool:
    """Check if a key exists in cache."""
    client = get_redis()
    return bool(await client.exists(key))


# ---------------------------------------------------------------------------
# Pub/Sub helpers
# ---------------------------------------------------------------------------

async def publish(channel: str, message: dict[str, Any]) -> int:
    """Publish a JSON message to a Redis pub/sub channel. Returns receiver count."""
    client = get_redis()
    payload = json.dumps(message, default=str)
    count = await client.publish(channel, payload)
    logger.debug("redis.published", channel=channel, receivers=count)
    return count


async def subscribe(*channels: str):
    """Subscribe to one or more channels. Returns a PubSub object.

    Usage::

        pubsub = await subscribe("alerts", "signals")
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
    """
    client = get_redis()
    pubsub = client.pubsub()
    await pubsub.subscribe(*channels)
    logger.info("redis.subscribed", channels=list(channels))
    return pubsub


# ---------------------------------------------------------------------------
# Stream helpers (thin wrappers around the raw Redis client)
# ---------------------------------------------------------------------------

async def stream_publish(stream: str, data: dict[str, Any], max_len: int = 100_000) -> str:
    """Add a message to a Redis Stream. Returns the entry ID."""
    client = get_redis()
    entry_id = await client.xadd(stream, {"data": json.dumps(data, default=str)}, maxlen=max_len, approximate=True)
    logger.debug("redis.stream_published", stream=stream, entry_id=entry_id)
    return entry_id


async def stream_read(
    streams: dict[str, str],
    count: int = 10,
    block_ms: int = 5000,
) -> list:
    """Read from Redis Streams. ``streams`` maps stream names to IDs (or '>')."""
    client = get_redis()
    results = await client.xread(streams=streams, count=count, block=block_ms)
    return results or []
