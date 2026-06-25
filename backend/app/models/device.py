"""Device model - represents a WiFi client connected to the MikroTik router."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.device_session import DeviceSession
    from app.models.queue_rule import QueueRule
    from app.models.tenant import Tenant


class Device(UUIDPrimaryKeyMixin, Base):
    """Device model representing a WiFi client device."""

    __tablename__ = "devices"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    mac_address: Mapped[str] = mapped_column(String(17), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    manufacturer_logo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    is_vip: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    total_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    first_seen: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="devices")
    queue_rules: Mapped[list["QueueRule"]] = relationship(back_populates="device")
    sessions: Mapped[list["DeviceSession"]] = relationship(back_populates="device")

    __table_args__ = (
        Index("ix_devices_tenant_id", "tenant_id"),
        Index("ix_devices_mac_tenant", "tenant_id", "mac_address", unique=True),
        Index("ix_devices_status", "tenant_id", "status"),
        # Covering index for device listing (ORDER BY last_seen DESC)
        Index("ix_devices_tenant_last_seen", "tenant_id", "last_seen"),
        # VIP device lookup (bandwidth exemption queries)
        Index("ix_devices_tenant_vip", "tenant_id", "is_vip"),
    )
