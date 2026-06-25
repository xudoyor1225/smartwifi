"""FirewallRule model - individual rules applied to MikroTik router."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.blocking_scenario import BlockingScenario
    from app.models.tenant import Tenant


class FirewallRule(UUIDPrimaryKeyMixin, Base):
    """Firewall rule model representing a rule applied to the MikroTik router."""

    __tablename__ = "firewall_rules"

    scenario_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("blocking_scenarios.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    rule_type: Mapped[str] = mapped_column(String(20), nullable=False)
    pattern: Mapped[str] = mapped_column(String(512), nullable=False)
    mikrotik_rule_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    scenario: Mapped["BlockingScenario"] = relationship(back_populates="firewall_rules")
    tenant: Mapped["Tenant"] = relationship(back_populates="firewall_rules")

    __table_args__ = (
        Index("ix_firewall_rules_tenant_id", "tenant_id"),
        Index("ix_firewall_rules_scenario_id", "scenario_id"),
        Index("ix_firewall_rules_tenant_applied", "tenant_id", "is_applied"),
    )
