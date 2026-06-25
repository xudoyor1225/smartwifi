"""Seed script to create a default admin user for development.

Run this script to create a test admin in the database:
    python seed_admin.py

Default credentials:
    Username: admin
    Password: admin123
"""

import asyncio
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.config import get_settings
from app.services.auth_service import AuthService

settings = get_settings()


async def seed():
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        # Check if tenant exists
        result = await session.execute(text("SELECT id FROM tenants LIMIT 1"))
        tenant = result.scalar_one_or_none()

        if tenant is None:
            # Create a default tenant
            tenant_id = str(uuid.uuid4())
            await session.execute(
                text(
                    "INSERT INTO tenants (id, name, subscription_tier, is_active) "
                    "VALUES (:id, :name, :tier, :active)"
                ),
                {
                    "id": tenant_id,
                    "name": "Default Tenant",
                    "tier": "professional",
                    "active": True,
                },
            )
            print(f"Created tenant: Default Tenant (ID: {tenant_id})")
        else:
            tenant_id = str(tenant)
            print(f"Using existing tenant (ID: {tenant_id})")

        # Check if admin exists
        result = await session.execute(
            text("SELECT id FROM admins WHERE username = :username"),
            {"username": "admin"},
        )
        existing_admin = result.scalar_one_or_none()

        if existing_admin:
            print("Admin user 'admin' already exists!")
        else:
            # Create admin user
            admin_id = str(uuid.uuid4())
            password_hash = AuthService.hash_password("admin123")

            await session.execute(
                text(
                    "INSERT INTO admins (id, tenant_id, username, password_hash, email, is_active) "
                    "VALUES (:id, :tenant_id, :username, :password_hash, :email, :active)"
                ),
                {
                    "id": admin_id,
                    "tenant_id": tenant_id,
                    "username": "admin",
                    "password_hash": password_hash,
                    "email": "admin@smartwifi.local",
                    "active": True,
                },
            )
            print(f"Created admin user:")
            print(f"  Username: admin")
            print(f"  Password: admin123")
            print(f"  Admin ID: {admin_id}")

        await session.commit()

    await engine.dispose()
    print("\nDone! You can now login with: admin / admin123")


if __name__ == "__main__":
    asyncio.run(seed())
