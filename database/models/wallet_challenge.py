"""WalletChallenge model: a single-use, expiring ownership proof."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base, UUIDPrimaryKeyMixin, utcnow

if TYPE_CHECKING:
    from database.models.user import User


class WalletChallenge(UUIDPrimaryKeyMixin, Base):
    """A signed-message challenge used to prove wallet ownership.

    The backend never sees a private key: the user signs ``message`` with their
    wallet and we recover the signer address from ``signature``. Challenges are
    single-use and expire after a short TTL.
    """

    __tablename__ = "wallet_challenges"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    address: Mapped[str] = mapped_column(String(42), nullable=False)
    chain: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(String(512), nullable=False)
    nonce: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    signature: Mapped[str | None] = mapped_column(String(132), nullable=True)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    user: Mapped[User | None] = relationship(back_populates="challenges")

    def __repr__(self) -> str:
        return f"<WalletChallenge id={self.id} nonce={self.nonce!r} used={self.used}>"
