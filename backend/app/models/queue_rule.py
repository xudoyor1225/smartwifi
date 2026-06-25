"""QueueRule model - per-device bandwidth queue rules on MikroTik router."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.device import Device
    from app.models.tenant import Tenant


class QueueRule(UUIDPrimaryKeyMixin, Base):
    """Queue rule model for per-device bandwidth limits."""

    __tablename__ = "queue_rules"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    device_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    download_limit_mbps: Mapped[int] = mapped_column(Integer, nullable=False)
    upload_limit_mbps: Mapped[int] = mapped_column(Integer, nullable=False)
    mikrotik_queue_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    rule_type: Mapped[str] = mapped_column(String(20), nullable=False, default="global")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="queue_rules")
    device: Mapped["Device"] = relationship(back_populates="queue_rules")

    __table_args__ = (
        Index("ix_queue_rules_tenant_id", "tenant_id"),
        Index("ix_queue_rules_device_id", "device_id"),
        Index("ix_queue_rules_tenant_device", "tenant_id", "device_id"),
    )
