"""RouterConfig model - stores MikroTik router connection configuration per tenant."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.tenant import Tenant


class RouterConfig(UUIDPrimaryKeyMixin, Base):
    """Router configuration model for MikroTik API connection details."""

    __tablename__ = "router_configs"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    api_port: Mapped[int] = mapped_column(Integer, nullable=False, default=8728)
    api_username: Mapped[str] = mapped_column(String(128), nullable=False)
    encrypted_password: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    encryption_iv: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    connection_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="disconnected"
    )
    last_connected: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="router_config")

    __table_args__ = (Index("ix_router_configs_tenant_id", "tenant_id"),)
