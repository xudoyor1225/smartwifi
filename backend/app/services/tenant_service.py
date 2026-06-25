"""Tenant isolation service for cross-tenant access validation and logging.

Provides utilities for validating tenant access boundaries and logging
any cross-tenant access attempts to the audit log for security monitoring.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


class CrossTenantAccessError(Exception):
    """Raised when a cross-tenant access attempt is detected."""

    def __init__(self, source_tenant: str, target_tenant: str, action: str):
        self.source_tenant = source_tenant
        self.target_tenant = target_tenant
        self.action = action
        super().__init__(
            f"Cross-tenant access denied: {source_tenant} attempted to access "
            f"{target_tenant} resources via {action}"
        )


class TenantService:
    """Service for tenant isolation enforcement and audit logging."""

    @staticmethod
    def validate_tenant_access(
        admin_tenant_id: str, resource_tenant_id: str
    ) -> None:
        """Validate that an admin is accessing resources within their own tenant.

        Compares the authenticated admin's tenant_id with the resource's tenant_id.
        Raises CrossTenantAccessError if they do not match.

        Args:
            admin_tenant_id: The tenant_id from the authenticated admin's JWT token.
            resource_tenant_id: The tenant_id of the resource being accessed.

        Raises:
            CrossTenantAccessError: If admin_tenant_id != resource_tenant_id.
        """
        if str(admin_tenant_id) != str(resource_tenant_id):
            raise CrossTenantAccessError(
                source_tenant=str(admin_tenant_id),
                target_tenant=str(resource_tenant_id),
                action="resource_access",
            )

    @staticmethod
    async def log_cross_tenant_attempt(
        db: AsyncSession,
        source_tenant: str,
        target_tenant: str,
        action: str,
        admin_id: str | None = None,
    ) -> None:
        """Log a cross-tenant access attempt to the audit log.

        Records the attempt with timestamp, source tenant, target tenant,
        and the action that was attempted. This is critical for security
        monitoring and compliance.

        Args:
            db: The async database session (should NOT have tenant context set,
                or use a separate admin session for logging).
            source_tenant: The tenant_id of the admin making the request.
            target_tenant: The tenant_id of the resource being accessed.
            action: Description of the action that was attempted.
            admin_id: Optional admin_id of the user making the attempt.
        """
        now = datetime.now(timezone.utc)

        logger.warning(
            "Cross-tenant access attempt detected: "
            "source_tenant=%s, target_tenant=%s, action=%s, timestamp=%s",
            source_tenant,
            target_tenant,
            action,
            now.isoformat(),
        )

        try:
            stmt = insert(AuditLog).values(
                tenant_id=source_tenant,
                admin_id=admin_id,
                action="cross_tenant_access_attempt",
                target_type="tenant",
                target_id=target_tenant,
                request_data={
                    "source_tenant": source_tenant,
                    "target_tenant": target_tenant,
                    "attempted_action": action,
                    "timestamp": now.isoformat(),
                },
                response_data={"result": "denied"},
                result="failure",
            )
            await db.execute(stmt)
            await db.commit()
        except Exception as e:
            # Log the error but don't let audit logging failure
            # prevent the security response from being sent
            logger.error(
                "Failed to log cross-tenant access attempt: %s", str(e)
            )
            await db.rollback()

    @staticmethod
    async def validate_and_log_access(
        db: AsyncSession,
        admin_tenant_id: str,
        resource_tenant_id: str,
        action: str,
        admin_id: str | None = None,
    ) -> None:
        """Validate tenant access and log any violations.

        Combines validation and logging into a single call for convenience.
        If a cross-tenant access is detected, it logs the attempt and raises
        CrossTenantAccessError.

        Args:
            db: The async database session for audit logging.
            admin_tenant_id: The tenant_id from the authenticated admin's JWT.
            resource_tenant_id: The tenant_id of the resource being accessed.
            action: Description of the action being attempted.
            admin_id: Optional admin_id of the user making the attempt.

        Raises:
            CrossTenantAccessError: If admin_tenant_id != resource_tenant_id.
        """
        if str(admin_tenant_id) != str(resource_tenant_id):
            await TenantService.log_cross_tenant_attempt(
                db=db,
                source_tenant=str(admin_tenant_id),
                target_tenant=str(resource_tenant_id),
                action=action,
                admin_id=admin_id,
            )
            raise CrossTenantAccessError(
                source_tenant=str(admin_tenant_id),
                target_tenant=str(resource_tenant_id),
                action=action,
            )
