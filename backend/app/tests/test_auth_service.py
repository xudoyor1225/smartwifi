"""Tests for the authentication service.

Tests cover password hashing, JWT token generation/decoding,
input validation, and API endpoint behavior.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.core.config import get_settings
from app.services.auth_service import AuthService

settings = get_settings()


class TestPasswordHashing:
    """Tests for bcrypt password hashing and verification."""

    def test_hash_password_returns_bcrypt_hash(self):
        """Hash should be a valid bcrypt string."""
        hashed = AuthService.hash_password("testpassword123")
        assert hashed.startswith("$2b$12$") or hashed.startswith("$2a$12$")

    def test_hash_password_different_each_time(self):
        """Two hashes of the same password should differ (unique salt)."""
        hash1 = AuthService.hash_password("samepassword")
        hash2 = AuthService.hash_password("samepassword")
        assert hash1 != hash2

    def test_verify_password_correct(self):
        """Correct password should verify successfully."""
        password = "my_secure_password"
        hashed = AuthService.hash_password(password)
        assert AuthService.verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Incorrect password should fail verification."""
        hashed = AuthService.hash_password("correct_password")
        assert AuthService.verify_password("wrong_password", hashed) is False

    def test_verify_password_empty_string(self):
        """Empty password should not match a non-empty hash."""
        hashed = AuthService.hash_password("notempty")
        assert AuthService.verify_password("", hashed) is False

    def test_hash_password_empty_string(self):
        """Empty string can be hashed (edge case)."""
        hashed = AuthService.hash_password("")
        assert hashed is not None
        assert AuthService.verify_password("", hashed) is True


class TestJWTTokens:
    """Tests for JWT token creation and decoding."""

    def test_create_token_returns_string(self):
        """Token should be a non-empty string."""
        token = AuthService.create_token("admin-uuid-123", "tenant-uuid-456")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_token_contains_correct_claims(self):
        """Token payload should contain sub, tenant_id, iat, exp."""
        admin_id = "admin-uuid-123"
        tenant_id = "tenant-uuid-456"
        token = AuthService.create_token(admin_id, tenant_id)
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        assert payload["sub"] == admin_id
        assert payload["tenant_id"] == tenant_id
        assert "iat" in payload
        assert "exp" in payload

    def test_create_token_expiry_is_30_minutes(self):
        """Token should expire approximately 30 minutes from creation."""
        token = AuthService.create_token("admin-id", "tenant-id")
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        iat = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        diff = exp - iat
        assert timedelta(minutes=29) <= diff <= timedelta(minutes=31)

    def test_decode_token_valid(self):
        """Valid token should decode successfully."""
        token = AuthService.create_token("admin-id", "tenant-id")
        payload = AuthService.decode_token(token)
        assert payload["sub"] == "admin-id"
        assert payload["tenant_id"] == "tenant-id"

    def test_decode_token_expired(self):
        """Expired token should raise JWTError."""
        from jose import JWTError

        # Create a token that's already expired
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "admin-id",
            "tenant_id": "tenant-id",
            "iat": now - timedelta(hours=2),
            "exp": now - timedelta(hours=1),
        }
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
        with pytest.raises(JWTError):
            AuthService.decode_token(token)

    def test_decode_token_invalid_signature(self):
        """Token with wrong secret should raise JWTError."""
        from jose import JWTError

        now = datetime.now(timezone.utc)
        payload = {
            "sub": "admin-id",
            "tenant_id": "tenant-id",
            "iat": now,
            "exp": now + timedelta(minutes=30),
        }
        token = jwt.encode(payload, "wrong-secret-key", algorithm=settings.jwt_algorithm)
        with pytest.raises(JWTError):
            AuthService.decode_token(token)

    def test_decode_token_missing_sub_claim(self):
        """Token without 'sub' claim should raise JWTError."""
        from jose import JWTError

        now = datetime.now(timezone.utc)
        payload = {
            "tenant_id": "tenant-id",
            "iat": now,
            "exp": now + timedelta(minutes=30),
        }
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
        with pytest.raises(JWTError):
            AuthService.decode_token(token)

    def test_decode_token_missing_tenant_id_claim(self):
        """Token without 'tenant_id' claim should raise JWTError."""
        from jose import JWTError

        now = datetime.now(timezone.utc)
        payload = {
            "sub": "admin-id",
            "iat": now,
            "exp": now + timedelta(minutes=30),
        }
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
        with pytest.raises(JWTError):
            AuthService.decode_token(token)


