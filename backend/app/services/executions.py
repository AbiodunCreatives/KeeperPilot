"""Execution service: create, approve (submit), reject, cancel, refresh.

Safety model
------------
* **Policy is re-verified server-side at creation time** — the client never
  decides what may execute; it only points at a wallet/position/target and the
  service re-fetches the position and re-runs `evaluate_opportunity` with the
  user's current preferences.
* **No concurrent executions on the same position** — one in-flight execution
  (pending/approved/submitted) per wallet+asset blocks a second one.
* **Explicit approval** — an execution does not reach KeeperHub until the owner
  approves it (guardrail against fully unattended moves).
* Everything is scoped by the authenticated user.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agent.keeperhub.client import (
    ExecutionAction,
    KeeperHubClient,
    get_keeperhub_client,
)
from backend.app.schemas.executions import ExecutionRequest
from backend.app.services import preferences as preferences_service
from backend.app.services.policies import evaluate_opportunity
from database.models import (
    AuditLog,
    Execution,
    ExecutionStatus,
    Position,
    User,
    Wallet,
    WalletStatus,
)

ACTION = "migrate_yield"

IN_FLIGHT = (
    ExecutionStatus.PENDING,
    ExecutionStatus.APPROVED,
    ExecutionStatus.SUBMITTED,
)


class ExecutionError(ValueError):
    """Base error for the execution flow."""


class ExecutionNotFoundError(ExecutionError):
    """Raised when the execution is missing or belongs to another user."""


class ExecutionConflictError(ExecutionError):
    """Raised when the requested transition violates a guardrail."""


def _now() -> datetime:
    return datetime.now(UTC)


def _audit(
    db: AsyncSession, user: User, execution: Execution, event: str, description: str
) -> None:
    db.add(
        AuditLog(
            event=event,
            description=description,
            user_id=user.id,
            execution_id=execution.id,
        )
    )


async def _get_position(
    db: AsyncSession, user: User, wallet_id: uuid.UUID, asset: str, protocol: str
) -> Position:
    stmt = (
        select(Position)
        .join(Wallet, Wallet.id == Position.wallet_id)
        .where(
            Wallet.user_id == user.id,
            Wallet.status == WalletStatus.ACTIVE,
            Wallet.id == wallet_id,
            Position.asset == asset.upper(),
            Position.protocol == protocol.lower(),
        )
    )
    position = (await db.execute(stmt)).scalar_one_or_none()
    if position is None:
        raise ExecutionNotFoundError("Position not found for this wallet and asset")
    return position


async def create_execution(
    db: AsyncSession,
    user: User,
    payload: ExecutionRequest,
    client: KeeperHubClient | None = None,
) -> Execution:
    """Create a pending execution after re-verifying the move against policy."""
    position = await _get_position(
        db, user, payload.wallet_id, payload.asset, payload.source_protocol
    )
    wallet = await db.get(Wallet, position.wallet_id)
    if wallet is None:
        raise ExecutionNotFoundError("Wallet not found")

    client = client or get_keeperhub_client()
    opportunities = await client.get_opportunities(position.asset, wallet.chain)
    target = next(
        (o for o in opportunities if o.protocol.lower() == payload.target_protocol.lower()),
        None,
    )
    if target is None:
        raise ExecutionNotFoundError(f"No opportunity found for target {payload.target_protocol}")
    if target.protocol.lower() == position.protocol.lower():
        raise ExecutionError("Target protocol is the position's current protocol")

    prefs = await preferences_service.get_preferences(db, user)
    decision = evaluate_opportunity(
        prefs,
        asset=position.asset,
        current_apy=float(position.apy),
        candidate_apy=target.apy,
        gas_cost=target.estimated_gas,
        candidate_protocol_risk=target.risk_level,
    )
    if not decision.allowed:
        raise ExecutionError(
            "Move blocked by policy: " + "; ".join(decision.reasons)
        )

    # Guardrail: one in-flight execution per wallet+asset.
    stmt = select(Execution).where(
        Execution.wallet_id == position.wallet_id,
        Execution.asset == position.asset,
        Execution.status.in_(IN_FLIGHT),
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        raise ExecutionConflictError(
            "An execution for "
            f"{position.asset} is already in flight (status={existing.status.value})"
        )

    execution = Execution(
        user_id=user.id,
        wallet_id=position.wallet_id,
        action=ACTION,
        status=ExecutionStatus.PENDING,
        source_protocol=position.protocol,
        target_protocol=target.protocol,
        gas_used=Decimal(str(target.estimated_gas)),
        amount=position.amount,
        asset=position.asset,
        reason=(
            f"Migrate {position.asset} from {position.protocol} to {target.protocol}: "
            f"{target.apy - float(position.apy):+.2f}pp APY, est. gas ${target.estimated_gas:.2f}"
        ),
    )
    db.add(execution)
    await db.flush()
    _audit(
        db,
        user,
        execution,
        "execution.created",
        f"{position.asset} {position.protocol} -> {target.protocol} pending approval",
    )
    await db.commit()
    await db.refresh(execution)
    return execution


async def _load_execution(db: AsyncSession, user: User, execution_id: uuid.UUID) -> Execution:
    execution = await db.get(Execution, execution_id)
    if execution is None or execution.user_id != user.id:
        raise ExecutionNotFoundError("Execution not found")
    return execution


async def approve_execution(
    db: AsyncSession,
    user: User,
    execution_id: uuid.UUID,
    client: KeeperHubClient | None = None,
) -> Execution:
    """Approve a pending execution and submit it to the execution layer."""
    execution = await _load_execution(db, user, execution_id)
    if execution.status != ExecutionStatus.PENDING:
        raise ExecutionError(
            f"Only pending executions can be approved (current status: {execution.status.value})"
        )

    wallet = await db.get(Wallet, execution.wallet_id) if execution.wallet_id else None
    if wallet is None:
        raise ExecutionError("Wallet no longer available")

    execution.status = ExecutionStatus.APPROVED
    _audit(db, user, execution, "execution.approved", "Approved by owner")

    client = client or get_keeperhub_client()
    action = ExecutionAction(
        wallet_address=wallet.address,
        chain=wallet.chain,
        asset=execution.asset or "",
        amount=execution.amount or Decimal("0"),
        source_protocol=execution.source_protocol or "",
        target_protocol=execution.target_protocol or "",
        estimated_gas=float(execution.gas_used or 0),
    )
    receipt = await client.submit(action)
    execution.status = ExecutionStatus.SUBMITTED
    execution.transaction_hash = receipt.tx_hash
    _audit(db, user, execution, "execution.submitted", f"tx {receipt.tx_hash}")

    # Poll once — mock completes immediately; real client may stay SUBMITTED.
    if receipt.status == "failed":
        execution.status = ExecutionStatus.FAILED
        execution.completed_at = _now()
        _audit(db, user, execution, "execution.failed", f"tx {receipt.tx_hash} failed on-chain")
    elif receipt.status == "completed":
        execution.status = ExecutionStatus.COMPLETED
        execution.completed_at = _now()
        _audit(db, user, execution, "execution.completed", f"tx {receipt.tx_hash} completed")

    await db.commit()
    await db.refresh(execution)
    return execution


async def reject_execution(
    db: AsyncSession, user: User, execution_id: uuid.UUID
) -> Execution:
    execution = await _load_execution(db, user, execution_id)
    if execution.status != ExecutionStatus.PENDING:
        raise ExecutionError(
            f"Only pending executions can be rejected (current status: {execution.status.value})"
        )
    execution.status = ExecutionStatus.REJECTED
    _audit(db, user, execution, "execution.rejected", "Rejected by owner")
    await db.commit()
    await db.refresh(execution)
    return execution


async def cancel_execution(
    db: AsyncSession, user: User, execution_id: uuid.UUID
) -> Execution:
    execution = await _load_execution(db, user, execution_id)
    if execution.status not in (ExecutionStatus.PENDING, ExecutionStatus.APPROVED):
        raise ExecutionError(
            "Only pending/approved executions can be cancelled "
            f"(current status: {execution.status.value})"
        )
    execution.status = ExecutionStatus.CANCELLED
    _audit(db, user, execution, "execution.cancelled", "Cancelled")
    await db.commit()
    await db.refresh(execution)
    return execution


async def refresh_execution(
    db: AsyncSession,
    user: User,
    execution_id: uuid.UUID,
    client: KeeperHubClient | None = None,
) -> Execution:
    """Poll the execution layer for a submitted execution's latest status."""
    execution = await _load_execution(db, user, execution_id)
    if execution.status != ExecutionStatus.SUBMITTED or execution.transaction_hash is None:
        return execution

    client = client or get_keeperhub_client()
    receipt = await client.get_receipt(execution.transaction_hash)
    if receipt.status == "failed":
        execution.status = ExecutionStatus.FAILED
        execution.completed_at = _now()
        _audit(db, user, execution, "execution.failed", f"tx {receipt.tx_hash} failed on-chain")
    elif receipt.status == "completed":
        execution.status = ExecutionStatus.COMPLETED
        execution.completed_at = _now()
        _audit(db, user, execution, "execution.completed", f"tx {receipt.tx_hash} completed")
    await db.commit()
    await db.refresh(execution)
    return execution


async def list_executions(db: AsyncSession, user: User) -> list[Execution]:
    stmt = (
        select(Execution)
        .where(Execution.user_id == user.id)
        .options(selectinload(Execution.wallet))
        .order_by(Execution.created_at.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def get_execution(db: AsyncSession, user: User, execution_id: uuid.UUID) -> Execution:
    return await _load_execution(db, user, execution_id)
