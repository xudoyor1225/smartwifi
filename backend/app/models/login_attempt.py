"""LoginAttempt model - tracks authentication attempts for rate limiting."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class LoginAttempt(UUIDPrimaryKeyMixin, Base):
    """Login attempt model for tracking authentication attempts and rate limiting."""

    __tablename__ = "login_attempts"

    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_login_attempts_ip_address", "ip_address"),
        Index("ix_login_attempts_attempted_at", "attempted_at"),
    )
