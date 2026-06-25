"""Tenant model - represents a business/organization using the SaaS platform."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.admin import Admin
    from app.models.anomaly_alert import AnomalyAlert
    from app.models.bandwidth_config import BandwidthConfig
    from app.models.blocking_scenario import BlockingScenario
    from app.models.device import Device
    from app.models.device_session import DeviceSession
    from app.models.firewall_rule import FirewallRule
    from app.models.queue_rule import QueueRule
    from app.models.report import Report
    from app.models.router_config import RouterConfig


class Tenant(UUIDPrimaryKeyMixin, Base):
    """Tenant model representing a business using the platform."""

    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    subscription_tier: Mapped[str] = mapped_column(
        String(50), nullable=False, default="basic"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    admins: Mapped[list["Admin"]] = relationship(back_populates="tenant")
    router_config: Mapped["RouterConfig | None"] = relationship(
        back_populates="tenant", uselist=False
    )
    devices: Mapped[list["Device"]] = relationship(back_populates="tenant")
    blocking_scenarios: Mapped[list["BlockingScenario"]] = relationship(
        back_populates="tenant"
    )
    firewall_rules: Mapped[list["FirewallRule"]] = relationship(
        back_populates="tenant"
    )
    bandwidth_config: Mapped["BandwidthConfig | None"] = relationship(
        back_populates="tenant", uselist=False
    )
    queue_rules: Mapped[list["QueueRule"]] = relationship(back_populates="tenant")
    anomaly_alerts: Mapped[list["AnomalyAlert"]] = relationship(
        back_populates="tenant"
    )
    device_sessions: Mapped[list["DeviceSession"]] = relationship(
        back_populates="tenant"
    )
    reports: Mapped[list["Report"]] = relationship(back_populates="tenant")
