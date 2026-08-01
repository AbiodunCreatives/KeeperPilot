"""Auth API tests: registration issues JWTs, no duplicates, input validation."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from backend.app.core.config import get_settings

REGISTER_URL = "/api/auth/register"


async def register(client, email="alice@example.com"):
    resp = await client.post(REGISTER_URL, json={"email": email})
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_register_returns_token_and_user(api_client) -> None:
    data = await register(api_client)
    assert data["token_type"] == "bearer"  # noqa: S105
    assert data["access_token"]
    assert data["user"]["email"] == "alice@example.com"
    assert data["user"]["id"]


@pytest.mark.asyncio
async def test_register_is_idempotent_for_same_email(api_client) -> None:
    first = await register(api_client, "bob@example.com")
    second = await register(api_client, "bob@example.com")
    assert first["user"]["id"] == second["user"]["id"]
    assert first["access_token"] != second["access_token"]


@pytest.mark.asyncio
async def test_register_normalizes_email_case(api_client) -> None:
    data = await register(api_client, "Carol@Example.COM")
    assert data["user"]["email"] == "carol@example.com"


@pytest.mark.asyncio
async def test_register_rejects_invalid_email(api_client) -> None:
    resp = await api_client.post(REGISTER_URL, json={"email": "not-an-email"})
    assert resp.status_code == 422


# ----------------------------------------------------------- token security


def _make_token(secret: str, **overrides) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(uuid.uuid4()),
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + timedelta(minutes=10),
        **overrides,
    }
    return jwt.encode(payload, secret, algorithm=settings.jwt_algorithm)


@pytest.mark.asyncio
async def test_garbage_token_rejected(api_client) -> None:
    resp = await api_client.get("/api/wallets", headers={"Authorization": "Bearer not.a.jwt"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_tampered_token_rejected(api_client) -> None:
    settings = get_settings()
    good = _make_token(settings.jwt_secret)
    bad = good[:-4] + "abcd"
    resp = await api_client.get("/api/wallets", headers={"Authorization": f"Bearer {bad}"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_expired_token_rejected(api_client) -> None:
    settings = get_settings()
    now = datetime.now(UTC)
    expired = _make_token(
        settings.jwt_secret, exp=now - timedelta(minutes=1), iat=now - timedelta(hours=2)
    )
    resp = await api_client.get("/api/wallets", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_token_for_nonexistent_user_rejected(api_client) -> None:
    settings = get_settings()
    ghost = _make_token(settings.jwt_secret)
    resp = await api_client.get("/api/wallets", headers={"Authorization": f"Bearer {ghost}"})
    assert resp.status_code == 401
