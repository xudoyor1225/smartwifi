"""Tenant-scoped cache service using Redis.

Provides utility functions for caching data with tenant isolation.
All cache keys are prefixed with the tenant ID to ensure data separation.
Default TTL is 10 seconds (configurable via settings.redis_cache_ttl).
"""

import json
from typing import Any

from app.core.config import get_settings
from app.core.redis import get_redis


def _make_key(tenant_id: str, key: str) -> str:
    """Build a tenant-scoped cache key.

    Args:
        tenant_id: The tenant identifier.
        key: The logical cache key.

    Returns:
        A namespaced Redis key in the format 'cache:{tenant_id}:{key}'.
    """
    return f"cache:{tenant_id}:{key}"


def _tenant_pattern(tenant_id: str) -> str:
    """Build a glob pattern matching all cache keys for a tenant.

    Args:
        tenant_id: The tenant identifier.

    Returns:
        A Redis key pattern for SCAN operations.
    """
    return f"cache:{tenant_id}:*"


async def get_cached(tenant_id: str, key: str) -> Any | None:
    """Retrieve a cached value for a tenant.

    Args:
        tenant_id: The tenant identifier.
        key: The logical cache key.

    Returns:
        The deserialized cached value, or None if not found or expired.
    """
    client = get_redis()
    raw = await client.get(_make_key(tenant_id, key))
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


async def set_cached(
    tenant_id: str, key: str, value: Any, ttl: int | None = None
) -> None:
    """Store a value in the cache with a TTL.

    Args:
        tenant_id: The tenant identifier.
        key: The logical cache key.
        value: The value to cache (will be JSON-serialized).
        ttl: Time-to-live in seconds. Defaults to settings.redis_cache_ttl (10s).
    """
    if ttl is None:
        ttl = get_settings().redis_cache_ttl

    client = get_redis()
    serialized = json.dumps(value)
    await client.set(_make_key(tenant_id, key), serialized, ex=ttl)


async def invalidate(tenant_id: str, key: str) -> bool:
    """Delete a single cache entry for a tenant.

    Args:
        tenant_id: The tenant identifier.
        key: The logical cache key to invalidate.

    Returns:
        True if the key existed and was deleted, False otherwise.
    """
    client = get_redis()
    result = await client.delete(_make_key(tenant_id, key))
    return result > 0


async def invalidate_tenant(tenant_id: str) -> int:
    """Delete all cache entries for a tenant.

    Uses SCAN to find matching keys in a non-blocking manner,
    then deletes them in batches.

    Args:
        tenant_id: The tenant identifier.

    Returns:
        The number of keys deleted.
    """
    client = get_redis()
    pattern = _tenant_pattern(tenant_id)
    deleted = 0

    async for key in client.scan_iter(match=pattern, count=100):
        await client.delete(key)
        deleted += 1

    return deleted
