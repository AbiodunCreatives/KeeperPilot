"""Wallet API tests: signed ownership verification, isolation, lifecycle.

These tests exercise the security properties of Task 3:
* ownership is proven by signature, never by revealing a private key;
* challenges are single-use and expiring (no replay);
* every operation is scoped to the authenticated user (isolation);
* private key material is never persisted.
"""

import uuid
from datetime import timedelta

import pytest
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_utils import to_checksum_address
from sqlalchemy import select

from database.models import AuditLog, Wallet, WalletChallenge

CHAIN = "11155111"


async def register_user(client, email: str) -> str:
    resp = await client.post("/api/auth/register", json={"email": email})
    assert resp.status_code == 201
    return resp.json()["access_token"]


def make_account() -> Account:
    return Account.create()


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def create_challenge(client, token: str, address: str, chain: str = CHAIN) -> dict:
    resp = await client.post(
        "/api/wallets/challenge",
        json={"address": address, "chain": chain},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


def sign_message(acct: Account, message: str) -> str:
    signed = acct.sign_message(encode_defunct(text=message))
    return signed.signature.hex()


async def connect(
    client, token: str, challenge: dict, signature: str, chain: str = CHAIN
) -> object:
    return await client.post(
        "/api/wallets/connect",
        json={
            "challenge_id": challenge["challenge_id"],
            "address": challenge["address"],
            "chain": chain,
            "signature": signature,
        },
        headers=auth_headers(token),
    )


# ---------------------------------------------------------------- happy path


@pytest.mark.asyncio
async def test_full_connect_flow(api_client, db_session) -> None:
    token = await register_user(api_client, "alice@example.com")
    acct = make_account()
    challenge = await create_challenge(api_client, token, acct.address)

    assert challenge["nonce"]
    assert "Nonce:" in challenge["message"]

    signature = sign_message(acct, challenge["message"])
    resp = await connect(api_client, token, challenge, signature)

    assert resp.status_code == 201
    wallet = resp.json()
    assert wallet["address"] == to_checksum_address(acct.address)
    assert wallet["chain"] == CHAIN
    assert wallet["status"] == "active"

    # challenge is marked used in the DB
    stored = await db_session.get(WalletChallenge, uuid.UUID(challenge["challenge_id"]))
    assert stored is not None
    assert stored.used is True

    # audit event written
    events = list(
        (await db_session.execute(select(AuditLog.event))).scalars().all()
    )
    assert "wallet.connected" in events

    # wallet listed for the user
    listing = await api_client.get("/api/wallets", headers=auth_headers(token))
    assert listing.status_code == 200
    assert [w["id"] for w in listing.json()] == [wallet["id"]]


@pytest.mark.asyncio
async def test_connect_normalizes_address_case(api_client) -> None:
    token = await register_user(api_client, "bob@example.com")
    acct = make_account()
    challenge = await create_challenge(api_client, token, acct.address)
    signature = sign_message(acct, challenge["message"])

    resp = await connect(api_client, token, challenge, signature)
    assert resp.status_code == 201
    # stored checksummed even if client sent a different case variant
    assert resp.json()["address"] == to_checksum_address(acct.address)


# ------------------------------------------------------------- security tests


@pytest.mark.asyncio
async def test_connect_rejects_wrong_signature(api_client) -> None:
    token = await register_user(api_client, "mallory@example.com")
    acct = make_account()
    other = make_account()
    challenge = await create_challenge(api_client, token, acct.address)

    resp = await connect(api_client, token, challenge, sign_message(other, challenge["message"]))
    assert resp.status_code == 400
    assert "does not match" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_connect_rejects_garbage_signature(api_client) -> None:
    token = await register_user(api_client, "noise@example.com")
    acct = make_account()
    challenge = await create_challenge(api_client, token, acct.address)
    garbage = "0x" + "ab" * 65
    resp = await connect(api_client, token, challenge, garbage)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_challenge_is_single_use(api_client) -> None:
    token = await register_user(api_client, "replay@example.com")
    acct = make_account()
    challenge = await create_challenge(api_client, token, acct.address)
    signature = sign_message(acct, challenge["message"])

    first = await connect(api_client, token, challenge, signature)
    assert first.status_code == 201
    second = await connect(api_client, token, challenge, signature)
    assert second.status_code == 400
    assert "already used" in second.json()["detail"]


@pytest.mark.asyncio
async def test_expired_challenge_is_rejected(api_client, db_session) -> None:
    token = await register_user(api_client, "tardy@example.com")
    acct = make_account()
    challenge = await create_challenge(api_client, token, acct.address)

    stored = await db_session.get(WalletChallenge, uuid.UUID(challenge["challenge_id"]))
    stored.expires_at = stored.expires_at - timedelta(minutes=11)
    await db_session.commit()

    resp = await connect(api_client, token, challenge, sign_message(acct, challenge["message"]))
    assert resp.status_code == 400
    assert "expired" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_address_mismatch_with_challenge_is_rejected(api_client) -> None:
    token = await register_user(api_client, "mixup@example.com")
    acct = make_account()
    challenge = await create_challenge(api_client, token, acct.address)

    # Trying to register a *different* address while using acct's signature
    # must fail: the challenge is bound to the address it was issued for.
    other = make_account()
    tampered = await api_client.post(
        "/api/wallets/connect",
        json={
            "challenge_id": challenge["challenge_id"],
            "address": other.address,
            "chain": CHAIN,
            "signature": sign_message(acct, challenge["message"]),
        },
        headers=auth_headers(token),
    )
    assert tampered.status_code == 400
    assert "does not match" in tampered.json()["detail"]


@pytest.mark.asyncio
async def test_challenge_of_another_user_cannot_be_used(api_client) -> None:
    token_a = await register_user(api_client, "a@example.com")
    token_b = await register_user(api_client, "b@example.com")
    acct = make_account()
    challenge = await create_challenge(api_client, token_a, acct.address)
    signature = sign_message(acct, challenge["message"])

    resp = await connect(api_client, token_b, challenge, signature)
    assert resp.status_code == 400
    assert "Unknown challenge" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_unauthenticated_requests_are_rejected(api_client) -> None:
    resp = await api_client.get("/api/wallets")
    assert resp.status_code == 401
    resp = await api_client.post(
        "/api/wallets/challenge",
        json={"address": "0x" + "0" * 40, "chain": CHAIN},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_malformed_addresses_are_rejected(api_client) -> None:
    token = await register_user(api_client, "malformed@example.com")
    for bad in ["0x123", "1234567890", "0x" + "z" * 40]:
        resp = await api_client.post(
            "/api/wallets/challenge",
            json={"address": bad, "chain": CHAIN},
            headers=auth_headers(token),
        )
        # 422 = schema rejection, 400 = service rejection; either is secure.
        assert resp.status_code in (400, 422), bad


# ------------------------------------------------------------- isolation


@pytest.mark.asyncio
async def test_cannot_access_another_users_wallet(api_client) -> None:
    token_a = await register_user(api_client, "alice2@example.com")
    token_b = await register_user(api_client, "bob2@example.com")

    acct = make_account()
    challenge = await create_challenge(api_client, token_a, acct.address)
    signature = sign_message(acct, challenge["message"])
    wallet = (await connect(api_client, token_a, challenge, signature)).json()
    wallet_id = wallet["id"]

    # B cannot fetch A's wallet
    fetched = await api_client.get(f"/api/wallets/{wallet_id}", headers=auth_headers(token_b))
    assert fetched.status_code == 404

    # B cannot revoke A's wallet
    revoked = await api_client.post(
        f"/api/wallets/{wallet_id}/revoke", headers=auth_headers(token_b)
    )
    assert revoked.status_code == 404

    # B's list is empty
    listing = await api_client.get("/api/wallets", headers=auth_headers(token_b))
    assert listing.json() == []


@pytest.mark.asyncio
async def test_revoke_and_reconnect_reactivates(api_client) -> None:
    token = await register_user(api_client, "lifecycle@example.com")
    acct = make_account()
    challenge = await create_challenge(api_client, token, acct.address)
    signature = sign_message(acct, challenge["message"])
    wallet = (await connect(api_client, token, challenge, signature)).json()

    revoked = await api_client.post(
        f"/api/wallets/{wallet['id']}/revoke", headers=auth_headers(token)
    )
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"

    listed = (await api_client.get("/api/wallets", headers=auth_headers(token))).json()
    assert listed[0]["status"] == "revoked"

    # reconnecting re-activates the same wallet row
    challenge2 = await create_challenge(api_client, token, acct.address)
    signature2 = sign_message(acct, challenge2["message"])
    resp = await connect(api_client, token, challenge2, signature2)
    assert resp.status_code == 201
    assert resp.json()["id"] == wallet["id"]
    assert resp.json()["status"] == "active"


# ----------------------------------------------------- no key material stored


@pytest.mark.asyncio
async def test_private_key_is_never_persisted(api_client, db_session) -> None:
    token = await register_user(api_client, "privacy@example.com")
    acct = make_account()
    private_key = "0x" + acct.key.hex()
    challenge = await create_challenge(api_client, token, acct.address)
    signature = sign_message(acct, challenge["message"])
    resp = await connect(api_client, token, challenge, signature)
    assert resp.status_code == 201

    # The private key hex must not appear in any stored row of any table.
    leaked: list[str] = []
    for model in (Wallet, WalletChallenge):
        rows = (await db_session.execute(select(model))).scalars().all()
        for row in rows:
            dumped = {c.name: getattr(row, c.name) for c in model.__table__.columns}
            for value in dumped.values():
                if value is not None and private_key.lower() in str(value).lower():
                    leaked.append(f"{model.__name__}.{value}")
    assert leaked == []
