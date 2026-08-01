"""ORM model tests: relationships, constraints, defaults, cascade behavior."""

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from database.models import (
    AuditLog,
    Execution,
    ExecutionStatus,
    Position,
    RiskLevel,
    User,
    UserPreferences,
    Wallet,
    WalletStatus,
)


@pytest.mark.asyncio
async def test_full_hierarchy_create(db_session) -> None:
    user = User(email="alice@example.com")
    db_session.add(user)
    await db_session.flush()

    prefs = UserPreferences(
        user_id=user.id,
        risk_level=RiskLevel.MEDIUM,
        preferred_assets=["USDC"],
        minimum_yield_difference=2.0,
        maximum_gas_cost=5.0,
    )
    wallet = Wallet(
        user_id=user.id, address="0x1111111111111111111111111111111111111111", chain="ethereum"
    )
    db_session.add_all([prefs, wallet])
    await db_session.flush()

    position = Position(
        wallet_id=wallet.id,
        protocol="aave-v3",
        asset="USDC",
        amount=Decimal("10000"),
        apy=Decimal("4.5000"),
    )
    execution = Execution(user_id=user.id, action="migrate_yield", status=ExecutionStatus.PENDING)
    audit = AuditLog(user_id=user.id, event="user.created", description="Account created")
    db_session.add_all([position, execution, audit])
    await db_session.commit()

    fetched = await db_session.scalar(
        select(User)
        .where(User.id == user.id)
        .options(
            selectinload(User.preferences),
            selectinload(User.wallets).selectinload(Wallet.positions),
            selectinload(User.executions),
            selectinload(User.audit_logs),
        )
    )
    assert fetched is not None
    assert fetched.email == "alice@example.com"
    assert fetched.preferences.risk_level is RiskLevel.MEDIUM
    assert fetched.preferences.preferred_assets == ["USDC"]
    assert len(fetched.wallets) == 1
    assert fetched.wallets[0].positions[0].amount == Decimal("10000")
    assert len(fetched.executions) == 1
    assert len(fetched.audit_logs) == 1


@pytest.mark.asyncio
async def test_enum_defaults(db_session) -> None:
    user = User(email="bob@example.com")
    db_session.add(user)
    await db_session.flush()
    wallet = Wallet(
        user_id=user.id, address="0x2222222222222222222222222222222222222222", chain="base"
    )
    execution = Execution(user_id=user.id, action="rebalance")
    db_session.add_all([wallet, execution])
    await db_session.commit()

    fetched_wallet = await db_session.get(Wallet, wallet.id)
    fetched_execution = await db_session.get(Execution, execution.id)
    assert fetched_wallet.status is WalletStatus.ACTIVE
    assert fetched_execution.status is ExecutionStatus.PENDING


@pytest.mark.asyncio
async def test_email_unique(db_session) -> None:
    db_session.add_all([User(email="dup@example.com"), User(email="dup@example.com")])
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_wallet_unique_per_user_chain(db_session) -> None:
    user = User(email="wallet@example.com")
    db_session.add(user)
    await db_session.flush()
    addr = "0x3333333333333333333333333333333333333333"
    db_session.add_all(
        [
            Wallet(user_id=user.id, address=addr, chain="ethereum"),
            Wallet(user_id=user.id, address=addr, chain="ethereum"),
        ]
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_same_address_different_chain_allowed(db_session) -> None:
    user = User(email="multi@example.com")
    db_session.add(user)
    await db_session.flush()
    addr = "0x4444444444444444444444444444444444444444"
    db_session.add_all(
        [
            Wallet(user_id=user.id, address=addr, chain="ethereum"),
            Wallet(user_id=user.id, address=addr, chain="base"),
        ]
    )
    await db_session.commit()
    result = await db_session.scalars(select(Wallet).where(Wallet.address == addr))
    assert len(result.all()) == 2


@pytest.mark.asyncio
async def test_position_unique_protocol_asset(db_session) -> None:
    user = User(email="pos@example.com")
    db_session.add(user)
    await db_session.flush()
    wallet = Wallet(
        user_id=user.id, address="0x5555555555555555555555555555555555555555", chain="ethereum"
    )
    db_session.add(wallet)
    await db_session.flush()
    db_session.add_all(
        [
            Position(wallet_id=wallet.id, protocol="aave-v3", asset="USDC"),
            Position(wallet_id=wallet.id, protocol="aave-v3", asset="USDC"),
        ]
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_user_delete_cascades(db_session) -> None:
    user = User(email="cascade@example.com")
    db_session.add(user)
    await db_session.flush()
    wallet = Wallet(
        user_id=user.id, address="0x6666666666666666666666666666666666666666", chain="ethereum"
    )
    db_session.add(wallet)
    await db_session.flush()
    db_session.add_all(
        [
            Position(wallet_id=wallet.id, protocol="morpho", asset="USDC"),
            Execution(user_id=user.id, action="deposit"),
            AuditLog(user_id=user.id, event="wallet.connected", description="Wallet connected"),
        ]
    )
    await db_session.commit()

    await db_session.delete(user)
    await db_session.commit()

    assert await db_session.get(User, user.id) is None
    assert await db_session.get(Wallet, wallet.id) is None
    assert (await db_session.scalars(select(Position))).all() == []
    assert (await db_session.scalars(select(Execution))).all() == []
    assert (await db_session.scalars(select(AuditLog))).all() == []
