"""Tenant isolation middleware and FastAPI dependencies.

Provides dependency injection for extracting tenant_id from JWT tokens
and creating tenant-scoped database sessions with RLS enforcement.
"""

import logging
import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import (
    async_session_factory,
    clear_tenant_context,
    set_tenant_context,
)
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

# HTTP Bearer token scheme for JWT extraction
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    """Dependency that extracts and validates the JWT token from the request.

    Returns the decoded token payload containing admin_id (sub) and tenant_id.

    Raises:
        HTTPException 401: If no token is provided or token is invalid/expired.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = AuthService.decode_token(credentials.credentials)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


async def get_current_tenant_id(
    token_payload: dict = Depends(get_current_admin),
) -> str:
    """Dependency that extracts the tenant_id from the authenticated JWT token.

    This is the primary dependency for tenant-scoped operations. It ensures
    the request is authenticated and returns the tenant_id as a string.

    Returns:
        The tenant_id UUID string from the JWT token.

    Raises:
        HTTPException 401: If the token is missing or invalid.
        HTTPException 403: If the token does not contain a valid tenant_id.
    """
    tenant_id = token_payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Validate tenant_id is a valid UUID format
    try:
        uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    return tenant_id


async def get_current_admin_id(
    token_payload: dict = Depends(get_current_admin),
) -> str:
    """Dependency that extracts the admin_id from the authenticated JWT token.

    Returns:
        The admin_id UUID string from the JWT token.

    Raises:
        HTTPException 401: If the token is missing or invalid.
    """
    admin_id = token_payload.get("sub")
    if not admin_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return admin_id


async def get_tenant_session(
    tenant_id: str = Depends(get_current_tenant_id),
) -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides a tenant-scoped async database session.

    Sets tenant context for query filtering.
    """
    async with async_session_factory() as session:
        try:
            await set_tenant_context(session, tenant_id)
            yield session
        finally:
            await clear_tenant_context(session)
            await session.close()
