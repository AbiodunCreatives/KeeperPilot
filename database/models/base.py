"""Declarative base and shared column mixins."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    """Timezone-aware UTC timestamp used as the default for datetime columns."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Root declarative base for all KeeperPilot ORM models."""


class UUIDPrimaryKeyMixin:
    """UUID primary key with a client-side default (portable across dialects)."""

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
