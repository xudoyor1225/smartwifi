"""Report model - generated PDF/Excel reports for analytics export."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.admin import Admin
    from app.models.tenant import Tenant


class Report(UUIDPrimaryKeyMixin, Base):
    """Report model for generated analytics exports."""

    __tablename__ = "reports"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    admin_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("admins.id", ondelete="CASCADE"), nullable=False
    )
    format: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="reports")
    admin: Mapped["Admin"] = relationship(back_populates="reports")

    __table_args__ = (
        Index("ix_reports_tenant_id", "tenant_id"),
        Index("ix_reports_admin_id", "admin_id"),
    )
