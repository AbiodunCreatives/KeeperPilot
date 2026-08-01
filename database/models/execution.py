"""Execution model: an agent decision that was submitted to the execution layer."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base, UUIDPrimaryKeyMixin, utcnow
from database.models.enums import ExecutionStatus

if TYPE_CHECKING:
    from database.models.user import User
    from database.models.wallet import Wallet


class Execution(UUIDPrimaryKeyMixin, Base):
    """A record of one action requested through KeeperHub.

    `status` tracks the full lifecycle; `transaction_hash` is the on-chain proof
    once submitted, `gas_used` is the estimated execution cost in USD.
    """

    __tablename__ = "executions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    wallet_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("wallets.id", ondelete="SET NULL"), index=True, nullable=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[ExecutionStatus] = mapped_column(
        Enum(ExecutionStatus, native_enum=False, length=16),
        default=ExecutionStatus.PENDING,
        nullable=False,
    )
    source_protocol: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_protocol: Mapped[str | None] = mapped_column(String(64), nullable=True)
    transaction_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)
    gas_used: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(38, 18), nullable=True)
    asset: Mapped[str | None] = mapped_column(String(16), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="executions")
    wallet: Mapped[Wallet | None] = relationship()

    def __repr__(self) -> str:
        return f"<Execution id={self.id} action={self.action} status={self.status}>"
