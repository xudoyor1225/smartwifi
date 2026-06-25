"""AnomalyAlert model - AI-detected traffic anomaly alerts."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.tenant import Tenant


class AnomalyAlert(UUIDPrimaryKeyMixin, Base):
    """Anomaly alert model for AI-detected traffic anomalies."""

    __tablename__ = "anomaly_alerts"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    severity: Mapped[str] = mapped_column(String(10), nullable=False)
    anomaly_type: Mapped[str] = mapped_column(String(50), nullable=False)
    observed_value: Mapped[float] = mapped_column(Float, nullable=False)
    baseline_value: Mapped[float] = mapped_column(Float, nullable=False)
    deviation_std: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="anomaly_alerts")

    __table_args__ = (
        Index("ix_anomaly_alerts_tenant_id", "tenant_id"),
        Index("ix_anomaly_alerts_tenant_detected", "tenant_id", "detected_at"),
        Index("ix_anomaly_alerts_severity", "tenant_id", "severity"),
    )
