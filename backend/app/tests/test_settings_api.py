"""Tests for the settings API endpoints (router configuration)."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.schemas.settings import RouterConfigRequest


class TestRouterConfigRequestValidation:
    """Tests for RouterConfigRequest schema validation."""

    def test_valid_ipv4_address(self):
        """Should accept valid IPv4 addresses."""
        req = RouterConfigRequest(
            ip_address="192.168.1.1",
            api_port=8728,
            api_username="admin",
            api_password="password",
        )
        assert req.ip_address == "192.168.1.1"

    def test_valid_boundary_ip(self):
        """Should accept boundary IPv4 values."""
        req = RouterConfigRequest(
            ip_address="0.0.0.0",
            api_port=8728,
            api_username="admin",
            api_password="password",
        )
        assert req.ip_address == "0.0.0.0"

        req2 = RouterConfigRequest(
            ip_address="255.255.255.255",
            api_port=8728,
            api_username="admin",
            api_password="password",
        )
        assert req2.ip_address == "255.255.255.255"

    def test_invalid_ipv4_format(self):
        """Should reject invalid IPv4 formats."""
        with pytest.raises(ValueError):
            RouterConfigRequest(
                ip_address="not.an.ip",
                api_port=8728,
                api_username="admin",
                api_password="password",
            )

    def test_invalid_ipv4_octet_too_large(self):
        """Should reject IPv4 with octet > 255."""
        with pytest.raises(ValueError):
            RouterConfigRequest(
                ip_address="192.168.1.256",
                api_port=8728,
                api_username="admin",
                api_password="password",
            )

    def test_invalid_ipv4_too_few_octets(self):
        """Should reject IPv4 with fewer than 4 octets."""
        with pytest.raises(ValueError):
            RouterConfigRequest(
                ip_address="192.168.1",
                api_port=8728,
                api_username="admin",
                api_password="password",
            )

    def test_invalid_ipv4_ipv6_format(self):
        """Should reject IPv6 addresses."""
        with pytest.raises(ValueError):
            RouterConfigRequest(
                ip_address="::1",
                api_port=8728,
                api_username="admin",
                api_password="password",
            )

    def test_valid_port_boundaries(self):
        """Should accept port at boundaries (1 and 65535)."""
        req1 = RouterConfigRequest(
            ip_address="10.0.0.1",
            api_port=1,
            api_username="admin",
            api_password="password",
        )
        assert req1.api_port == 1

        req2 = RouterConfigRequest(
            ip_address="10.0.0.1",
            api_port=65535,
            api_username="admin",
            api_password="password",
        )
        assert req2.api_port == 65535

    def test_invalid_port_zero(self):
        """Should reject port 0."""
        with pytest.raises(ValueError):
            RouterConfigRequest(
                ip_address="10.0.0.1",
                api_port=0,
                api_username="admin",
                api_password="password",
            )

    def test_invalid_port_too_large(self):
        """Should reject port > 65535."""
        with pytest.raises(ValueError):
            RouterConfigRequest(
                ip_address="10.0.0.1",
                api_port=65536,
                api_username="admin",
                api_password="password",
            )

    def test_invalid_port_negative(self):
        """Should reject negative port."""
        with pytest.raises(ValueError):
            RouterConfigRequest(
                ip_address="10.0.0.1",
                api_port=-1,
                api_username="admin",
                api_password="password",
            )


class TestSettingsEndpoints:
    """Integration tests for settings API endpoints."""

    @pytest.fixture
    def app(self):
        """Create a fresh application instance."""
        return create_app()

    @pytest.fixture
    async def client(self, app):
        """Create an async HTTP test client."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac

    @pytest.fixture
    def mock_tenant_id(self):
        """Return a mock tenant ID."""
        return str(uuid.uuid4())

    @pytest.fixture
    def auth_headers(self):
        """Return mock auth headers."""
        return {"Authorization": "Bearer mock-token"}

    @pytest.mark.asyncio
    async def test_get_router_config_not_found(self, client, auth_headers, mock_tenant_id):
        """GET /api/settings/router should return 404 when no config exists."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        from app.core.tenant_middleware import get_current_tenant_id, get_tenant_session

        app = client._transport.app
        app.dependency_overrides[get_current_tenant_id] = lambda: mock_tenant_id
        app.dependency_overrides[get_tenant_session] = lambda: mock_session

        response = await client.get("/api/settings/router", headers=auth_headers)
        assert response.status_code == 404

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_router_config_success(self, client, auth_headers, mock_tenant_id):
        """GET /api/settings/router should return config when it exists."""
        mock_config = MagicMock()
        mock_config.ip_address = "192.168.88.1"
        mock_config.api_port = 8728
        mock_config.api_username = "admin"
        mock_config.connection_status = "connected"
        mock_config.last_connected = datetime(2024, 1, 1, tzinfo=timezone.utc)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_config
        mock_session.execute = AsyncMock(return_value=mock_result)

        from app.core.tenant_middleware import get_current_tenant_id, get_tenant_session

        app = client._transport.app
        app.dependency_overrides[get_current_tenant_id] = lambda: mock_tenant_id
        app.dependency_overrides[get_tenant_session] = lambda: mock_session

        response = await client.get("/api/settings/router", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["ip_address"] == "192.168.88.1"
        assert data["api_port"] == 8728
        assert data["api_username"] == "admin"
        assert data["connection_status"] == "connected"
        # Password should NOT be in response
        assert "api_password" not in data
        assert "encrypted_password" not in data

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_put_router_config_creates_new(self, client, auth_headers, mock_tenant_id):
        """PUT /api/settings/router should create config when none exists."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        from app.core.tenant_middleware import get_current_tenant_id, get_tenant_session

        app = client._transport.app
        app.dependency_overrides[get_current_tenant_id] = lambda: mock_tenant_id
        app.dependency_overrides[get_tenant_session] = lambda: mock_session

        with patch("app.api.settings.encrypt_password", return_value=(b"encrypted", b"iv12bytes123")):
            response = await client.put(
                "/api/settings/router",
                headers=auth_headers,
                json={
                    "ip_address": "192.168.88.1",
                    "api_port": 8728,
                    "api_username": "admin",
                    "api_password": "secret123",
                },
            )

        assert response.status_code == 200
        mock_session.add.assert_called_once()

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_put_router_config_invalid_ip(self, client, auth_headers, mock_tenant_id):
        """PUT /api/settings/router should reject invalid IP."""
        from app.core.tenant_middleware import get_current_tenant_id, get_tenant_session

        mock_session = AsyncMock()
        app = client._transport.app
        app.dependency_overrides[get_current_tenant_id] = lambda: mock_tenant_id
        app.dependency_overrides[get_tenant_session] = lambda: mock_session

        response = await client.put(
            "/api/settings/router",
            headers=auth_headers,
            json={
                "ip_address": "999.999.999.999",
                "api_port": 8728,
                "api_username": "admin",
                "api_password": "secret123",
            },
        )
        assert response.status_code == 422

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_put_router_config_invalid_port(self, client, auth_headers, mock_tenant_id):
        """PUT /api/settings/router should reject invalid port."""
        from app.core.tenant_middleware import get_current_tenant_id, get_tenant_session

        mock_session = AsyncMock()
        app = client._transport.app
        app.dependency_overrides[get_current_tenant_id] = lambda: mock_tenant_id
        app.dependency_overrides[get_tenant_session] = lambda: mock_session

        response = await client.put(
            "/api/settings/router",
            headers=auth_headers,
            json={
                "ip_address": "192.168.1.1",
                "api_port": 70000,
                "api_username": "admin",
                "api_password": "secret123",
            },
        )
        assert response.status_code == 422

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_post_router_test_not_found(self, client, auth_headers, mock_tenant_id):
        """POST /api/settings/router/test should return 404 when no config exists."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        from app.core.tenant_middleware import get_current_tenant_id, get_tenant_session

        app = client._transport.app
        app.dependency_overrides[get_current_tenant_id] = lambda: mock_tenant_id
        app.dependency_overrides[get_tenant_session] = lambda: mock_session

        response = await client.post("/api/settings/router/test", headers=auth_headers)
        assert response.status_code == 404

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_post_router_test_success(self, client, auth_headers, mock_tenant_id):
        """POST /api/settings/router/test should return success on successful connection."""
        from app.services.router_bridge import ConnectionResult, ConnectionStatus

        mock_config = MagicMock()
        mock_config.ip_address = "192.168.88.1"
        mock_config.api_port = 8728
        mock_config.api_username = "admin"
        mock_config.encrypted_password = b"encrypted"
        mock_config.encryption_iv = b"iv12bytes123"
        mock_config.connection_status = "disconnected"
        mock_config.last_connected = None

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_config
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        mock_connection_result = ConnectionResult(
            status=ConnectionStatus.SUCCESS,
            message="Connection successful",
            latency_ms=45.2,
        )

        from app.core.tenant_middleware import get_current_tenant_id, get_tenant_session

        app = client._transport.app
        app.dependency_overrides[get_current_tenant_id] = lambda: mock_tenant_id
        app.dependency_overrides[get_tenant_session] = lambda: mock_session

        with (
            patch("app.api.settings.decrypt_password", return_value="decrypted_pass"),
            patch(
                "app.api.settings.RouterBridge.test_connection",
                new_callable=AsyncMock,
                return_value=mock_connection_result,
            ),
        ):
            response = await client.post("/api/settings/router/test", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["message"] == "Connection successful"
        assert data["latency_ms"] == 45.2

        # Verify connection status was updated
        assert mock_config.connection_status == "connected"

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_post_router_test_failure(self, client, auth_headers, mock_tenant_id):
        """POST /api/settings/router/test should return failure status on timeout."""
        from app.services.router_bridge import ConnectionResult, ConnectionStatus

        mock_config = MagicMock()
        mock_config.ip_address = "192.168.88.1"
        mock_config.api_port = 8728
        mock_config.api_username = "admin"
        mock_config.encrypted_password = b"encrypted"
        mock_config.encryption_iv = b"iv12bytes123"
        mock_config.connection_status = "connected"
        mock_config.last_connected = None

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_config
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        mock_connection_result = ConnectionResult(
            status=ConnectionStatus.TIMEOUT,
            message="Connection timed out after 10s",
            latency_ms=None,
        )

        from app.core.tenant_middleware import get_current_tenant_id, get_tenant_session

        app = client._transport.app
        app.dependency_overrides[get_current_tenant_id] = lambda: mock_tenant_id
        app.dependency_overrides[get_tenant_session] = lambda: mock_session

        with (
            patch("app.api.settings.decrypt_password", return_value="decrypted_pass"),
            patch(
                "app.api.settings.RouterBridge.test_connection",
                new_callable=AsyncMock,
                return_value=mock_connection_result,
            ),
        ):
            response = await client.post("/api/settings/router/test", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "timeout"
        assert "timed out" in data["message"]
        assert data["latency_ms"] is None

        # Verify connection status was updated to disconnected
        assert mock_config.connection_status == "disconnected"

        app.dependency_overrides.clear()
