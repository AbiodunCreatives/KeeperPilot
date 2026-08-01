"""JWT issuance/validation for KeeperPilot access tokens."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from jwt import InvalidTokenError

from backend.app.core.config import get_settings


def create_access_token(subject: uuid.UUID) -> str:
    """Issue a signed HS256 JWT with a ``sub`` claim, a unique id, and expiry."""
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(subject),
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expires_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> uuid.UUID | None:
    """Validate a token and return the user UUID, or ``None`` if invalid."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except InvalidTokenError:
        return None
    subject = payload.get("sub")
    if subject is None:
        return None
    try:
        return uuid.UUID(str(subject))
    except (ValueError, TypeError):
        return None
