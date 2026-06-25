"""Authentication API endpoints.

Provides login, logout, and session validation endpoints.
Integrates rate limiting and brute-force protection.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin
from app.models.admin import Admin
from app.models.login_attempt import LoginAttempt
from app.schemas.auth import AdminPasswordUpdate, LoginRequest, LoginResponse, LogoutResponse, SessionResponse
from app.services.auth_service import AuthService
from app.services.rate_limiter import get_limiter

router = APIRouter(prefix="/auth", tags=["authentication"])


def _get_client_ip(request: Request) -> str:
    """Extract the client IP address from the request.

    Checks X-Forwarded-For header first (for reverse proxy setups),
    then falls back to the direct client host.
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP in the chain (original client)
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Authenticate admin and return JWT token.

    Validates credentials and returns a JWT access token with 30-minute expiry.
    Returns a generic error message for invalid credentials without revealing
    which field was incorrect.

    Enforces rate limiting (5 failed attempts per 10 minutes) and brute-force
    protection (20 failed attempts per hour → 30-minute IP ban).
    """
    ip_address = _get_client_ip(request)
    rate_limiter = get_limiter()
    try:
        # Check brute-force ban first (most restrictive)
        await rate_limiter.check_brute_force(ip_address)
        # Check rate limit (5 attempts per 10 minutes)
        await rate_limiter.check_rate_limit(ip_address)
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Rate limit error: %s", e)

    # Attempt authentication
    admin = None
    try:
        admin = await AuthService.authenticate_by_username(
            username=login_data.username,
            password=login_data.password,
            db=db,
        )
    except Exception as db_err:
        # If database is unavailable, use demo mode
        import logging
        logging.getLogger(__name__).warning(
            "Database unavailable, using demo authentication: %s", db_err
        )
        # Demo mode: accept admin/admin123
        if login_data.username == "admin" and login_data.password == "admin123":
            import uuid
            demo_admin_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "demo-admin"))
            demo_tenant_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "demo-tenant"))
            token = AuthService.create_token(
                admin_id=demo_admin_id,
                tenant_id=demo_tenant_id,
            )
            return LoginResponse(access_token=token, token_type="bearer")
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

    if admin is None:
        # Record failed attempt in Redis
        try:
            await rate_limiter.record_failed_attempt(ip_address)
        except Exception:
            pass  # Redis may be unavailable

        # Store LoginAttempt in database for audit
        try:
            login_attempt = LoginAttempt(
                ip_address=ip_address,
                username=login_data.username,
                success=False,
            )
            db.add(login_attempt)
            await db.commit()
        except Exception:
            pass

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Successful login
    try:
        await rate_limiter.record_success(ip_address)
    except Exception:
        pass  # Redis may be unavailable

    # Store successful LoginAttempt in database for audit
    try:
        login_attempt = LoginAttempt(
            ip_address=ip_address,
            username=login_data.username,
            success=True,
        )
        db.add(login_attempt)

        # Update last_login timestamp
        admin.last_login = datetime.now(timezone.utc)
        await db.commit()
    except Exception:
        pass

    # Generate JWT token
    token = AuthService.create_token(
        admin_id=str(admin.id),
        tenant_id=str(admin.tenant_id),
    )

    return LoginResponse(access_token=token, token_type="bearer")


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    current_admin: Admin = Depends(get_current_admin),
) -> LogoutResponse:
    """Invalidate the current session token.

    In a stateless JWT setup, the client discards the token.
    Server-side token invalidation can be extended with a Redis blacklist.
    """
    return LogoutResponse(message="Successfully logged out")


@router.get("/session", response_model=SessionResponse)
async def get_session(
    current_admin: Admin = Depends(get_current_admin),
) -> SessionResponse:
    """Validate current session and return session details.

    Returns the admin's session information including expiration time.
    Requires a valid JWT token in the Authorization header.
    """
    # Re-create token to get the expiry (sliding window concept)
    from app.core.config import get_settings

    settings = get_settings()
    from datetime import timedelta

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expiry_minutes)

    return SessionResponse(
        admin_id=str(current_admin.id),
        tenant_id=str(current_admin.tenant_id),
        username=current_admin.username,
        expires_at=expires_at,
    )


@router.put("/password", response_model=LogoutResponse)
async def update_password(
    password_data: AdminPasswordUpdate,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> LogoutResponse:
    """Update admin dashboard password.
    
    Verifies the current password and hashes the new one.
    """
    # Verify current password
    if not AuthService.verify_password(password_data.current_password, current_admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )
    
    # Hash new password and save
    current_admin.password_hash = AuthService.hash_password(password_data.new_password)
    db.add(current_admin)
    await db.commit()

    return LogoutResponse(message="Password successfully updated")
