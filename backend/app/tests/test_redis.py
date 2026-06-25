"""Tests for Redis client and cache service modules."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core import redis as redis_module
from app.core.redis import (
    CHANNEL_ALERTS,
    CHANNEL_DEVICE_UPDATES,
    close_redis,
    get_channel_name,
    get_pubsub,
    get_redis,
    init_redis,
    publish_message,
)
from app.services import cache_service
from app.services.cache_service import (
    _make_key,
    _tenant_pattern,
    get_cached,
    invalidate,
    invalidate_tenant,
    set_cached,
)


class TestRedisModule:
    """Tests for the Redis client lifecycle and helpers."""

    def test_get_redis_raises_when_not_initialized(self):
        """get_redis raises RuntimeError before init_redis is called."""
        # Ensure clean state
        redis_module._redis_client = None
        with pytest.raises(RuntimeError, match="not initialized"):
            get_redis()

    def test_get_pubsub_raises_when_not_initialized(self):
        """get_pubsub raises RuntimeError before init_redis is called."""
        redis_module._redis_client = None
        with pytest.raises(RuntimeError, match="not initialized"):
            get_pubsub()

    def test_get_channel_name_formats_correctly(self):
        """Channel names are formatted with tenant_id."""
        result = get_channel_name(CHANNEL_DEVICE_UPDATES, "tenant-123")
        assert result == "ws:device_updates:tenant-123"

        result = get_channel_name(CHANNEL_ALERTS, "abc")
        assert result == "ws:alerts:abc"

    @pytest.mark.asyncio
    async def test_init_redis_creates_client(self):
        """init_redis creates a working Redis client."""
        with patch("app.core.redis.ConnectionPool.from_url") as mock_pool_cls:
            mock_pool = MagicMock()
            mock_pool_cls.return_value = mock_pool

            with patch("app.core.redis.Redis") as mock_redis_cls:
                mock_client = AsyncMock()
                mock_client.ping = AsyncMock(return_value=True)
                mock_redis_cls.return_value = mock_client

                client = await init_redis()

                assert client is mock_client
                mock_client.ping.assert_awaited_once()
                mock_pool_cls.assert_called_once()

        # Cleanup
        redis_module._redis_client = None
        redis_module._redis_pool = None

    @pytest.mark.asyncio
    async def test_close_redis_cleans_up(self):
        """close_redis closes client and pool."""
        mock_client = AsyncMock()
        mock_pool = AsyncMock()
        redis_module._redis_client = mock_client
        redis_module._redis_pool = mock_pool

        await close_redis()

        mock_client.aclose.assert_awaited_once()
        mock_pool.aclose.assert_awaited_once()
        assert redis_module._redis_client is None
        assert redis_module._redis_pool is None

    @pytest.mark.asyncio
    async def test_close_redis_handles_none_state(self):
        """close_redis is safe to call when already closed."""
        redis_module._redis_client = None
        redis_module._redis_pool = None

        # Should not raise
        await close_redis()

    @pytest.mark.asyncio
    async def test_publish_message(self):
        """publish_message publishes to the correct channel."""
        mock_client = AsyncMock()
        mock_client.publish = AsyncMock(return_value=2)
        redis_module._redis_client = mock_client

        result = await publish_message(CHANNEL_DEVICE_UPDATES, "t1", '{"event":"test"}')

        assert result == 2
        mock_client.publish.assert_awaited_once_with(
            "ws:device_updates:t1", '{"event":"test"}'
        )

        # Cleanup
        redis_module._redis_client = None

    def test_get_redis_returns_client_when_initialized(self):
        """get_redis returns the client after initialization."""
        mock_client = MagicMock()
        redis_module._redis_client = mock_client

        assert get_redis() is mock_client

        # Cleanup
        redis_module._redis_client = None


class TestCacheService:
    """Tests for the tenant-scoped cache service."""

    def test_make_key_format(self):
        """Cache keys follow the expected format."""
        assert _make_key("tenant-1", "devices") == "cache:tenant-1:devices"
        assert _make_key("abc", "rules:active") == "cache:abc:rules:active"

    def test_tenant_pattern_format(self):
        """Tenant pattern uses glob wildcard."""
        assert _tenant_pattern("tenant-1") == "cache:tenant-1:*"

    @pytest.mark.asyncio
    async def test_get_cached_returns_none_on_miss(self):
        """get_cached returns None when key doesn't exist."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=None)

        with patch.object(cache_service, "get_redis", return_value=mock_client):
            result = await get_cached("t1", "missing-key")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_cached_deserializes_json(self):
        """get_cached deserializes JSON values."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value='{"name": "device1", "active": true}')

        with patch.object(cache_service, "get_redis", return_value=mock_client):
            result = await get_cached("t1", "device:abc")

        assert result == {"name": "device1", "active": True}

    @pytest.mark.asyncio
    async def test_get_cached_returns_raw_on_invalid_json(self):
        """get_cached returns raw string if JSON decode fails."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value="not-json")

        with patch.object(cache_service, "get_redis", return_value=mock_client):
            result = await get_cached("t1", "raw-key")

        assert result == "not-json"

    @pytest.mark.asyncio
    async def test_set_cached_uses_default_ttl(self):
        """set_cached uses the configured default TTL (10s)."""
        mock_client = AsyncMock()
        mock_client.set = AsyncMock()

        with patch.object(cache_service, "get_redis", return_value=mock_client):
            await set_cached("t1", "devices", [{"mac": "AA:BB:CC:DD:EE:FF"}])

        mock_client.set.assert_awaited_once_with(
            "cache:t1:devices",
            '[{"mac": "AA:BB:CC:DD:EE:FF"}]',
            ex=10,
        )

    @pytest.mark.asyncio
    async def test_set_cached_uses_custom_ttl(self):
        """set_cached respects a custom TTL."""
        mock_client = AsyncMock()
        mock_client.set = AsyncMock()

        with patch.object(cache_service, "get_redis", return_value=mock_client):
            await set_cached("t1", "session", {"user": "admin"}, ttl=1800)

        mock_client.set.assert_awaited_once_with(
            "cache:t1:session",
            '{"user": "admin"}',
            ex=1800,
        )

    @pytest.mark.asyncio
    async def test_invalidate_returns_true_on_delete(self):
        """invalidate returns True when key existed."""
        mock_client = AsyncMock()
        mock_client.delete = AsyncMock(return_value=1)

        with patch.object(cache_service, "get_redis", return_value=mock_client):
            result = await invalidate("t1", "devices")

        assert result is True
        mock_client.delete.assert_awaited_once_with("cache:t1:devices")

    @pytest.mark.asyncio
    async def test_invalidate_returns_false_on_miss(self):
        """invalidate returns False when key didn't exist."""
        mock_client = AsyncMock()
        mock_client.delete = AsyncMock(return_value=0)

        with patch.object(cache_service, "get_redis", return_value=mock_client):
            result = await invalidate("t1", "nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_invalidate_tenant_deletes_all_keys(self):
        """invalidate_tenant removes all cache keys for a tenant."""
        mock_client = AsyncMock()
        mock_client.delete = AsyncMock(return_value=1)

        # Simulate scan_iter yielding keys
        async def mock_scan_iter(match=None, count=None):
            keys = ["cache:t1:devices", "cache:t1:rules", "cache:t1:status"]
            for k in keys:
                yield k

        mock_client.scan_iter = mock_scan_iter

        with patch.object(cache_service, "get_redis", return_value=mock_client):
            deleted = await invalidate_tenant("t1")

        assert deleted == 3
        assert mock_client.delete.await_count == 3
