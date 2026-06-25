"""Admin model - represents an authorized user who can access the dashboard."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.audit_log import AuditLog
    from app.models.report import Report
    from app.models.tenant import Tenant


class Admin(UUIDPrimaryKeyMixin, Base):
    """Admin model representing an authorized dashboard user."""

    __tablename__ = "admins"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="admins")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="admin")
    reports: Mapped[list["Report"]] = relationship(back_populates="admin")

    __table_args__ = (
        Index("ix_admins_tenant_id", "tenant_id"),
        Index("ix_admins_username_tenant", "tenant_id", "username", unique=True),
    )
