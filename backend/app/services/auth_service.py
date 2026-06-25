"""Authentication service handling login, logout, and session management.

Provides bcrypt password hashing (cost factor 12), JWT token generation
with 30-minute sliding expiry, and credential verification.
"""

from datetime import datetime, timedelta, timezone

import asyncio
import bcrypt
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.admin import Admin

settings = get_settings()

# (Passlib removed)

class AuthService:
    """Service for authentication operations."""

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt.

        Args:
            password: The plain text password to hash.

        Returns:
            The bcrypt hash string.
        """
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a plain password against a bcrypt hash.

        Args:
            plain_password: The plain text password to verify.
            hashed_password: The bcrypt hash to verify against.

        Returns:
            True if the password matches, False otherwise.
        """
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )

    @staticmethod
    def create_token(admin_id: str, tenant_id: str) -> str:
        """Create a JWT token with 30-minute expiry.

        Args:
            admin_id: The UUID of the admin as a string.
            tenant_id: The UUID of the tenant as a string.

        Returns:
            The encoded JWT token string.
        """
        now = datetime.now(timezone.utc)
        expire = now + timedelta(minutes=settings.jwt_expiry_minutes)
        payload = {
            "sub": admin_id,
            "tenant_id": tenant_id,
            "iat": now,
            "exp": expire,
        }
        return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    @staticmethod
    def decode_token(token: str) -> dict:
        """Decode and validate a JWT token.

        Args:
            token: The JWT token string to decode.

        Returns:
            The decoded payload dictionary containing sub, tenant_id, iat, exp.

        Raises:
            JWTError: If the token is invalid, expired, or malformed.
        """
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        if "sub" not in payload or "tenant_id" not in payload:
            raise JWTError("Token missing required claims")
        return payload

    @staticmethod
    async def authenticate(
        username: str, password: str, tenant_id: str, db: AsyncSession
    ) -> Admin | None:
        """Authenticate an admin by username, password, and tenant.

        Args:
            username: The admin's username.
            password: The plain text password.
            tenant_id: The tenant UUID string to scope the lookup.
            db: The async database session.

        Returns:
            The Admin object if credentials are valid, None otherwise.
        """
        result = await db.execute(
            select(Admin).where(
                Admin.username == username,
                Admin.tenant_id == tenant_id,
                Admin.is_active == True,  # noqa: E712
            )
        )
        admin = result.scalar_one_or_none()
        if admin is None:
            return None
            
        # Run bcrypt in a thread pool to avoid blocking the asyncio event loop
        is_valid = await asyncio.to_thread(
            AuthService.verify_password, password, admin.password_hash
        )
        if not is_valid:
            return None
        return admin

    @staticmethod
    async def authenticate_by_username(
        username: str, password: str, db: AsyncSession
    ) -> Admin | None:
        """Authenticate an admin by username and password (tenant-agnostic lookup).

        Used for login where tenant_id is not yet known. Looks up the admin
        by username alone and verifies the password.

        Args:
            username: The admin's username.
            password: The plain text password.
            db: The async database session.

        Returns:
            The Admin object if credentials are valid, None otherwise.
        """
        result = await db.execute(
            select(Admin).where(
                Admin.username == username,
                Admin.is_active == True,  # noqa: E712
            )
        )
        admin = result.scalar_one_or_none()
        if admin is None:
            return None
            
        # Run bcrypt in a thread pool to avoid blocking the asyncio event loop
        is_valid = await asyncio.to_thread(
            AuthService.verify_password, password, admin.password_hash
        )
        if not is_valid:
            return None
        return admin
