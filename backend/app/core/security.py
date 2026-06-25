"""Security dependencies for FastAPI endpoints.

Provides the `get_current_admin` dependency that extracts and validates
JWT tokens from the Authorization header.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.admin import Admin
from app.services.auth_service import AuthService

# HTTP Bearer scheme for extracting tokens from Authorization header
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Admin:
    """FastAPI dependency that extracts and validates JWT from Authorization header.

    Extracts the Bearer token, decodes it, and returns the corresponding Admin.

    Args:
        credentials: The HTTP Bearer credentials from the Authorization header.
        db: The async database session.

    Returns:
        The authenticated Admin object.

    Raises:
        HTTPException: 401 if token is missing, invalid, expired, or admin not found.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = AuthService.decode_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    admin_id = payload.get("sub")
    if admin_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(
        select(Admin).where(Admin.id == admin_id, Admin.is_active == True)  # noqa: E712
    )
    admin = result.scalar_one_or_none()
    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return admin
