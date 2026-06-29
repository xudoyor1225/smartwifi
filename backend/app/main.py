"""FastAPI application factory for the Smart WiFi Dashboard backend.

Creates and configures the FastAPI application with CORS middleware,
GZip compression, security headers, router registration, and lifecycle
event handlers. Includes BackgroundStatCollector for optimized network
monitoring. Supports horizontal scaling via stateless request handling.
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown events.

    Startup order:
    1. Database tables (SQLite/PostgreSQL)
    2. Default data seeding
    3. Redis connection (optional)
    4. BackgroundStatCollector (network monitoring)

    Shutdown order (reverse):
    4. Stop stat collector
    3. Close Redis
    """
    from app.core.database import create_tables
    from app.core.redis import close_redis, init_redis
    from app.services.stat_collector import get_stat_collector

    startup_time = time.time()

    # Startup
    settings = get_settings()
    app.state.settings = settings

    # 1. Create SQLite tables and Seed data with retries
    max_retries = 5
    for attempt in range(max_retries):
        try:
            await create_tables()
            logger.info("Database tables created/verified")
            
            # 2. Seed default admin if not exists
            await _seed_default_data()
            break
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Database initialization failed (attempt {attempt + 1}/{max_retries}): {e}. Retrying in 3 seconds...")
                import asyncio
                await asyncio.sleep(3)
            else:
                logger.error(f"Failed to initialize database after {max_retries} attempts: {e}")
                raise

    # 3. Initialize Redis (optional - app works without it)
    try:
        await init_redis()
        logger.info("Redis connection established successfully")
    except Exception as e:
        logger.warning(
            "Redis connection failed during startup: %s. "
            "Application will operate without cache until Redis is available.",
            str(e),
        )

    # 4. Start background stat collector
    collector = get_stat_collector()
    await collector.start()
    app.state.stat_collector = collector

    elapsed = round((time.time() - startup_time) * 1000)
    logger.info("Application startup complete in %dms", elapsed)

    yield

    # Shutdown (reverse order)
    logger.info("Application shutdown initiated...")

    # 4. Stop stat collector
    await collector.stop()

    # 3. Close Redis
    await close_redis()

    logger.info("Application shutdown complete")


async def _seed_default_data() -> None:
    """Seed default tenant and admin user if database is empty."""
    import uuid
    from sqlalchemy import select
    from app.core.database import async_session_factory
    from app.models.admin import Admin
    from app.models.tenant import Tenant
    from app.models.blocking_scenario import BlockingScenario
    from app.services.auth_service import AuthService

    async with async_session_factory() as session:
        # Check if any tenant exists
        result = await session.execute(select(Tenant).limit(1))
        if result.scalar_one_or_none() is not None:
            return  # Already seeded

        # Create default tenant
        tenant_id = str(uuid.uuid4())
        tenant = Tenant(
            id=tenant_id,
            name="Default Network",
            subscription_tier="professional",
            is_active=True,
        )
        session.add(tenant)

        # Create default admin (admin / admin123)
        admin = Admin(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            username="admin",
            password_hash=AuthService.hash_password("admin123"),
            email="admin@smartwifi.local",
            is_active=True,
        )
        session.add(admin)

        # Create default blocking scenarios
        apps = [
            ("Instagram", "📷"),
            ("TikTok", "🎵"),
            ("Telegram", "✈️"),
            ("YouTube", "▶️"),
            ("Netflix", "🎬"),
        ]
        for app_name, _ in apps:
            scenario = BlockingScenario(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                app_name=app_name,
                version=1,
                is_active=False,
                rule_definitions={},
            )
            session.add(scenario)

        await session.commit()
        logger.info("Default data seeded: tenant='Default Network', admin='admin/admin123'")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance.

    Returns a fully configured FastAPI app with:
    - CORS middleware for frontend communication
    - All API routers registered under /api prefix
    - Health check endpoint for load balancer probes
    - Conditional docs/redoc based on debug mode
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Smart WiFi Dashboard API - Multi-tenant MikroTik router management platform",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    # === Middleware stack (order matters: last added = first executed) ===

    # CORS middleware for frontend origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # GZip compression for responses > 500 bytes
    app.add_middleware(GZipMiddleware, minimum_size=500)

    # Security headers (OWASP best practices)
    app.add_middleware(SecurityHeadersMiddleware)

    # Request timing + logging middleware
    app.add_middleware(RequestTimingMiddleware)

    # Register global exception handlers
    _register_exception_handlers(app)

    # Register API routers
    _register_routers(app)

    return app


def _register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers for structured error responses."""
    from fastapi import Request, HTTPException
    from fastapi.responses import JSONResponse

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle unhandled exceptions with a structured error response."""
        if isinstance(exc, HTTPException):
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers=exc.headers,
            )

        error_name = type(exc).__name__

        # Database connection errors
        if "connect" in error_name.lower() or "connection" in str(exc).lower():
            logger.warning(f"Database connection error: {exc}")
            return JSONResponse(
                status_code=503,
                content={
                    "code": "SERVICE_UNAVAILABLE",
                    "message": "Database service unavailable",
                    "resolution": "Please ensure PostgreSQL is running and accessible",
                },
            )

        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "code": "INTERNAL_ERROR",
                "message": "An internal error occurred",
                "resolution": "Please try again later",
            },
        )


def _register_routers(app: FastAPI) -> None:
    """Register all API route modules under the /api prefix."""
    from app.api.router import api_router

    app.include_router(api_router, prefix="/api")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add OWASP-recommended security headers to all responses.

    Headers prevent clickjacking, MIME sniffing, and XSS attacks.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """Log request duration and add timing header.

    Adds X-Process-Time header for client-side performance monitoring.
    Logs slow requests (>500ms) at WARNING level.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.time()
        response = await call_next(request)
        duration_ms = (time.time() - start) * 1000
        response.headers["X-Process-Time"] = f"{duration_ms:.1f}ms"

        if duration_ms > 500:
            logger.warning(
                "Slow request: %s %s took %.0fms",
                request.method,
                request.url.path,
                duration_ms,
            )

        return response


# Application instance for uvicorn
app = create_app()
