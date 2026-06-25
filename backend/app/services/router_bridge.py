"""RouterBridge service - MikroTik API communication with connection pooling.

Provides a clean abstraction layer for communicating with MikroTik routers
via the RouterOS API. Implements per-tenant connection pooling (max 5 concurrent),
connection/request timeouts, and request queuing.

Requirements: 13.3, 13.4, 13.5
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

from app.core.config import get_settings

logger = logging.getLogger(__name__)


# --- Exceptions ---


class RouterBridgeError(Exception):
    """Base exception for RouterBridge errors."""

    pass


class ConnectionPoolExhausted(RouterBridgeError):
    """Raised when all connections are in use and queue timeout expires."""

    def __init__(self, tenant_id: str, timeout: float):
        self.tenant_id = tenant_id
        self.timeout = timeout
        super().__init__(
            f"Connection pool exhausted for tenant {tenant_id}. "
            f"All connections in use and queue timeout ({timeout}s) expired."
        )


class RouterConnectionError(RouterBridgeError):
    """Raised when unable to connect to the MikroTik router."""

    def __init__(self, message: str, host: str | None = None, port: int | None = None):
        self.host = host
        self.port = port
        super().__init__(message)


class RouterCommandError(RouterBridgeError):
    """Raised when a router command fails."""

    def __init__(self, command: str, message: str):
        self.command = command
        super().__init__(f"Command '{command}' failed: {message}")


class RouterTimeoutError(RouterBridgeError):
    """Raised when a router request times out."""

    def __init__(self, command: str, timeout: float):
        self.command = command
        self.timeout = timeout
        super().__init__(
            f"Request timeout ({timeout}s) exceeded for command '{command}'"
        )


# --- Data Classes ---


class ConnectionStatus(str, Enum):
    """Router connection test result status."""

    SUCCESS = "success"
    TIMEOUT = "timeout"
    AUTH_FAILURE = "auth_failure"
    UNREACHABLE = "unreachable"
    ERROR = "error"


@dataclass
class RouterConfig:
    """Configuration for connecting to a MikroTik router."""

    host: str
    port: int = 8728
    username: str = "admin"
    password: str = ""


@dataclass
class RouterResponse:
    """Response from a MikroTik router command."""

    success: bool
    data: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    command: str = ""


@dataclass
class ConnectionResult:
    """Result of a connection test to a MikroTik router."""

    status: ConnectionStatus
    message: str
    latency_ms: float | None = None


@dataclass
class DeviceInfo:
    """Device information retrieved from the router."""

    mac_address: str
    ip_address: str | None = None
    hostname: str | None = None
    interface: str | None = None
    uptime: str | None = None
    bytes_in: int = 0
    bytes_out: int = 0


@dataclass
class FirewallRuleParams:
    """Parameters for a firewall rule."""

    chain: str = "forward"
    action: str = "drop"
    src_address: str | None = None
    dst_address: str | None = None
    protocol: str | None = None
    dst_port: str | None = None
    layer7_protocol: str | None = None
    tls_host: str | None = None
    comment: str | None = None


@dataclass
class QueueRuleParams:
    """Parameters for a queue (bandwidth) rule."""

    name: str = ""
    target: str = ""
    max_limit: str = ""  # e.g., "10M/10M" (upload/download)
    comment: str | None = None


# --- MikroTik Client Protocol ---


class MikroTikClientProtocol(Protocol):
    """Protocol defining the interface for a MikroTik API client.

    This abstraction allows the RouterBridge to work with either a real
    routeros-api client or a mock/stub for testing.
    """

    def connect(self, host: str, port: int, username: str, password: str) -> None:
        """Connect to the router."""
        ...

    def disconnect(self) -> None:
        """Disconnect from the router."""
        ...

    def execute(self, command: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Execute a command and return the response."""
        ...


# --- Default MikroTik Client Implementation ---


