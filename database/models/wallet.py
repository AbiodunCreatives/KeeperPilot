"""Wallet model: a verified on-chain address owned by a user."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base, UUIDPrimaryKeyMixin, utcnow
from database.models.enums import WalletStatus

if TYPE_CHECKING:
    from database.models.position import Position
    from database.models.user import User


class Wallet(UUIDPrimaryKeyMixin, Base):
    """An EVM address registered by a user.

    Addresses are stored in checksummed form. Private keys are never stored.
    """

    __tablename__ = "wallets"
    __table_args__ = (
        UniqueConstraint("user_id", "address", "chain", name="uq_wallet_user_address_chain"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    address: Mapped[str] = mapped_column(String(42), nullable=False)
    chain: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[WalletStatus] = mapped_column(
        Enum(WalletStatus, native_enum=False, length=16),
        default=WalletStatus.ACTIVE,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    user: Mapped[User] = relationship(back_populates="wallets")
    positions: Mapped[list[Position]] = relationship(
        back_populates="wallet",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Wallet id={self.id} chain={self.chain} address={self.address!r}>"
