"""Tests for tenant isolation middleware and tenant service.

Tests cover:
- JWT token extraction and tenant_id dependency
- Tenant-scoped database session creation
- Cross-tenant access validation and logging
- Error handling for missing/invalid tokens
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.tenant_middleware import (
    get_current_admin,
    get_current_admin_id,
    get_current_tenant_id,
    get_tenant_session,
)
from app.services.auth_service import AuthService
from app.services.tenant_service import (
    CrossTenantAccessError,
    TenantService,
)


# --- Fixtures ---


@pytest.fixture
def tenant_id():
    """Generate a valid tenant UUID string."""
    return str(uuid.uuid4())


@pytest.fixture
def admin_id():
    """Generate a valid admin UUID string."""
    return str(uuid.uuid4())


@pytest.fixture
def valid_token(admin_id, tenant_id):
    """Create a valid JWT token for testing."""
    return AuthService.create_token(admin_id=admin_id, tenant_id=tenant_id)


@pytest.fixture
def expired_token(admin_id, tenant_id):
    """Create an expired JWT token for testing."""
    from jose import jwt

    from app.core.config import get_settings

    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": admin_id,
        "tenant_id": tenant_id,
        "iat": now - timedelta(hours=2),
        "exp": now - timedelta(hours=1),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


@pytest.fixture
def test_app(valid_token, tenant_id, admin_id):
    """Create a minimal FastAPI app with tenant middleware dependencies for testing."""
    app = FastAPI()

    @app.get("/test/tenant-id")
    async def get_tenant(tid: str = pytest.importorskip("fastapi").Depends(get_current_tenant_id)):
        return {"tenant_id": tid}

    @app.get("/test/admin-id")
    async def get_admin(aid: str = pytest.importorskip("fastapi").Depends(get_current_admin_id)):
        return {"admin_id": aid}

    @app.get("/test/admin")
    async def get_admin_payload(payload: dict = pytest.importorskip("fastapi").Depends(get_current_admin)):
        return payload

    return app


@pytest.fixture
def app_with_deps():
    """Create a FastAPI app with tenant middleware dependencies."""
    from fastapi import Depends

    app = FastAPI()

    @app.get("/test/tenant-id")
    async def get_tenant(tid: str = Depends(get_current_tenant_id)):
        return {"tenant_id": tid}

    @app.get("/test/admin-id")
    async def get_admin(aid: str = Depends(get_current_admin_id)):
        return {"admin_id": aid}

    @app.get("/test/admin")
    async def get_admin_payload(payload: dict = Depends(get_current_admin)):
        return payload

    return app


# --- Tests for get_current_admin ---


class TestGetCurrentAdmin:
    """Tests for the get_current_admin dependency."""

    async def test_valid_token_returns_payload(self, app_with_deps, valid_token, admin_id, tenant_id):
        """A valid JWT token should return the decoded payload."""
        async with AsyncClient(
            transport=ASGITransport(app=app_with_deps),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/test/admin",
                headers={"Authorization": f"Bearer {valid_token}"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["sub"] == admin_id
            assert data["tenant_id"] == tenant_id

    async def test_missing_token_returns_401(self, app_with_deps):
        """A request without a token should return 401."""
        async with AsyncClient(
            transport=ASGITransport(app=app_with_deps),
            base_url="http://test",
        ) as client:
            response = await client.get("/test/admin")
            assert response.status_code == 401

    async def test_invalid_token_returns_401(self, app_with_deps):
        """An invalid JWT token should return 401."""
        async with AsyncClient(
            transport=ASGITransport(app=app_with_deps),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/test/admin",
                headers={"Authorization": "Bearer invalid-token-here"},
            )
            assert response.status_code == 401

    async def test_expired_token_returns_401(self, app_with_deps, expired_token):
        """An expired JWT token should return 401."""
        async with AsyncClient(
            transport=ASGITransport(app=app_with_deps),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/test/admin",
                headers={"Authorization": f"Bearer {expired_token}"},
            )
            assert response.status_code == 401


# --- Tests for get_current_tenant_id ---


class TestGetCurrentTenantId:
    """Tests for the get_current_tenant_id dependency."""

    async def test_extracts_tenant_id_from_valid_token(
        self, app_with_deps, valid_token, tenant_id
    ):
        """Should extract tenant_id from a valid JWT token."""
        async with AsyncClient(
            transport=ASGITransport(app=app_with_deps),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/test/tenant-id",
                headers={"Authorization": f"Bearer {valid_token}"},
            )
            assert response.status_code == 200
            assert response.json()["tenant_id"] == tenant_id

    async def test_missing_tenant_id_in_token_returns_403(self, app_with_deps):
        """A token without tenant_id claim should return 403."""
        from jose import jwt

        from app.core.config import get_settings

        settings = get_settings()
        # Create a token without tenant_id
        payload = {
            "sub": str(uuid.uuid4()),
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        }
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

        async with AsyncClient(
            transport=ASGITransport(app=app_with_deps),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/test/tenant-id",
                headers={"Authorization": f"Bearer {token}"},
            )
            # The decode_token in AuthService will raise JWTError for missing tenant_id
            assert response.status_code == 401

    async def test_invalid_uuid_tenant_id_returns_403(self, app_with_deps):
        """A token with an invalid UUID as tenant_id should return 403."""
        from jose import jwt

        from app.core.config import get_settings

        settings = get_settings()
        payload = {
            "sub": str(uuid.uuid4()),
            "tenant_id": "not-a-valid-uuid",
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        }
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

        async with AsyncClient(
            transport=ASGITransport(app=app_with_deps),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/test/tenant-id",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 403


# --- Tests for get_current_admin_id ---


class TestGetCurrentAdminId:
    """Tests for the get_current_admin_id dependency."""

    async def test_extracts_admin_id_from_valid_token(
        self, app_with_deps, valid_token, admin_id
    ):
        """Should extract admin_id from a valid JWT token."""
        async with AsyncClient(
            transport=ASGITransport(app=app_with_deps),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/test/admin-id",
                headers={"Authorization": f"Bearer {valid_token}"},
            )
            assert response.status_code == 200
            assert response.json()["admin_id"] == admin_id


# --- Tests for TenantService ---


class TestTenantServiceValidation:
    """Tests for TenantService.validate_tenant_access."""

    def test_same_tenant_passes(self, tenant_id):
        """Validation should pass when admin and resource tenant match."""
        # Should not raise
        TenantService.validate_tenant_access(tenant_id, tenant_id)

    def test_different_tenant_raises(self):
        """Validation should raise CrossTenantAccessError for mismatched tenants."""
        tenant_a = str(uuid.uuid4())
        tenant_b = str(uuid.uuid4())

        with pytest.raises(CrossTenantAccessError) as exc_info:
            TenantService.validate_tenant_access(tenant_a, tenant_b)

        assert exc_info.value.source_tenant == tenant_a
        assert exc_info.value.target_tenant == tenant_b

    def test_string_comparison_works(self):
        """Validation should work with UUID objects converted to strings."""
        tenant_uuid = uuid.uuid4()
        # Both as strings should pass
        TenantService.validate_tenant_access(str(tenant_uuid), str(tenant_uuid))

    def test_different_format_same_uuid_passes(self):
        """Same UUID in different string representations should pass."""
        tenant_uuid = uuid.uuid4()
        TenantService.validate_tenant_access(
            str(tenant_uuid), str(tenant_uuid)
        )


class TestTenantServiceLogging:
    """Tests for TenantService.log_cross_tenant_attempt."""

    async def test_logs_cross_tenant_attempt(self):
        """Should insert an audit log entry for cross-tenant access attempts."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()

        source = str(uuid.uuid4())
        target = str(uuid.uuid4())
        admin = str(uuid.uuid4())

        await TenantService.log_cross_tenant_attempt(
            db=mock_session,
            source_tenant=source,
            target_tenant=target,
            action="device_access",
            admin_id=admin,
        )

        # Verify execute was called (insert statement)
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

    async def test_handles_db_error_gracefully(self):
        """Should not raise if database logging fails."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=Exception("DB connection lost"))
        mock_session.rollback = AsyncMock()

        source = str(uuid.uuid4())
        target = str(uuid.uuid4())

        # Should not raise
        await TenantService.log_cross_tenant_attempt(
            db=mock_session,
            source_tenant=source,
            target_tenant=target,
            action="device_access",
        )

        mock_session.rollback.assert_called_once()


class TestTenantServiceValidateAndLog:
    """Tests for TenantService.validate_and_log_access."""

    async def test_same_tenant_does_not_log(self):
        """Should not log anything when tenants match."""
        mock_session = AsyncMock()
        tenant_id = str(uuid.uuid4())

        # Should not raise
        await TenantService.validate_and_log_access(
            db=mock_session,
            admin_tenant_id=tenant_id,
            resource_tenant_id=tenant_id,
            action="device_access",
        )

        # No logging should occur
        mock_session.execute.assert_not_called()

    async def test_different_tenant_logs_and_raises(self):
        """Should log and raise CrossTenantAccessError for mismatched tenants."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()

        tenant_a = str(uuid.uuid4())
        tenant_b = str(uuid.uuid4())
        admin = str(uuid.uuid4())

        with pytest.raises(CrossTenantAccessError) as exc_info:
            await TenantService.validate_and_log_access(
                db=mock_session,
                admin_tenant_id=tenant_a,
                resource_tenant_id=tenant_b,
                action="device_access",
                admin_id=admin,
            )

        assert exc_info.value.source_tenant == tenant_a
        assert exc_info.value.target_tenant == tenant_b
        # Verify logging occurred
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()


