"""WebSocket connection manager for real-time push notifications.

Manages WebSocket connections per tenant, broadcasts events to all
connected clients within a tenant scope. Handles JWT authentication,
heartbeat/keepalive, and graceful disconnection.

Event Types:
- stats.update: Real-time network stats (every 1s)
- devices.update: Device list changed (every 10s or on change)
- alert.new: New anomaly alert detected
- router.status: Router connection status changed
"""

import asyncio
import json
import logging
import time
from typing import Any, Optional

from fastapi import WebSocket
from jose import JWTError

from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)


class WebSocketConnection:
    """Wraps a WebSocket with metadata for management."""

    __slots__ = ("websocket", "tenant_id", "admin_id", "connected_at", "last_ping")

    def __init__(self, websocket: WebSocket, tenant_id: str, admin_id: str) -> None:
        self.websocket = websocket
        self.tenant_id = tenant_id
        self.admin_id = admin_id
        self.connected_at = time.time()
        self.last_ping = time.time()


class ConnectionManager:
    """Manages WebSocket connections with tenant isolation.

    Architecture:
    - Connections grouped by tenant_id for efficient broadcast
    - JWT authentication on connect
    - Heartbeat monitoring (stale connections cleaned up)
    - Thread-safe via asyncio (single event loop)

    Usage:
        manager = ConnectionManager()
        # In WebSocket endpoint:
        await manager.connect(websocket, tenant_id, admin_id)
        # From stat collector or API:
        await manager.broadcast_to_tenant(tenant_id, "stats.update", data)
    """

    def __init__(self) -> None:
        # tenant_id -> list of active connections
        self._connections: dict[str, list[WebSocketConnection]] = {}
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._running = False

    @property
    def total_connections(self) -> int:
        """Total number of active WebSocket connections across all tenants."""
        return sum(len(conns) for conns in self._connections.values())

    @property
    def tenant_count(self) -> int:
        """Number of tenants with active connections."""
        return len(self._connections)

    def get_tenant_connections(self, tenant_id: str) -> int:
        """Number of active connections for a specific tenant."""
        return len(self._connections.get(tenant_id, []))

    async def start(self) -> None:
        """Start the heartbeat monitoring task."""
        if self._running:
            return
        self._running = True
        self._heartbeat_task = asyncio.create_task(
            self._heartbeat_loop(), name="ws_heartbeat"
        )
        logger.info("WebSocket ConnectionManager started")

    async def stop(self) -> None:
        """Stop heartbeat and close all connections gracefully."""
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

        # Close all connections
        all_conns = [
            conn
            for conns in self._connections.values()
            for conn in conns
        ]
        for conn in all_conns:
            try:
                await conn.websocket.close(code=1001, reason="Server shutting down")
            except Exception:
                pass

        self._connections.clear()
        logger.info("WebSocket ConnectionManager stopped, %d connections closed", len(all_conns))

    async def connect(self, websocket: WebSocket, tenant_id: str, admin_id: str) -> WebSocketConnection:
        """Accept and register a new WebSocket connection.

        Args:
            websocket: The WebSocket to accept.
            tenant_id: Tenant ID from JWT token.
            admin_id: Admin ID from JWT token.

        Returns:
            The registered WebSocketConnection.
        """
        await websocket.accept()

        conn = WebSocketConnection(websocket, tenant_id, admin_id)

        if tenant_id not in self._connections:
            self._connections[tenant_id] = []
        self._connections[tenant_id].append(conn)

        logger.info(
            "WebSocket connected: tenant=%s, admin=%s (total=%d)",
            tenant_id[:8],
            admin_id[:8],
            self.total_connections,
        )

        return conn

    def disconnect(self, conn: WebSocketConnection) -> None:
        """Remove a connection from the registry.

        Args:
            conn: The WebSocketConnection to remove.
        """
        tenant_conns = self._connections.get(conn.tenant_id, [])
        try:
            tenant_conns.remove(conn)
        except ValueError:
            pass

        # Clean up empty tenant entry
        if not tenant_conns and conn.tenant_id in self._connections:
            del self._connections[conn.tenant_id]

        logger.info(
            "WebSocket disconnected: tenant=%s (total=%d)",
            conn.tenant_id[:8],
            self.total_connections,
        )

    async def broadcast_to_tenant(
        self, tenant_id: str, event_type: str, data: Any
    ) -> int:
        """Send a message to all connections for a tenant.

        Args:
            tenant_id: Target tenant.
            event_type: Event type string (e.g., "stats.update").
            data: JSON-serializable payload.

        Returns:
            Number of clients that received the message.
        """
        conns = self._connections.get(tenant_id, [])
        if not conns:
            return 0

        message = json.dumps({"type": event_type, "data": data, "ts": time.time()})
        sent = 0
        disconnected: list[WebSocketConnection] = []

        for conn in conns:
            try:
                await conn.websocket.send_text(message)
                sent += 1
            except Exception:
                disconnected.append(conn)

        # Clean up dead connections
        for conn in disconnected:
            self.disconnect(conn)

        return sent

    async def broadcast_to_all(self, event_type: str, data: Any) -> int:
        """Send a message to all connected clients across all tenants.

        Args:
            event_type: Event type string.
            data: JSON-serializable payload.

        Returns:
            Total number of clients that received the message.
        """
        total = 0
        for tenant_id in list(self._connections.keys()):
            total += await self.broadcast_to_tenant(tenant_id, event_type, data)
        return total

    async def handle_client_message(self, conn: WebSocketConnection, raw: str) -> None:
        """Process an incoming message from a client.

        Handles:
        - ping: keepalive heartbeat
        - subscribe: channel subscription (future use)
        """
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return

        msg_type = msg.get("type", "")

        if msg_type == "ping":
            conn.last_ping = time.time()
            try:
                await conn.websocket.send_text(
                    json.dumps({"type": "pong", "ts": time.time()})
                )
            except Exception:
                pass

    async def _heartbeat_loop(self) -> None:
        """Periodically check for stale connections (no ping in 60s)."""
        while self._running:
            try:
                await asyncio.sleep(30)
                now = time.time()
                stale: list[WebSocketConnection] = []

                for conns in self._connections.values():
                    for conn in conns:
                        if now - conn.last_ping > 60:
                            stale.append(conn)

                for conn in stale:
                    try:
                        await conn.websocket.close(code=1000, reason="Heartbeat timeout")
                    except Exception:
                        pass
                    self.disconnect(conn)

                if stale:
                    logger.info("Cleaned %d stale WebSocket connections", len(stale))

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Heartbeat loop error: %s", e)


def authenticate_ws_token(token: str) -> tuple[str, str] | None:
    """Authenticate a WebSocket connection token.

    Args:
        token: JWT token string.

    Returns:
        Tuple of (admin_id, tenant_id) if valid, None otherwise.
    """
    try:
        payload = AuthService.decode_token(token)
        admin_id = payload.get("sub")
        tenant_id = payload.get("tenant_id")
        if admin_id and tenant_id:
            return admin_id, tenant_id
    except JWTError:
        pass
    return None


# === Singleton ===

_manager: Optional[ConnectionManager] = None


def get_ws_manager() -> ConnectionManager:
    """Get the singleton ConnectionManager instance."""
    global _manager
    if _manager is None:
        _manager = ConnectionManager()
    return _manager
