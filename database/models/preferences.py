"""UserPreferences model: the policy knobs that gate agent decisions."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base, UUIDPrimaryKeyMixin, utcnow
from database.models.enums import RiskLevel

if TYPE_CHECKING:
    from database.models.user import User


class UserPreferences(UUIDPrimaryKeyMixin, Base):
    """One-to-one preferences controlling what the agent may do for a user."""

    __tablename__ = "user_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    risk_level: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, native_enum=False, length=16),
        default=RiskLevel.MEDIUM,
        nullable=False,
    )
    preferred_assets: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    # Minimum yield improvement (percentage points) required before the agent acts.
    minimum_yield_difference: Mapped[float] = mapped_column(Float, default=2.0, nullable=False)
    # Maximum acceptable execution cost in USD.
    maximum_gas_cost: Mapped[float] = mapped_column(Float, default=5.0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    user: Mapped[User] = relationship(back_populates="preferences")

    def __repr__(self) -> str:
        return f"<UserPreferences user_id={self.user_id} risk={self.risk_level}>"
