"""Position model: a user's holdings in a lending/DeFi protocol."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base, UUIDPrimaryKeyMixin, utcnow

if TYPE_CHECKING:
    from database.models.wallet import Wallet


class Position(UUIDPrimaryKeyMixin, Base):
    """An asset deposited into a protocol from a wallet.

    `apy` is the last-observed annual percentage yield for the position.
    """

    __tablename__ = "positions"
    __table_args__ = (
        UniqueConstraint(
            "wallet_id", "protocol", "asset", name="uq_position_wallet_protocol_asset"
        ),
    )

    wallet_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("wallets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    protocol: Mapped[str] = mapped_column(String(64), nullable=False)
    asset: Mapped[str] = mapped_column(String(16), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False, default=Decimal("0"))
    apy: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=Decimal("0"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    wallet: Mapped[Wallet] = relationship(back_populates="positions")

    def __repr__(self) -> str:
        return f"<Position id={self.id} {self.protocol}/{self.asset} apy={self.apy}%>"
