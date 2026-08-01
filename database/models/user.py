"""User account model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base, UUIDPrimaryKeyMixin, utcnow

if TYPE_CHECKING:
    from database.models.audit_log import AuditLog
    from database.models.execution import Execution
    from database.models.preferences import UserPreferences
    from database.models.wallet import Wallet
    from database.models.wallet_challenge import WalletChallenge


class User(UUIDPrimaryKeyMixin, Base):
    """An account owner. Wallets, preferences, executions, and audit events hang off a user."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    preferences: Mapped[UserPreferences] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    wallets: Mapped[list[Wallet]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    executions: Mapped[list[Execution]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    audit_logs: Mapped[list[AuditLog]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    challenges: Mapped[list[WalletChallenge]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"
