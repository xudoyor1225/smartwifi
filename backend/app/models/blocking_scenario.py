"""BlockingScenario model - predefined rule sets for blocking applications."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.firewall_rule import FirewallRule
    from app.models.tenant import Tenant


class BlockingScenario(UUIDPrimaryKeyMixin, Base):
    """Blocking scenario model with versioned rule definitions."""

    __tablename__ = "blocking_scenarios"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    app_name: Mapped[str] = mapped_column(String(100), nullable=False)
    app_logo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rule_definitions: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="blocking_scenarios")
    firewall_rules: Mapped[list["FirewallRule"]] = relationship(back_populates="scenario")

    __table_args__ = (
        Index("ix_blocking_scenarios_tenant_id", "tenant_id"),
        Index("ix_blocking_scenarios_app", "tenant_id", "app_name"),
    )