class TestLoginEndpoint:
    """Tests for the POST /api/auth/login endpoint.

    Uses dependency overrides to mock the database layer so tests
    can run without a real PostgreSQL connection.
    """

    @pytest.fixture
    def mock_admin(self):
        """Create a mock Admin object for testing."""
        admin = MagicMock()
        admin.id = uuid.uuid4()
        admin.tenant_id = uuid.uuid4()
        admin.username = "testadmin"
        admin.password_hash = AuthService.hash_password("correctpassword")
        admin.is_active = True
        admin.last_login = None
        return admin

    @pytest.fixture
    async def auth_client(self, app, mock_admin):
        """Create a test client with mocked database and Redis dependencies."""
        from app.core.database import get_db

        # Mock the database session
        mock_session = AsyncMock()

        # By default, authenticate returns None (invalid credentials)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        mock_session.commit = AsyncMock()
        mock_session.add = MagicMock()

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        # Mock the rate limiter
        mock_limiter = AsyncMock()
        mock_limiter.check_brute_force = AsyncMock()
        mock_limiter.check_rate_limit = AsyncMock()
        mock_limiter.record_failed_attempt = AsyncMock()
        mock_limiter.record_success = AsyncMock()

        with patch("app.api.auth.get_limiter", return_value=mock_limiter):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                yield ac, mock_session, mock_admin

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_login_invalid_credentials_returns_401(self, auth_client):
        """Invalid credentials should return 401 with generic message."""
        client, mock_session, _ = auth_client
        response = await client.post(
            "/api/auth/login",
            json={"username": "nonexistent", "password": "wrongpass"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid credentials"

    @pytest.mark.asyncio
    async def test_login_wrong_password_same_error(self, auth_client):
        """Wrong password should return same error as wrong username."""
        client, mock_session, mock_admin = auth_client
        # Admin exists but password is wrong
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_admin
        mock_session.execute.return_value = mock_result

        response = await client.post(
            "/api/auth/login",
            json={"username": "testadmin", "password": "wrongpassword"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid credentials"

    @pytest.mark.asyncio
    async def test_login_success_returns_token(self, auth_client):
        """Valid credentials should return a JWT token."""
        client, mock_session, mock_admin = auth_client
        # Admin exists with correct password
        mock_admin.password_hash = AuthService.hash_password("correctpassword")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_admin
        mock_session.execute.return_value = mock_result

        response = await client.post(
            "/api/auth/login",
            json={"username": "testadmin", "password": "correctpassword"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

        # Verify the token is valid
        payload = AuthService.decode_token(data["access_token"])
        assert payload["sub"] == str(mock_admin.id)
        assert payload["tenant_id"] == str(mock_admin.tenant_id)

    @pytest.mark.asyncio
    async def test_login_username_too_long_returns_422(self, auth_client):
        """Username exceeding 64 chars should be rejected with 422."""
        client, _, _ = auth_client
        response = await client.post(
            "/api/auth/login",
            json={"username": "a" * 65, "password": "password123"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_login_password_too_long_returns_422(self, auth_client):
        """Password exceeding 128 chars should be rejected with 422."""
        client, _, _ = auth_client
        response = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "p" * 129},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_login_username_at_max_length_accepted(self, auth_client):
        """Username at exactly 64 chars should pass validation (but may fail auth)."""
        client, _, _ = auth_client
        response = await client.post(
            "/api/auth/login",
            json={"username": "a" * 64, "password": "password123"},
        )
        # Should not be 422 (validation error) - it should be 401 (auth failure)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_password_at_max_length_accepted(self, auth_client):
        """Password at exactly 128 chars should pass validation (but may fail auth)."""
        client, _, _ = auth_client
        response = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "p" * 128},
        )
        # Should not be 422 (validation error) - it should be 401 (auth failure)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_missing_username_returns_422(self, auth_client):
        """Missing username field should return 422."""
        client, _, _ = auth_client
        response = await client.post(
            "/api/auth/login",
            json={"password": "password123"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_login_missing_password_returns_422(self, auth_client):
        """Missing password field should return 422."""
        client, _, _ = auth_client
        response = await client.post(
            "/api/auth/login",
            json={"username": "admin"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_login_error_uniformity(self, auth_client):
        """Error for wrong username and wrong password must be identical."""
        client, mock_session, mock_admin = auth_client

        # First: nonexistent user (returns None from DB)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        resp1 = await client.post(
            "/api/auth/login",
            json={"username": "nonexistent", "password": "anypass"},
        )

        # Second: existing user, wrong password
        mock_admin.password_hash = AuthService.hash_password("realpassword")
        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = mock_admin
        mock_session.execute.return_value = mock_result2

        resp2 = await client.post(
            "/api/auth/login",
            json={"username": "testadmin", "password": "wrongpassword"},
        )

        # Both should have identical error structure
        assert resp1.status_code == resp2.status_code == 401
        assert resp1.json()["detail"] == resp2.json()["detail"] == "Invalid credentials"


class TestSessionEndpoint:
    """Tests for the GET /api/auth/session endpoint."""

    @pytest.fixture
    async def session_client(self, app):
        """Create a test client with mocked database for session tests."""
        from app.core.database import get_db

        mock_session = AsyncMock()

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac, mock_session

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_session_without_token_returns_401(self, session_client):
        """Session endpoint without token should return 401."""
        client, _ = session_client
        response = await client.get("/api/auth/session")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_session_with_invalid_token_returns_401(self, session_client):
        """Session endpoint with invalid token should return 401."""
        client, _ = session_client
        response = await client.get(
            "/api/auth/session",
            headers={"Authorization": "Bearer invalid-token-here"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_session_with_valid_token_returns_session(self, session_client):
        """Session endpoint with valid token should return session info."""
        client, mock_session = session_client

        # Create a valid admin and token
        admin_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        token = AuthService.create_token(str(admin_id), str(tenant_id))

        # Mock the DB lookup for get_current_admin
        mock_admin = MagicMock()
        mock_admin.id = admin_id
        mock_admin.tenant_id = tenant_id
        mock_admin.username = "testadmin"
        mock_admin.is_active = True

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_admin
        mock_session.execute.return_value = mock_result

        response = await client.get(
            "/api/auth/session",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["admin_id"] == str(admin_id)
        assert data["tenant_id"] == str(tenant_id)
        assert data["username"] == "testadmin"
        assert "expires_at" in data


class TestLogoutEndpoint:
    """Tests for the POST /api/auth/logout endpoint."""

    @pytest.fixture
    async def logout_client(self, app):
        """Create a test client with mocked database for logout tests."""
        from app.core.database import get_db

        mock_session = AsyncMock()

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac, mock_session

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_logout_without_token_returns_401(self, logout_client):
        """Logout without token should return 401."""
        client, _ = logout_client
        response = await client.post("/api/auth/logout")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_logout_with_invalid_token_returns_401(self, logout_client):
        """Logout with invalid token should return 401."""
        client, _ = logout_client
        response = await client.post(
            "/api/auth/logout",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_logout_with_valid_token_succeeds(self, logout_client):
        """Logout with valid token should return success message."""
        client, mock_session = logout_client

        # Create a valid admin and token
        admin_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        token = AuthService.create_token(str(admin_id), str(tenant_id))

        # Mock the DB lookup for get_current_admin
        mock_admin = MagicMock()
        mock_admin.id = admin_id
        mock_admin.tenant_id = tenant_id
        mock_admin.username = "testadmin"
        mock_admin.is_active = True

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_admin
        mock_session.execute.return_value = mock_result

        response = await client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["message"] == "Successfully logged out"
