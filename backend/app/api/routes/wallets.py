"""Wallet management routes (all authenticated and user-scoped)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user
from backend.app.schemas.wallets import (
    ChallengeRequest,
    ChallengeResponse,
    ConnectRequest,
    WalletResponse,
    WalletRevokeResponse,
)
from backend.app.services import wallets as wallet_service
from backend.app.services.wallets import ChallengeError
from database.models import User
from database.session import get_db

router = APIRouter(prefix="/wallets", tags=["wallets"])

db_dep = Annotated[AsyncSession, Depends(get_db)]
current_user_dep = Annotated[User, Depends(get_current_user)]


def _challenge_error(exc: ChallengeError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/challenge", response_model=ChallengeResponse, status_code=201)
async def create_challenge(
    payload: ChallengeRequest,
    db: db_dep,
    user: current_user_dep,
) -> ChallengeResponse:
    """Request a single-use, expiring message to sign for ownership proof."""
    try:
        challenge = await wallet_service.create_challenge(db, user, payload.address, payload.chain)
    except ChallengeError as exc:
        raise _challenge_error(exc) from exc
    return ChallengeResponse(
        challenge_id=challenge.id,
        address=challenge.address,
        chain=challenge.chain,
        nonce=challenge.nonce,
        message=challenge.message,
        expires_at=challenge.expires_at,
    )


@router.post("/connect", response_model=WalletResponse, status_code=201)
async def connect_wallet(
    payload: ConnectRequest,
    db: db_dep,
    user: current_user_dep,
) -> WalletResponse:
    """Verify the signed message and register the wallet."""
    try:
        wallet = await wallet_service.connect_wallet(
            db,
            user,
            payload.challenge_id,
            payload.address,
            payload.chain,
            payload.signature,
        )
    except ChallengeError as exc:
        raise _challenge_error(exc) from exc
    return WalletResponse.model_validate(wallet)


@router.get("", response_model=list[WalletResponse])
async def list_wallets(db: db_dep, user: current_user_dep) -> list[WalletResponse]:
    """List the authenticated user's wallets."""
    wallets = await wallet_service.list_wallets(db, user)
    return [WalletResponse.model_validate(w) for w in wallets]


@router.get("/{wallet_id}", response_model=WalletResponse)
async def get_wallet(
    wallet_id: str,
    db: db_dep,
    user: current_user_dep,
) -> WalletResponse:
    """Fetch one of the authenticated user's wallets."""
    try:
        parsed = uuid.UUID(wallet_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Wallet not found") from exc
    try:
        wallet = await wallet_service.get_wallet(db, user, parsed)
    except ChallengeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return WalletResponse.model_validate(wallet)


@router.post("/{wallet_id}/revoke", response_model=WalletRevokeResponse)
async def revoke_wallet(
    wallet_id: str,
    db: db_dep,
    user: current_user_dep,
) -> WalletRevokeResponse:
    """Revoke a wallet (removes it from the agent's consideration set)."""
    try:
        parsed = uuid.UUID(wallet_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Wallet not found") from exc
    try:
        wallet = await wallet_service.revoke_wallet(db, user, parsed)
    except ChallengeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return WalletRevokeResponse(id=wallet.id, status=wallet.status)
