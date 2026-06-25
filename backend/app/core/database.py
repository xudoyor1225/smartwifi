"""Database session and engine configuration.

Provides async SQLAlchemy engine and session factory.
Uses SQLite with aiosqlite for local development (no external DB needed).
Tenant isolation is handled at the application level via query filtering.
"""

from collections.abc import AsyncGenerator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

# Build engine kwargs based on database type
_engine_kwargs: dict = {
    "echo": settings.debug,
}

# SQLite doesn't support pool_size/max_overflow
if not settings.database_url.startswith("sqlite"):
    _engine_kwargs["pool_size"] = settings.db_pool_size
    _engine_kwargs["max_overflow"] = settings.db_max_overflow
    _engine_kwargs["pool_timeout"] = settings.db_pool_timeout

# Async engine
engine = create_async_engine(settings.database_url, **_engine_kwargs)

# Enable WAL mode, foreign keys, and performance PRAGMAs for SQLite
if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        # WAL mode — concurrent reads during writes
        cursor.execute("PRAGMA journal_mode=WAL")
        # Foreign keys enforcement
        cursor.execute("PRAGMA foreign_keys=ON")
        # NORMAL sync — 2x faster writes, safe with WAL mode
        cursor.execute("PRAGMA synchronous=NORMAL")
        # 64MB page cache (negative = KB)
        cursor.execute("PRAGMA cache_size=-65536")
        # Temp tables in memory (faster JOINs, sorts)
        cursor.execute("PRAGMA temp_store=MEMORY")
        # Memory-mapped I/O — 256MB (reduces syscalls)
        cursor.execute("PRAGMA mmap_size=268435456")
        cursor.close()

# Session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def set_tenant_context(session: AsyncSession, tenant_id: str) -> None:
    """Set the current tenant context.

    For SQLite, this is a no-op since we handle tenant isolation
    at the application level via query filtering.
    For PostgreSQL, this sets the session variable for RLS.
    """
    # Store tenant_id in session info for application-level filtering
    session.info["tenant_id"] = str(tenant_id)
    if get_settings().database_url.startswith("postgresql"):
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
            {"tenant_id": str(tenant_id)}
        )


async def clear_tenant_context(session: AsyncSession) -> None:
    """Clear the current tenant context."""
    session.info.pop("tenant_id", None)
    if get_settings().database_url.startswith("postgresql"):
        await session.execute(text("SELECT set_config('app.current_tenant_id', '', false)"))


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_tenant_db(tenant_id: str) -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides a tenant-scoped async database session."""
    async with async_session_factory() as session:
        try:
            await set_tenant_context(session, tenant_id)
            yield session
        finally:
            await clear_tenant_context(session)
            await session.close()


async def create_tables() -> None:
    """Create all database tables. Used for SQLite initialization."""
    from app.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables() -> None:
    """Drop all database tables. Used for testing."""
    from app.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
