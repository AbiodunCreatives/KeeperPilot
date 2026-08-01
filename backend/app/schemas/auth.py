"""Pydantic schemas for authentication."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    """Create (or log into) a user account by email."""

    email: EmailStr = Field(max_length=255)


class UserResponse(BaseModel):
    """Public user payload (never exposes keys or secrets)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    created_at: datetime


class TokenResponse(BaseModel):
    """JWT access token issued at registration/login."""

    access_token: str
    token_type: str = "bearer"  # noqa: S105
    user: UserResponse
