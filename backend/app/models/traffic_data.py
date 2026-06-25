"""TrafficData model - NetFlow traffic records collected from MikroTik router."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.tenant import Tenant


class TrafficData(UUIDPrimaryKeyMixin, Base):
    """Traffic data model for NetFlow records."""

    __tablename__ = "traffic_data"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    src_ip: Mapped[str] = mapped_column(String(45), nullable=False)
    dst_ip: Mapped[str] = mapped_column(String(45), nullable=False)
    src_port: Mapped[int] = mapped_column(Integer, nullable=False)
    dst_port: Mapped[int] = mapped_column(Integer, nullable=False)
    protocol: Mapped[str] = mapped_column(String(10), nullable=False)
    bytes_transferred: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    packets: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships (no back_populates to avoid circular issues)
    tenant: Mapped["Tenant"] = relationship()

    __table_args__ = (
        Index("ix_traffic_data_tenant_id", "tenant_id"),
        Index("ix_traffic_data_tenant_collected", "tenant_id", "collected_at"),
        Index("ix_traffic_data_collected_at", "collected_at"),
        # Covering index for traffic distribution by category (analytics query)
        Index("ix_traffic_data_tenant_category_time", "tenant_id", "category", "collected_at"),
    )
