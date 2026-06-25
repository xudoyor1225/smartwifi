"""Unit tests for the RouterBridge service.

Tests connection pooling, timeouts, command execution, and error handling.
"""

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest

from app.services.router_bridge import (
    ConnectionPoolExhausted,
    ConnectionStatus,
    FirewallRuleParams,
    QueueRuleParams,
    RouterBridge,
    RouterBridgeError,
    RouterCommandError,
    RouterConfig,
    RouterConnectionError,
    TenantConnectionPool,
)


# --- Test Settings Mock ---


@dataclass
class MockSettings:
    """Mock settings for testing."""

    router_connection_timeout: int = 5
    router_request_timeout: int = 10
    router_max_connections_per_tenant: int = 5
    router_connection_queue_timeout: int = 10


# --- Mock MikroTik Client ---


class MockMikroTikClient:
    """Mock MikroTik client for testing."""

    def __init__(self) -> None:
        self.connected = False
        self.connect_delay: float = 0
        self.execute_delay: float = 0
        self.connect_error: Exception | None = None
        self.execute_error: Exception | None = None
        self.execute_result: list[dict[str, Any]] = []
        self._host: str | None = None
        self._port: int | None = None

    def connect(self, host: str, port: int, username: str, password: str) -> None:
        if self.connect_error:
            raise self.connect_error
        self.connected = True
        self._host = host
        self._port = port

    def disconnect(self) -> None:
        self.connected = False

    def execute(self, command: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if self.execute_error:
            raise self.execute_error
        return self.execute_result


class MockMikroTikClientFactory:
    """Factory that creates pre-configured mock clients."""

    def __init__(self) -> None:
        self.last_client: MockMikroTikClient | None = None
        self.connect_delay: float = 0
        self.execute_delay: float = 0
        self.connect_error: Exception | None = None
        self.execute_error: Exception | None = None
        self.execute_result: list[dict[str, Any]] = []

    def __call__(self) -> MockMikroTikClient:
        client = MockMikroTikClient()
        client.connect_delay = self.connect_delay
        client.execute_delay = self.execute_delay
        client.connect_error = self.connect_error
        client.execute_error = self.execute_error
        client.execute_result = self.execute_result
        self.last_client = client
        return client


# --- Fixtures ---


@pytest.fixture
def mock_settings() -> MockSettings:
    """Create mock settings with default values."""
    return MockSettings()


@pytest.fixture
def mock_client_factory() -> MockMikroTikClientFactory:
    """Create a mock client factory."""
    return MockMikroTikClientFactory()


@pytest.fixture
def router_bridge(mock_settings, mock_client_factory) -> RouterBridge:
    """Create a RouterBridge with mock dependencies."""
    bridge = RouterBridge(
        client_factory=mock_client_factory,
        settings=mock_settings,
    )
    return bridge


@pytest.fixture
def sample_router_config() -> RouterConfig:
    """Create a sample router configuration."""
    return RouterConfig(
        host="192.168.1.1",
        port=8728,
        username="admin",
        password="secret",
    )


@pytest.fixture
def registered_bridge(router_bridge, sample_router_config) -> RouterBridge:
    """Create a RouterBridge with a registered router config."""
    router_bridge.register_router("tenant-1", sample_router_config)
    return router_bridge


# --- TenantConnectionPool Tests ---


class TestTenantConnectionPool:
    """Tests for the TenantConnectionPool class."""

    @pytest.mark.asyncio
    async def test_acquire_and_release(self):
        """Test basic acquire and release of connection slots."""
        pool = TenantConnectionPool(
            tenant_id="test", max_connections=5, queue_timeout=10
        )
        assert pool.active_connections == 0
        assert pool.available_connections == 5

        await pool.acquire()
        assert pool.active_connections == 1
        assert pool.available_connections == 4

        pool.release()
        assert pool.active_connections == 0
        assert pool.available_connections == 5

    @pytest.mark.asyncio
    async def test_max_connections_enforced(self):
        """Test that max connections limit is enforced."""
        pool = TenantConnectionPool(
            tenant_id="test", max_connections=2, queue_timeout=0.1
        )

        # Acquire all slots
        await pool.acquire()
        await pool.acquire()
        assert pool.active_connections == 2
        assert pool.available_connections == 0

        # Next acquire should timeout
        with pytest.raises(ConnectionPoolExhausted) as exc_info:
            await pool.acquire()

        assert exc_info.value.tenant_id == "test"
        assert exc_info.value.timeout == 0.1

    @pytest.mark.asyncio
    async def test_queue_waits_for_release(self):
        """Test that queued requests wait for a slot to be released."""
        pool = TenantConnectionPool(
            tenant_id="test", max_connections=1, queue_timeout=2.0
        )

        await pool.acquire()

        # Schedule a release after a short delay
        async def delayed_release():
            await asyncio.sleep(0.1)
            pool.release()

        asyncio.create_task(delayed_release())

        # This should succeed after the release
        await pool.acquire()
        assert pool.active_connections == 1

    @pytest.mark.asyncio
    async def test_release_does_not_go_below_zero(self):
        """Test that releasing without acquiring doesn't go negative."""
        pool = TenantConnectionPool(
            tenant_id="test", max_connections=5, queue_timeout=10
        )
        pool.release()
        assert pool.active_connections == 0


# --- RouterBridge Configuration Tests ---


class TestRouterBridgeConfig:
    """Tests for RouterBridge configuration and setup."""

    def test_default_settings(self, router_bridge, mock_settings):
        """Test that bridge uses settings correctly."""
        assert router_bridge.connection_timeout == 5.0
        assert router_bridge.request_timeout == 10.0
        assert router_bridge.max_connections_per_tenant == 5
        assert router_bridge.queue_timeout == 10.0

    def test_register_router(self, router_bridge, sample_router_config):
        """Test registering a router configuration."""
        router_bridge.register_router("tenant-1", sample_router_config)
        config = router_bridge._get_router_config("tenant-1")
        assert config.host == "192.168.1.1"
        assert config.port == 8728

    def test_get_router_config_not_registered(self, router_bridge):
        """Test getting config for unregistered tenant raises error."""
        with pytest.raises(RouterBridgeError, match="No router configuration"):
            router_bridge._get_router_config("unknown-tenant")

    def test_get_pool_creates_new(self, router_bridge):
        """Test that _get_pool creates a new pool for unknown tenant."""
        pool = router_bridge._get_pool("new-tenant")
        assert pool.tenant_id == "new-tenant"
        assert pool.max_connections == 5

    def test_get_pool_reuses_existing(self, router_bridge):
        """Test that _get_pool returns the same pool for same tenant."""
        pool1 = router_bridge._get_pool("tenant-1")
        pool2 = router_bridge._get_pool("tenant-1")
        assert pool1 is pool2

    def test_get_pool_status_nonexistent(self, router_bridge):
        """Test pool status for a tenant without a pool."""
        status = router_bridge.get_pool_status("unknown")
        assert status["exists"] is False
        assert status["active_connections"] == 0
        assert status["max_connections"] == 5

    def test_get_pool_status_existing(self, router_bridge):
        """Test pool status for a tenant with an existing pool."""
        router_bridge._get_pool("tenant-1")
        status = router_bridge.get_pool_status("tenant-1")
        assert status["exists"] is True
        assert status["active_connections"] == 0


# --- Command Execution Tests ---


class TestRouterBridgeExecution:
    """Tests for RouterBridge command execution."""

    @pytest.mark.asyncio
    async def test_execute_command_success(
        self, registered_bridge, mock_client_factory
    ):
        """Test successful command execution."""
        mock_client_factory.execute_result = [{"id": "*1", "name": "test"}]

        response = await registered_bridge.execute_command(
            "tenant-1", "/system/resource"
        )

        assert response.success is True
        assert response.data == [{"id": "*1", "name": "test"}]
        assert response.command == "/system/resource"

    @pytest.mark.asyncio
    async def test_execute_command_with_params(
        self, registered_bridge, mock_client_factory
    ):
        """Test command execution with parameters."""
        mock_client_factory.execute_result = [{"id": "*1"}]

        response = await registered_bridge.execute_command(
            "tenant-1",
            "/ip/firewall/filter",
            {"_operation": "add", "chain": "forward"},
        )

        assert response.success is True

    @pytest.mark.asyncio
    async def test_execute_command_connection_error(
        self, registered_bridge, mock_client_factory
    ):
        """Test command execution when connection fails."""
        mock_client_factory.connect_error = RouterConnectionError(
            "Connection refused", host="192.168.1.1", port=8728
        )

        with pytest.raises(RouterConnectionError):
            await registered_bridge.execute_command(
                "tenant-1", "/system/resource"
            )

    @pytest.mark.asyncio
    async def test_execute_command_error(
        self, registered_bridge, mock_client_factory
    ):
        """Test command execution when command fails."""
        mock_client_factory.execute_error = RouterCommandError(
            "/bad/command", "no such command"
        )

        response = await registered_bridge.execute_command(
            "tenant-1", "/bad/command"
        )

        assert response.success is False
        assert "no such command" in response.error

    @pytest.mark.asyncio
    async def test_execute_command_no_config(self, router_bridge):
        """Test command execution without registered config."""
        with pytest.raises(RouterBridgeError, match="No router configuration"):
            await router_bridge.execute_command("unknown", "/system/resource")

    @pytest.mark.asyncio
    async def test_execute_releases_pool_on_success(
        self, registered_bridge, mock_client_factory
    ):
        """Test that pool slot is released after successful execution."""
        mock_client_factory.execute_result = []

        await registered_bridge.execute_command("tenant-1", "/system/resource")

        pool = registered_bridge._get_pool("tenant-1")
        assert pool.active_connections == 0

    @pytest.mark.asyncio
    async def test_execute_releases_pool_on_error(
        self, registered_bridge, mock_client_factory
    ):
        """Test that pool slot is released even when command fails."""
        mock_client_factory.execute_error = RouterCommandError(
            "/test", "error"
        )

        await registered_bridge.execute_command("tenant-1", "/test")

        pool = registered_bridge._get_pool("tenant-1")
        assert pool.active_connections == 0

    @pytest.mark.asyncio
    async def test_execute_releases_pool_on_connection_error(
        self, registered_bridge, mock_client_factory
    ):
        """Test that pool slot is released on connection error."""
        mock_client_factory.connect_error = RouterConnectionError(
            "refused", host="192.168.1.1"
        )

        with pytest.raises(RouterConnectionError):
            await registered_bridge.execute_command("tenant-1", "/test")

        pool = registered_bridge._get_pool("tenant-1")
        assert pool.active_connections == 0


# --- Connection Pool Exhaustion Tests ---


class TestConnectionPoolExhaustion:
    """Tests for connection pool exhaustion behavior."""

    @pytest.mark.asyncio
    async def test_pool_exhausted_raises_error(self):
        """Test that exhausted pool raises ConnectionPoolExhausted."""
        settings = MockSettings(
            router_max_connections_per_tenant=1,
            router_connection_queue_timeout=0,  # Immediate timeout
        )

        # Create a client that blocks forever
        class BlockingClientFactory:
            def __call__(self):
                client = MockMikroTikClient()
                return client

        bridge = RouterBridge(
            client_factory=BlockingClientFactory(),
            settings=settings,
        )
        bridge.register_router("tenant-1", RouterConfig(host="192.168.1.1"))

        # Manually acquire the only slot
        pool = bridge._get_pool("tenant-1")
        await pool.acquire()

        # Next request should fail immediately
        with pytest.raises(ConnectionPoolExhausted) as exc_info:
            await bridge.execute_command("tenant-1", "/test")

        assert exc_info.value.tenant_id == "tenant-1"

    @pytest.mark.asyncio
    async def test_concurrent_requests_within_limit(
        self, mock_client_factory
    ):
        """Test that concurrent requests within pool limit succeed."""
        settings = MockSettings(router_max_connections_per_tenant=3)
        mock_client_factory.execute_result = [{"ok": True}]

        bridge = RouterBridge(
            client_factory=mock_client_factory, settings=settings
        )
        bridge.register_router("tenant-1", RouterConfig(host="192.168.1.1"))

        # Run 3 concurrent requests (within limit of 3)
        results = await asyncio.gather(
            bridge.execute_command("tenant-1", "/test"),
            bridge.execute_command("tenant-1", "/test"),
            bridge.execute_command("tenant-1", "/test"),
        )

        assert all(r.success for r in results)


# --- Device Operations Tests ---


class TestDeviceOperations:
    """Tests for device-related operations."""

    @pytest.mark.asyncio
    async def test_get_devices_success(
        self, registered_bridge, mock_client_factory
    ):
        """Test getting devices from router."""
        mock_client_factory.execute_result = [
            {
                "mac-address": "AA:BB:CC:DD:EE:FF",
                "address": "192.168.1.100",
                "host-name": "my-phone",
                "interface": "bridge1",
                "last-seen": "1h30m",
                "bytes-in": "1024",
                "bytes-out": "2048",
            },
            {
                "mac-address": "11:22:33:44:55:66",
                "address": "192.168.1.101",
                "host-name": None,
                "interface": "bridge1",
            },
        ]

        devices = await registered_bridge.get_devices("tenant-1")

        assert len(devices) == 2
        assert devices[0].mac_address == "AA:BB:CC:DD:EE:FF"
        assert devices[0].ip_address == "192.168.1.100"
        assert devices[0].hostname == "my-phone"
        assert devices[0].bytes_in == 1024
        assert devices[0].bytes_out == 2048
        assert devices[1].mac_address == "11:22:33:44:55:66"
        assert devices[1].hostname is None

    @pytest.mark.asyncio
    async def test_get_devices_empty(
        self, registered_bridge, mock_client_factory
    ):
        """Test getting devices when none are connected."""
        mock_client_factory.execute_result = []

        devices = await registered_bridge.get_devices("tenant-1")
        assert devices == []

    @pytest.mark.asyncio
    async def test_get_devices_on_error_returns_empty(
        self, registered_bridge, mock_client_factory
    ):
        """Test that get_devices returns empty list on command error."""
        mock_client_factory.execute_error = RouterCommandError(
            "/ip/dhcp-server/lease", "access denied"
        )

        devices = await registered_bridge.get_devices("tenant-1")
        assert devices == []


# --- Firewall Rule Tests ---


class TestFirewallRuleOperations:
    """Tests for firewall rule operations."""

    @pytest.mark.asyncio
    async def test_add_firewall_rule(
        self, registered_bridge, mock_client_factory
    ):
        """Test adding a firewall rule."""
        mock_client_factory.execute_result = [{"id": "*1"}]

        rule = FirewallRuleParams(
            chain="forward",
            action="drop",
            dst_address="1.2.3.4",
            protocol="tcp",
            dst_port="443",
            comment="Block test",
        )

        response = await registered_bridge.add_firewall_rule("tenant-1", rule)
        assert response.success is True

    @pytest.mark.asyncio
    async def test_add_firewall_rule_with_layer7(
        self, registered_bridge, mock_client_factory
    ):
        """Test adding a Layer7 firewall rule."""
        mock_client_factory.execute_result = [{"id": "*2"}]

        rule = FirewallRuleParams(
            chain="forward",
            action="drop",
            layer7_protocol="instagram",
            comment="Block Instagram",
        )

        response = await registered_bridge.add_firewall_rule("tenant-1", rule)
        assert response.success is True

    @pytest.mark.asyncio
    async def test_remove_firewall_rule(
        self, registered_bridge, mock_client_factory
    ):
        """Test removing a firewall rule."""
        mock_client_factory.execute_result = [{"removed": True}]

        response = await registered_bridge.remove_firewall_rule(
            "tenant-1", "*1"
        )
        assert response.success is True


# --- Queue Rule Tests ---


class TestQueueRuleOperations:
    """Tests for queue rule (bandwidth) operations."""

    @pytest.mark.asyncio
    async def test_set_queue_rule(
        self, registered_bridge, mock_client_factory
    ):
        """Test creating a queue rule."""
        mock_client_factory.execute_result = [{"id": "*1"}]

        queue = QueueRuleParams(
            name="limit-device-1",
            target="192.168.1.100/32",
            max_limit="10M/10M",
            comment="Limit device",
        )

        response = await registered_bridge.set_queue_rule("tenant-1", queue)
        assert response.success is True

    @pytest.mark.asyncio
    async def test_delete_queue_rule(
        self, registered_bridge, mock_client_factory
    ):
        """Test deleting a queue rule."""
        mock_client_factory.execute_result = [{"removed": True}]

        response = await registered_bridge.delete_queue_rule("tenant-1", "*1")
        assert response.success is True


# --- Connection Test Tests ---


class TestConnectionTest:
    """Tests for the connection test functionality."""

    @pytest.mark.asyncio
    async def test_connection_test_success(
        self, router_bridge, mock_client_factory, sample_router_config
    ):
        """Test successful connection test."""
        result = await router_bridge.test_connection(sample_router_config)

        assert result.status == ConnectionStatus.SUCCESS
        assert result.message == "Connection successful"
        assert result.latency_ms is not None
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_connection_test_auth_failure(
        self, router_bridge, mock_client_factory, sample_router_config
    ):
        """Test connection test with authentication failure."""
        mock_client_factory.connect_error = RouterConnectionError(
            "Authentication failed: invalid password",
            host="192.168.1.1",
        )

        result = await router_bridge.test_connection(sample_router_config)

        assert result.status == ConnectionStatus.AUTH_FAILURE
        assert "Authentication failed" in result.message

    @pytest.mark.asyncio
    async def test_connection_test_unreachable(
        self, router_bridge, mock_client_factory, sample_router_config
    ):
        """Test connection test with unreachable router."""
        mock_client_factory.connect_error = RouterConnectionError(
            "Connection refused: host unreachable",
            host="192.168.1.1",
        )

        result = await router_bridge.test_connection(sample_router_config)

        assert result.status == ConnectionStatus.UNREACHABLE
        assert "unreachable" in result.message.lower()

    @pytest.mark.asyncio
    async def test_connection_test_timeout(self, sample_router_config):
        """Test connection test with timeout."""
        settings = MockSettings(router_connection_timeout=0)  # Immediate timeout

        class SlowClientFactory:
            def __call__(self):
                client = MockMikroTikClient()
                # Override connect to block
                import time

                original_connect = client.connect

                def slow_connect(*args, **kwargs):
                    time.sleep(1)  # Block longer than timeout
                    original_connect(*args, **kwargs)

                client.connect = slow_connect
                return client

        bridge = RouterBridge(
            client_factory=SlowClientFactory(), settings=settings
        )

        result = await bridge.test_connection(sample_router_config)

        assert result.status == ConnectionStatus.TIMEOUT
        assert "timed out" in result.message.lower()


# --- Shutdown Tests ---


class TestShutdown:
    """Tests for RouterBridge shutdown behavior."""

    @pytest.mark.asyncio
    async def test_shutdown_clears_pools(self, registered_bridge):
        """Test that shutdown clears all pools."""
        # Create a pool
        registered_bridge._get_pool("tenant-1")
        assert "tenant-1" in registered_bridge._pools

        await registered_bridge.shutdown()

        assert len(registered_bridge._pools) == 0
        assert len(registered_bridge._router_configs) == 0

    @pytest.mark.asyncio
    async def test_shutdown_idempotent(self, router_bridge):
        """Test that shutdown can be called multiple times safely."""
        await router_bridge.shutdown()
        await router_bridge.shutdown()  # Should not raise


# --- Isolation Tests ---


class TestTenantIsolation:
    """Tests for tenant isolation in connection pooling."""

    @pytest.mark.asyncio
    async def test_separate_pools_per_tenant(self, router_bridge):
        """Test that each tenant gets its own connection pool."""
        pool1 = router_bridge._get_pool("tenant-1")
        pool2 = router_bridge._get_pool("tenant-2")

        assert pool1 is not pool2
        assert pool1.tenant_id == "tenant-1"
        assert pool2.tenant_id == "tenant-2"

    @pytest.mark.asyncio
    async def test_tenant_pool_exhaustion_doesnt_affect_other(
        self, mock_client_factory
    ):
        """Test that one tenant's pool exhaustion doesn't affect another."""
        settings = MockSettings(
            router_max_connections_per_tenant=1,
            router_connection_queue_timeout=0,
        )
        mock_client_factory.execute_result = [{"ok": True}]

        bridge = RouterBridge(
            client_factory=mock_client_factory, settings=settings
        )
        bridge.register_router("tenant-1", RouterConfig(host="192.168.1.1"))
        bridge.register_router("tenant-2", RouterConfig(host="192.168.2.1"))

        # Exhaust tenant-1's pool
        pool1 = bridge._get_pool("tenant-1")
        await pool1.acquire()

        # tenant-1 should fail
        with pytest.raises(ConnectionPoolExhausted):
            await bridge.execute_command("tenant-1", "/test")

        # tenant-2 should still work
        response = await bridge.execute_command("tenant-2", "/test")
        assert response.success is True