class MikroTikClient:
    """MikroTik API client wrapper using routeros-api library.

    Wraps the routeros_api library to provide a consistent interface
    that can be easily mocked in tests.
    """

    def __init__(self) -> None:
        self._connection: Any = None
        self._api: Any = None

    def connect(self, host: str, port: int, username: str, password: str) -> None:
        """Establish connection to the MikroTik router.

        Args:
            host: Router IP address.
            port: Router API port.
            username: API username.
            password: API password.

        Raises:
            RouterConnectionError: If connection fails.
        """
        try:
            import routeros_api

            self._connection = routeros_api.RouterOsApiPool(
                host=host,
                port=port,
                username=username,
                password=password,
                plaintext_login=True,
            )
            self._api = self._connection.get_api()
        except ImportError:
            raise RouterConnectionError(
                "routeros-api library not installed", host=host, port=port
            )
        except Exception as e:
            raise RouterConnectionError(
                f"Failed to connect to router: {e}", host=host, port=port
            )

    def disconnect(self) -> None:
        """Close the connection to the router."""
        if self._connection is not None:
            try:
                self._connection.disconnect()
            except Exception:
                pass
            finally:
                self._connection = None
                self._api = None

    def execute(self, command: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Execute a RouterOS API command.

        Args:
            command: The API command path (e.g., '/ip/dhcp-server/lease/print').
            params: Optional parameters for the command.

        Returns:
            List of response dictionaries.

        Raises:
            RouterCommandError: If the command fails.
        """
        if self._api is None:
            raise RouterCommandError(command, "Not connected to router")

        try:
            resource = self._api.get_resource(command)
            if params is None:
                return resource.get()

            # Determine operation from params
            operation = params.pop("_operation", "get")
            if operation == "add":
                result = resource.add(**params)
                return [{"id": result}] if result else []
            elif operation == "remove":
                resource.remove(id=params.get("id", ""))
                return [{"removed": True}]
            elif operation == "set":
                resource.set(id=params.pop("id", ""), **params)
                return [{"updated": True}]
            else:
                return resource.get(**params)
        except Exception as e:
            raise RouterCommandError(command, str(e))


# --- Connection Pool ---


class TenantConnectionPool:
    """Manages connection pooling for a single tenant.

    Uses an asyncio.Semaphore to limit concurrent connections and
    asyncio.wait_for to implement queue timeout.
    """

    def __init__(self, tenant_id: str, max_connections: int, queue_timeout: float):
        self.tenant_id = tenant_id
        self.max_connections = max_connections
        self.queue_timeout = queue_timeout
        self._semaphore = asyncio.Semaphore(max_connections)
        self._active_count = 0

    @property
    def active_connections(self) -> int:
        """Number of currently active connections."""
        return self._active_count

    @property
    def available_connections(self) -> int:
        """Number of available connection slots."""
        return self.max_connections - self._active_count

    async def acquire(self) -> None:
        """Acquire a connection slot from the pool.

        Waits up to queue_timeout seconds for a slot to become available.

        Raises:
            ConnectionPoolExhausted: If timeout expires before a slot is available.
        """
        try:
            # For zero/negative timeout, try non-blocking acquire first
            if self.queue_timeout <= 0:
                if self._semaphore._value <= 0:
                    raise ConnectionPoolExhausted(self.tenant_id, self.queue_timeout)
                await self._semaphore.acquire()
            else:
                await asyncio.wait_for(
                    self._semaphore.acquire(), timeout=self.queue_timeout
                )
            self._active_count += 1
        except asyncio.TimeoutError:
            raise ConnectionPoolExhausted(self.tenant_id, self.queue_timeout)

    def release(self) -> None:
        """Release a connection slot back to the pool."""
        self._active_count = max(0, self._active_count - 1)
        self._semaphore.release()


# --- RouterBridge Service ---


class RouterBridge:
    """Service for communicating with MikroTik routers.

    Provides connection pooling per tenant, request timeouts, and a clean
    command execution interface. The MikroTik client can be injected for
    testing purposes.

    Usage:
        bridge = RouterBridge()
        # Or with a custom client factory for testing:
        bridge = RouterBridge(client_factory=lambda: mock_client)
    """

    def __init__(
        self,
        client_factory: type[MikroTikClient] | Any = None,
        settings: Any = None,
    ) -> None:
        """Initialize the RouterBridge.

        Args:
            client_factory: Factory callable that creates MikroTikClient instances.
                           Defaults to MikroTikClient if not provided.
            settings: Application settings. Defaults to get_settings() if not provided.
        """
        self._settings = settings or get_settings()
        self._client_factory = client_factory or MikroTikClient
        self._pools: dict[str, TenantConnectionPool] = {}
        self._router_configs: dict[str, RouterConfig] = {}

    @property
    def connection_timeout(self) -> float:
        """Connection timeout in seconds."""
        return float(self._settings.router_connection_timeout)

    @property
    def request_timeout(self) -> float:
        """Request timeout in seconds."""
        return float(self._settings.router_request_timeout)

    @property
    def max_connections_per_tenant(self) -> int:
        """Maximum concurrent connections per tenant."""
        return int(self._settings.router_max_connections_per_tenant)

    @property
    def queue_timeout(self) -> float:
        """Queue timeout when all connections are in use."""
        return float(self._settings.router_connection_queue_timeout)

    def _get_pool(self, tenant_id: str) -> TenantConnectionPool:
        """Get or create a connection pool for a tenant.

        Args:
            tenant_id: The tenant identifier.

        Returns:
            The tenant's connection pool.
        """
        if tenant_id not in self._pools:
            self._pools[tenant_id] = TenantConnectionPool(
                tenant_id=tenant_id,
                max_connections=self.max_connections_per_tenant,
                queue_timeout=self.queue_timeout,
            )
        return self._pools[tenant_id]

    def register_router(self, tenant_id: str, config: RouterConfig) -> None:
        """Register a router configuration for a tenant.

        Args:
            tenant_id: The tenant identifier.
            config: The router connection configuration.
        """
        self._router_configs[tenant_id] = config

    def _get_router_config(self, tenant_id: str) -> RouterConfig:
        """Get the router configuration for a tenant.

        Args:
            tenant_id: The tenant identifier.

        Returns:
            The router configuration.

        Raises:
            RouterBridgeError: If no configuration is registered for the tenant.
        """
        if tenant_id not in self._router_configs:
            raise RouterBridgeError(
                f"No router configuration registered for tenant {tenant_id}"
            )
        return self._router_configs[tenant_id]

    async def execute_command(
        self, tenant_id: str, command: str, params: dict[str, Any] | None = None
    ) -> RouterResponse:
        """Execute a command on the tenant's MikroTik router.

        Acquires a connection from the pool, executes the command with
        request timeout, and returns the translated response.

        Args:
            tenant_id: The tenant identifier.
            command: The RouterOS API command path.
            params: Optional command parameters.

        Returns:
            RouterResponse with the command result.

        Raises:
            ConnectionPoolExhausted: If all connections are in use and queue times out.
            RouterTimeoutError: If the request exceeds the timeout.
            RouterConnectionError: If unable to connect to the router.
            RouterCommandError: If the command fails.
        """
        pool = self._get_pool(tenant_id)
        config = self._get_router_config(tenant_id)

        # Acquire a connection slot (waits up to queue_timeout)
        await pool.acquire()

        try:
            # Execute with request timeout
            result = await asyncio.wait_for(
                self._execute_with_client(config, command, params),
                timeout=self.request_timeout,
            )
            return result
        except asyncio.TimeoutError:
            raise RouterTimeoutError(command, self.request_timeout)
        finally:
            pool.release()

    async def _execute_with_client(
        self,
        config: RouterConfig,
        command: str,
        params: dict[str, Any] | None = None,
    ) -> RouterResponse:
        """Execute a command using a MikroTik client instance.

        Creates a client, connects, executes the command, and disconnects.
        Runs in a thread executor since routeros-api is synchronous.

        Args:
            config: Router connection configuration.
            command: The API command path.
            params: Optional command parameters.

        Returns:
            RouterResponse with the result.
        """
        loop = asyncio.get_event_loop()

        def _sync_execute() -> RouterResponse:
            client = self._client_factory()
            try:
                client.connect(
                    host=config.host,
                    port=config.port,
                    username=config.username,
                    password=config.password,
                )
                data = client.execute(command, params)
                return RouterResponse(success=True, data=data, command=command)
            except RouterCommandError as e:
                return RouterResponse(success=False, error=str(e), command=command)
            except RouterConnectionError as e:
                raise e
            except Exception as e:
                return RouterResponse(success=False, error=str(e), command=command)
            finally:
                try:
                    client.disconnect()
                except Exception:
                    pass

        return await loop.run_in_executor(None, _sync_execute)

    async def get_devices(self, tenant_id: str) -> list[DeviceInfo]:
        """Get all connected devices from the tenant's router.

        Args:
            tenant_id: The tenant identifier.

        Returns:
            List of DeviceInfo objects for connected devices.
        """
        response = await self.execute_command(
            tenant_id, "/ip/dhcp-server/lease"
        )

        if not response.success:
            logger.error(
                f"Failed to get devices for tenant {tenant_id}: {response.error}"
            )
            return []

        devices = []
        for entry in response.data:
            devices.append(
                DeviceInfo(
                    mac_address=entry.get("mac-address", ""),
                    ip_address=entry.get("address"),
                    hostname=entry.get("host-name"),
                    interface=entry.get("interface"),
                    uptime=entry.get("last-seen"),
                    bytes_in=int(entry.get("bytes-in", 0) or 0),
                    bytes_out=int(entry.get("bytes-out", 0) or 0),
                )
            )
        return devices

    async def add_firewall_rule(
        self, tenant_id: str, rule: FirewallRuleParams
    ) -> RouterResponse:
        """Add a firewall rule to the tenant's router.

        Args:
            tenant_id: The tenant identifier.
            rule: The firewall rule parameters.

        Returns:
            RouterResponse indicating success or failure.
        """
        params: dict[str, Any] = {"_operation": "add"}
        if rule.chain:
            params["chain"] = rule.chain
        if rule.action:
            params["action"] = rule.action
        if rule.src_address:
            params["src-address"] = rule.src_address
        if rule.dst_address:
            params["dst-address"] = rule.dst_address
        if rule.protocol:
            params["protocol"] = rule.protocol
        if rule.dst_port:
            params["dst-port"] = rule.dst_port
        if rule.layer7_protocol:
            params["layer7-protocol"] = rule.layer7_protocol
        if rule.tls_host:
            params["tls-host"] = rule.tls_host
        if rule.comment:
            params["comment"] = rule.comment

        return await self.execute_command(
            tenant_id, "/ip/firewall/filter", params
        )

    async def remove_firewall_rule(
        self, tenant_id: str, rule_id: str
    ) -> RouterResponse:
        """Remove a firewall rule from the tenant's router.

        Args:
            tenant_id: The tenant identifier.
            rule_id: The MikroTik rule ID to remove.

        Returns:
            RouterResponse indicating success or failure.
        """
        return await self.execute_command(
            tenant_id,
            "/ip/firewall/filter",
            {"_operation": "remove", "id": rule_id},
        )

    async def set_queue_rule(
        self, tenant_id: str, queue: QueueRuleParams
    ) -> RouterResponse:
        """Create a queue rule (bandwidth limit) on the tenant's router.

        Args:
            tenant_id: The tenant identifier.
            queue: The queue rule parameters.

        Returns:
            RouterResponse indicating success or failure.
        """
        params: dict[str, Any] = {"_operation": "add"}
        if queue.name:
            params["name"] = queue.name
        if queue.target:
            params["target"] = queue.target
        if queue.max_limit:
            params["max-limit"] = queue.max_limit
        if queue.comment:
            params["comment"] = queue.comment

        return await self.execute_command(
            tenant_id, "/queue/simple", params
        )

    async def delete_queue_rule(
        self, tenant_id: str, queue_id: str
    ) -> RouterResponse:
        """Delete a queue rule from the tenant's router.

        Args:
            tenant_id: The tenant identifier.
            queue_id: The MikroTik queue ID to delete.

        Returns:
            RouterResponse indicating success or failure.
        """
        return await self.execute_command(
            tenant_id,
            "/queue/simple",
            {"_operation": "remove", "id": queue_id},
        )

    async def get_hotspot_active_users(self, tenant_id: str) -> list[dict[str, Any]]:
        """Get all active Hotspot users on the tenant's router.
        
        Args:
            tenant_id: The tenant identifier.
            
        Returns:
            List of active hotspot user dictionaries.
        """
        response = await self.execute_command(tenant_id, "/ip/hotspot/active/print")
        if not response.success:
            logger.error(f"Failed to get hotspot users for tenant {tenant_id}: {response.error}")
            return []
        return response.data

    async def add_layer7_protocol(self, tenant_id: str, name: str, regexp: str, comment: str | None = None) -> RouterResponse:
        """Add a Layer 7 protocol definition for advanced blocking.
        
        Args:
            tenant_id: The tenant identifier.
            name: The name of the protocol (e.g., 'instagram').
            regexp: The regular expression to match.
            comment: Optional comment.
            
        Returns:
            RouterResponse indicating success or failure.
        """
        params: dict[str, Any] = {
            "_operation": "add",
            "name": name,
            "regexp": regexp
        }
        if comment:
            params["comment"] = comment
            
        return await self.execute_command(tenant_id, "/ip/firewall/layer7-protocol", params)

    async def get_interface_traffic(self, tenant_id: str, interface: str) -> dict[str, int]:
        """Get real-time bandwidth traffic for an interface.
        
        Args:
            tenant_id: The tenant identifier.
            interface: The interface name (e.g., 'ether1', 'bridge').
            
        Returns:
            Dictionary containing 'rx-bits-per-second' and 'tx-bits-per-second'.
        """
        response = await self.execute_command(
            tenant_id, 
            "/interface/monitor-traffic", 
            {"interface": interface, "once": "yes"}
        )
        if not response.success or not response.data:
            return {"rx-bits-per-second": 0, "tx-bits-per-second": 0}
            
        data = response.data[0]
        return {
            "rx-bits-per-second": int(data.get("rx-bits-per-second", 0)),
            "tx-bits-per-second": int(data.get("tx-bits-per-second", 0))
        }

    async def make_dhcp_lease_static(self, tenant_id: str, mac_address: str) -> RouterResponse:
        """Make a dynamic DHCP lease static.
        
        Args:
            tenant_id: The tenant identifier.
            mac_address: The MAC address to make static.
            
        Returns:
            RouterResponse indicating success or failure.
        """
        # First, find the lease ID
        response = await self.execute_command(
            tenant_id, 
            "/ip/dhcp-server/lease/print", 
            {"mac-address": mac_address}
        )
        if not response.success or not response.data:
            return RouterResponse(success=False, error="Lease not found for MAC")
            
        lease_id = response.data[0].get(".id")
        if not lease_id:
            return RouterResponse(success=False, error="Lease ID not found")
            
        # Execute make-static command
        return await self.execute_command(
            tenant_id,
            "/ip/dhcp-server/lease/make-static",
            {"numbers": lease_id}
        )

    async def create_wireguard_server(self, tenant_id: str, name: str, listen_port: int) -> RouterResponse:
        """Create a WireGuard interface (Server)."""
        return await self.execute_command(
            tenant_id,
            "/interface/wireguard/add",
            {
                "_operation": "add",
                "name": name,
                "listen-port": str(listen_port)
            }
        )

    async def add_wireguard_peer(
        self, tenant_id: str, interface: str, public_key: str, allowed_address: str
    ) -> RouterResponse:
        """Add a WireGuard peer (Client) to the interface."""
        return await self.execute_command(
            tenant_id,
            "/interface/wireguard/peers/add",
            {
                "_operation": "add",
                "interface": interface,
                "public-key": public_key,
                "allowed-address": allowed_address
            }
        )

    async def add_parental_control_rule(
        self, tenant_id: str, mac_address: str, time: str, days: str, action: str = "drop"
    ) -> RouterResponse:
        """Add a time-based firewall rule for Parental Control.
        
        Args:
            time: Format 'start-end', e.g., '22:00:00-07:00:00'.
            days: Comma-separated days, e.g., 'sun,mon,tue,wed,thu,fri,sat'.
        """
        return await self.execute_command(
            tenant_id,
            "/ip/firewall/filter",
            {
                "_operation": "add",
                "chain": "forward",
                "src-mac-address": mac_address,
                "time": f"{time},{days}",
                "action": action,
                "comment": f"Parental Control: {mac_address}"
            }
        )

    async def test_connection(self, config: RouterConfig) -> ConnectionResult:
        """Test connectivity to a MikroTik router.

        Attempts to connect with the given configuration using the
        connection timeout setting.

        Args:
            config: Router connection configuration to test.

        Returns:
            ConnectionResult with status and details.
        """
        import time

        start_time = time.monotonic()

        try:
            loop = asyncio.get_event_loop()

            def _sync_test() -> ConnectionResult:
                client = self._client_factory()
                try:
                    client.connect(
                        host=config.host,
                        port=config.port,
                        username=config.username,
                        password=config.password,
                    )
                    elapsed = (time.monotonic() - start_time) * 1000
                    return ConnectionResult(
                        status=ConnectionStatus.SUCCESS,
                        message="Connection successful",
                        latency_ms=round(elapsed, 2),
                    )
                except RouterConnectionError as e:
                    msg = str(e).lower()
                    if "auth" in msg or "login" in msg or "password" in msg:
                        return ConnectionResult(
                            status=ConnectionStatus.AUTH_FAILURE,
                            message="Authentication failed: invalid credentials",
                        )
                    elif "timeout" in msg:
                        return ConnectionResult(
                            status=ConnectionStatus.TIMEOUT,
                            message=f"Connection timed out after {self.connection_timeout}s",
                        )
                    else:
                        return ConnectionResult(
                            status=ConnectionStatus.UNREACHABLE,
                            message=f"Router unreachable: {e}",
                        )
                except Exception as e:
                    return ConnectionResult(
                        status=ConnectionStatus.ERROR,
                        message=f"Connection error: {e}",
                    )
                finally:
                    try:
                        client.disconnect()
                    except Exception:
                        pass

            result = await asyncio.wait_for(
                loop.run_in_executor(None, _sync_test),
                timeout=self.connection_timeout,
            )
            return result

        except asyncio.TimeoutError:
            return ConnectionResult(
                status=ConnectionStatus.TIMEOUT,
                message=f"Connection timed out after {self.connection_timeout}s",
            )

    async def shutdown(self) -> None:
        """Clean up all connection pools on shutdown."""
        logger.info("Shutting down RouterBridge, cleaning up connection pools")
        self._pools.clear()
        self._router_configs.clear()

    def get_pool_status(self, tenant_id: str) -> dict[str, Any]:
        """Get the connection pool status for a tenant.

        Args:
            tenant_id: The tenant identifier.

        Returns:
            Dictionary with pool status information.
        """
        if tenant_id not in self._pools:
            return {
                "tenant_id": tenant_id,
                "exists": False,
                "active_connections": 0,
                "available_connections": self.max_connections_per_tenant,
                "max_connections": self.max_connections_per_tenant,
            }

        pool = self._pools[tenant_id]
        return {
            "tenant_id": tenant_id,
            "exists": True,
            "active_connections": pool.active_connections,
            "available_connections": pool.available_connections,
            "max_connections": pool.max_connections,
        }
