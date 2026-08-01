"""Wallet management service: ownership challenges, verification, lifecycle.

Security model
--------------
* Private keys are never requested, stored, or logged. Proof of ownership is a
  signed message: the backend issues a single-use, expiring nonce, the user signs
  it with their wallet, and we recover the signer address locally (secp256k1).
* All queries are scoped by ``user_id`` derived from the JWT, so a user can only
  ever read/write their own wallets.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from eth_account import Account
from eth_account.messages import encode_defunct
from eth_utils import to_checksum_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import get_settings
from database.models import AuditLog, User, Wallet, WalletChallenge, WalletStatus

MESSAGE_TEMPLATE = (
    "keeperpilot.example wants you to sign in with your wallet.\n"
    "Wallet: {address}\n"
    "Chain: {chain}\n"
    "Nonce: {nonce}"
)


class ChallengeError(ValueError):
    """Raised when an ownership challenge is invalid, expired, or replayed."""


def _now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    """Return ``value`` in UTC, assuming UTC if it is naive (SQLite behavior)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _normalize_address(address: str) -> str:
    """Return the EIP-55 checksummed form or raise if the address is malformed."""
    if not address.startswith("0x") or len(address) != 42:
        raise ChallengeError("Invalid EVM address")
    try:
        return to_checksum_address(address)
    except ValueError as exc:
        raise ChallengeError("Invalid EVM address") from exc


def build_challenge_message(address: str, chain: str, nonce: str) -> str:
    """Compose the exact string the user must sign."""
    return MESSAGE_TEMPLATE.format(address=address, chain=chain, nonce=nonce)


async def create_challenge(
    db: AsyncSession,
    user: User,
    address: str,
    chain: str,
) -> WalletChallenge:
    """Create a single-use, expiring ownership challenge for ``address``."""
    settings = get_settings()
    checksummed = _normalize_address(address)
    nonce = secrets.token_urlsafe(32)
    message = build_challenge_message(checksummed, chain, nonce)

    challenge = WalletChallenge(
        user_id=user.id,
        address=checksummed,
        chain=chain,
        message=message,
        nonce=nonce,
        used=False,
        expires_at=_now() + timedelta(minutes=settings.challenge_ttl_minutes),
    )
    db.add(challenge)
    await db.commit()
    await db.refresh(challenge)
    return challenge


async def connect_wallet(
    db: AsyncSession,
    user: User,
    challenge_id: uuid.UUID,
    address: str,
    chain: str,
    signature: str,
) -> Wallet:
    """Verify a signature against the challenge and register the wallet.

    Steps:
    1. Load the challenge; it must belong to ``user``.
    2. Reject if it is expired, already used, or its address/chain mismatch.
    3. Recover the signer from ``signature`` and compare to the challenge
       address (checksummed).
    4. Create or re-activate the wallet and mark the challenge used.
    """
    challenge = await db.get(WalletChallenge, challenge_id)
    if challenge is None or challenge.user_id != user.id:
        raise ChallengeError("Unknown challenge")

    if challenge.used:
        raise ChallengeError("Challenge already used")
    if challenge.expires_at is None or _as_utc(challenge.expires_at) < _now():
        raise ChallengeError("Challenge expired")
    if challenge.address != _normalize_address(address) or challenge.chain != chain:
        raise ChallengeError("Challenge does not match this address/chain")

    try:
        normalized_signature = signature if signature.startswith("0x") else f"0x{signature}"
        recovered = Account.recover_message(
            encode_defunct(text=challenge.message), signature=normalized_signature
        )
    except ValueError as exc:
        raise ChallengeError("Invalid signature") from exc

    if to_checksum_address(recovered) != challenge.address:
        raise ChallengeError("Signature does not match the requested wallet")

    wallet = await _get_active_wallet(db, user.id, challenge.address, chain)
    if wallet is None:
        wallet = Wallet(
            user_id=user.id,
            address=challenge.address,
            chain=chain,
            status=WalletStatus.ACTIVE,
        )
        db.add(wallet)
    else:
        wallet.status = WalletStatus.ACTIVE

    challenge.used = True
    challenge.signature = normalized_signature

    db.add(
        AuditLog(
            event="wallet.connected",
            description=f"Wallet {challenge.address} on {chain} verified and registered",
            user_id=user.id,
        )
    )
    await db.commit()
    await db.refresh(wallet)
    return wallet


async def _get_active_wallet(
    db: AsyncSession, user_id: uuid.UUID, address: str, chain: str
) -> Wallet | None:
    stmt = select(Wallet).where(
        Wallet.user_id == user_id,
        Wallet.address == address,
        Wallet.chain == chain,
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_wallets(db: AsyncSession, user: User) -> list[Wallet]:
    stmt = (
        select(Wallet)
        .where(Wallet.user_id == user.id)
        .order_by(Wallet.created_at.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def get_wallet(db: AsyncSession, user: User, wallet_id: uuid.UUID) -> Wallet:
    wallet = await db.get(Wallet, wallet_id)
    if wallet is None or wallet.user_id != user.id:
        raise ChallengeError("Wallet not found")
    return wallet


async def revoke_wallet(db: AsyncSession, user: User, wallet_id: uuid.UUID) -> Wallet:
    """Revoke a wallet owned by ``user``. Revoked wallets can be re-connected."""
    wallet = await get_wallet(db, user, wallet_id)
    wallet.status = WalletStatus.REVOKED
    db.add(
        AuditLog(
            event="wallet.revoked",
            description=f"Wallet {wallet.address} on {wallet.chain} revoked",
            user_id=user.id,
        )
    )
    await db.commit()
    await db.refresh(wallet)
    return wallet
