"""Enum types shared across KeeperPilot database models."""

from enum import StrEnum


class RiskLevel(StrEnum):
    """User risk tolerance for agent decisions."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class WalletStatus(StrEnum):
    """Lifecycle state of a registered wallet."""

    ACTIVE = "active"
    REVOKED = "revoked"


class ExecutionStatus(StrEnum):
    """Lifecycle of an agent-triggered execution through KeeperHub."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUBMITTED = "submitted"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
