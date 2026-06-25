"""BandwidthConfig model - global bandwidth settings per tenant."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.tenant import Tenant


class BandwidthConfig(UUIDPrimaryKeyMixin, Base):
    """Bandwidth configuration model for global tenant bandwidth limits."""

    __tablename__ = "bandwidth_configs"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    global_download_mbps: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    global_upload_mbps: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    uplink_capacity_mbps: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="bandwidth_config")

    __table_args__ = (Index("ix_bandwidth_configs_tenant_id", "tenant_id"),)
