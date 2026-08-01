"""Pydantic schemas for executions."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from database.models import ExecutionStatus


class ExecutionRequest(BaseModel):
    """Point at a position and a target venue; the server re-verifies policy."""

    wallet_id: uuid.UUID
    asset: str = Field(min_length=1, max_length=16)
    source_protocol: str = Field(min_length=1, max_length=64)
    target_protocol: str = Field(min_length=1, max_length=64)


class ExecutionResponse(BaseModel):
    """An execution record with its lifecycle state."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    wallet_id: uuid.UUID | None
    action: str
    status: ExecutionStatus
    source_protocol: str | None
    target_protocol: str | None
    transaction_hash: str | None
    gas_used: Decimal | None
    amount: Decimal | None
    asset: str | None
    reason: str | None
    created_at: datetime
    completed_at: datetime | None
