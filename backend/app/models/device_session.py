"""DeviceSession model - tracks individual device connection sessions."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.device import Device
    from app.models.tenant import Tenant


class DeviceSession(UUIDPrimaryKeyMixin, Base):
    """Device session model tracking connection sessions and data usage."""

    __tablename__ = "device_sessions"

    device_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    bytes_downloaded: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    bytes_uploaded: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    session_start: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    session_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    device: Mapped["Device"] = relationship(back_populates="sessions")
    tenant: Mapped["Tenant"] = relationship(back_populates="device_sessions")

    __table_args__ = (
        Index("ix_device_sessions_tenant_id", "tenant_id"),
        Index("ix_device_sessions_device_id", "device_id"),
    )
