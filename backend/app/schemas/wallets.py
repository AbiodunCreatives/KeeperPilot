"""Pydantic schemas for wallet management."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from database.models.enums import WalletStatus


class ChallengeRequest(BaseModel):
    """Request an ownership challenge for an address."""

    address: str = Field(min_length=42, max_length=42)
    chain: str = Field(min_length=1, max_length=32)


class ChallengeResponse(BaseModel):
    """The message to sign. Only ever contains the public address."""

    challenge_id: uuid.UUID
    address: str
    chain: str
    nonce: str
    message: str
    expires_at: datetime


class ConnectRequest(BaseModel):
    """Submit a signed message to prove wallet ownership."""

    challenge_id: uuid.UUID
    address: str = Field(min_length=42, max_length=42)
    chain: str = Field(min_length=1, max_length=32)
    signature: str = Field(min_length=130, max_length=132)


class WalletResponse(BaseModel):
    """A registered wallet. Private keys never leave the user's wallet."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    address: str
    chain: str
    status: WalletStatus
    created_at: datetime


class WalletRevokeResponse(BaseModel):
    """Result of revoking a wallet."""

    id: uuid.UUID
    status: WalletStatus