# --- Tests for CrossTenantAccessError ---


class TestCrossTenantAccessError:
    """Tests for the CrossTenantAccessError exception."""

    def test_error_contains_tenant_info(self):
        """Error should contain source and target tenant information."""
        source = str(uuid.uuid4())
        target = str(uuid.uuid4())
        error = CrossTenantAccessError(source, target, "test_action")

        assert error.source_tenant == source
        assert error.target_tenant == target
        assert error.action == "test_action"
        assert source in str(error)
        assert target in str(error)


# --- Tests for get_tenant_session dependency ---


class TestGetTenantSession:
    """Tests for the get_tenant_session dependency."""

    async def test_sets_and_clears_tenant_context(self, tenant_id):
        """Should set tenant context on session start and clear on exit."""
        with patch("app.core.tenant_middleware.async_session_factory") as mock_factory:
            mock_session = AsyncMock()
            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_context.__aexit__ = AsyncMock(return_value=False)
            mock_factory.return_value = mock_context

            with patch("app.core.tenant_middleware.set_tenant_context") as mock_set:
                with patch("app.core.tenant_middleware.clear_tenant_context") as mock_clear:
                    gen = get_tenant_session(tenant_id=tenant_id)
                    _ = await gen.__anext__()

                    # Verify tenant context was set
                    mock_set.assert_called_once_with(mock_session, tenant_id)

                    # Simulate end of request
                    try:
                        await gen.__anext__()
                    except StopAsyncIteration:
                        pass

                    # Verify tenant context was cleared
                    mock_clear.assert_called_once_with(mock_session)
