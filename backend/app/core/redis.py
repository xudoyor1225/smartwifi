"""Redis client configuration and lifecycle management.

Provides a singleton async Redis client with connection pooling for use
across the application: sessions, caching, and pub/sub messaging.
"""

import redis.asyncio as redis
from redis.asyncio import ConnectionPool, Redis

from app.core.config import get_settings

# Module-level references managed by lifecycle functions
_redis_pool: ConnectionPool | None = None
_redis_client: Redis | None = None


async def init_redis() -> Redis:
    """Initialize the Redis connection pool and client.

    Should be called once during application startup. Creates a connection
    pool that is shared across all Redis operations.

    Returns:
        The initialized async Redis client.
    """
    global _redis_pool, _redis_client

    settings = get_settings()
    _redis_pool = ConnectionPool.from_url(
        settings.redis_url,
        decode_responses=True,
        max_connections=50,
        retry_on_timeout=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    )
    _redis_client = Redis(connection_pool=_redis_pool)
    # Verify connectivity
    await _redis_client.ping()
    return _redis_client


async def close_redis() -> None:
    """Close the Redis client and connection pool.

    Should be called during application shutdown to release resources.
    """
    global _redis_pool, _redis_client

    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
    if _redis_pool is not None:
        await _redis_pool.aclose()
        _redis_pool = None


def get_redis() -> Redis:
    """Get the current Redis client instance.

    Raises:
        RuntimeError: If Redis has not been initialized via init_redis().

    Returns:
        The async Redis client.
    """
    if _redis_client is None:
        raise RuntimeError(
            "Redis client is not initialized. Call init_redis() during app startup."
        )
    return _redis_client


def get_pubsub() -> redis.client.PubSub:
    """Get a new Pub/Sub instance from the current Redis client.

    Used for cross-instance WebSocket message broadcasting.

    Raises:
        RuntimeError: If Redis has not been initialized.

    Returns:
        A PubSub instance for subscribing/publishing messages.
    """
    client = get_redis()
    return client.pubsub()


# Channel name constants for pub/sub
CHANNEL_DEVICE_UPDATES = "ws:device_updates:{tenant_id}"
CHANNEL_TRAFFIC_STATS = "ws:traffic_stats:{tenant_id}"
CHANNEL_ALERTS = "ws:alerts:{tenant_id}"
CHANNEL_BLOCKING_STATUS = "ws:blocking_status:{tenant_id}"
CHANNEL_ROUTER_STATUS = "ws:router_status:{tenant_id}"


def get_channel_name(channel_template: str, tenant_id: str) -> str:
    """Format a pub/sub channel name with the tenant ID.

    Args:
        channel_template: Channel template string with {tenant_id} placeholder.
        tenant_id: The tenant identifier.

    Returns:
        Formatted channel name scoped to the tenant.
    """
    return channel_template.format(tenant_id=tenant_id)


async def publish_message(channel_template: str, tenant_id: str, message: str) -> int:
    """Publish a message to a tenant-scoped pub/sub channel.

    Used for broadcasting WebSocket events across multiple backend instances.

    Args:
        channel_template: Channel template with {tenant_id} placeholder.
        tenant_id: The tenant identifier.
        message: JSON-serialized message to publish.

    Returns:
        Number of subscribers that received the message.
    """
    client = get_redis()
    channel = get_channel_name(channel_template, tenant_id)
    return await client.publish(channel, message)
