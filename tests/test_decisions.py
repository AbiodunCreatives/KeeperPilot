"""Decision engine tests: scan, evaluation, ranking, summaries, isolation."""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from agent.keeperhub.client import MockKeeperHubClient
from agent.keeperhub.mock_data import MOCK_MARKET
from database.models import AuditLog, Position, Wallet, WalletStatus

CHAIN = "11155111"


def uid(user_id: str) -> uuid.UUID:
    return uuid.UUID(user_id)


async def register(client, email: str) -> dict:
    resp = await client.post("/api/auth/register", json={"email": email})
    assert resp.status_code == 201
    return resp.json()


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def add_wallet_with_position(
    db_session, user_id, *, chain=CHAIN, protocol="aave-v3", apy=4.0
) -> None:
    wallet = Wallet(
        user_id=user_id,
        address="0x1111111111111111111111111111111111111111",
        chain=chain,
        status=WalletStatus.ACTIVE,
    )
    db_session.add(wallet)
    await db_session.flush()
    db_session.add(
        Position(
            wallet_id=wallet.id,
            protocol=protocol,
            asset="USDC",
            amount=Decimal("10000"),
            apy=Decimal(str(apy)),
        )
    )
    await db_session.commit()


# ------------------------------------------------------------- happy path


@pytest.mark.asyncio
async def test_scan_returns_ranked_recommendations(api_client, db_session) -> None:
    user = await register(api_client, "investor@example.com")
    token = user["access_token"]
    await add_wallet_with_position(db_session, uid(user["user"]["id"]))

    result = await api_client.get("/api/decisions/scan", headers=auth(token))
    assert result.status_code == 200
    report = result.json()

    # 5 USDC rows in the mock market, minus the same-protocol (aave-v3) candidate
    assert report["recommendation_count"] == 4
    assert report["allowed_count"] == 2  # morpho + fluid under default policy
    assert report["blocked_count"] == 2  # compound (low delta) + yield-farm (high risk)
    assert report["summary"]
    assert "Best move" in report["summary"]

    recs = report["recommendations"]
    allowed = [r for r in recs if r["allowed"]]
    denied = [r for r in recs if not r["allowed"]]
    # allowed candidates first, ordered by APY delta desc
    assert recs == allowed + denied
    deltas = [r["delta_apy"] for r in allowed]
    assert deltas == sorted(deltas, reverse=True)
    # best move surfaces the top allowed recommendation
    assert allowed[0]["opportunity"]["protocol"] == "fluid"
    # every recommendation carries the per-rule checks
    assert all(r["checks"] for r in recs)
    # same-protocol candidate is excluded
    assert all(r["opportunity"]["protocol"] != "aave-v3" for r in recs)


@pytest.mark.asyncio
async def test_scan_empty_when_no_positions(api_client) -> None:
    user = await register(api_client, "empty@example.com")
    resp = await api_client.get("/api/decisions/scan", headers=auth(user["access_token"]))
    assert resp.status_code == 200
    report = resp.json()
    assert report["recommendation_count"] == 0
    assert report["allowed_count"] == 0
    assert "No tracked positions" in report["summary"]


@pytest.mark.asyncio
async def test_scan_is_per_user(api_client, db_session) -> None:
    user_a = await register(api_client, "onlya@example.com")
    await add_wallet_with_position(db_session, uid(user_a["user"]["id"]))

    user_b = await register(api_client, "onlyb@example.com")
    resp_b = await api_client.get("/api/decisions/scan", headers=auth(user_b["access_token"]))
    assert resp_b.status_code == 200
    assert resp_b.json()["recommendation_count"] == 0


@pytest.mark.asyncio
async def test_policy_blocks_candidates(api_client, db_session) -> None:
    user = await register(api_client, "conservative@example.com")
    token = user["access_token"]
    await add_wallet_with_position(db_session, uid(user["user"]["id"]))

    # strict user: low risk + USDC-only + 3pp min delta + $2 gas cap
    await api_client.put(
        "/api/preferences",
        headers=auth(token),
        json={
            "risk_level": "low",
            "preferred_assets": ["USDC"],
            "minimum_yield_difference": 3.0,
            "maximum_gas_cost": 2.0,
        },
    )

    report = (await api_client.get("/api/decisions/scan", headers=auth(token))).json()
    assert report["allowed_count"] == 0
    assert report["blocked_count"] == report["recommendation_count"]

    blocked_reasons = {r["reasons"][0] for r in report["recommendations"]}
    assert any("gas cost" in reason for reason in blocked_reasons)
    assert any("delta" in reason for reason in blocked_reasons)
    # the 34% farm is blocked by the low-risk APY ceiling (among other rules)
    farm = next(
        r for r in report["recommendations"] if r["opportunity"]["protocol"] == "yield-farm-9000"
    )
    failing = {c["rule"] for c in farm["checks"] if not c["passed"]}
    assert "risk_apy_ceiling" in failing
    assert "protocol_risk_tier" in failing


@pytest.mark.asyncio
async def test_audit_event_written_on_scan(api_client, db_session) -> None:
    user = await register(api_client, "audited@example.com")
    await add_wallet_with_position(db_session, uid(user["user"]["id"]))

    await api_client.get("/api/decisions/scan", headers=auth(user["access_token"]))
    events = (await db_session.execute(select(AuditLog.event))).scalars().all()
    assert "decision.scanned" in events


@pytest.mark.asyncio
async def test_unauthenticated_rejected(api_client) -> None:
    assert (await api_client.get("/api/decisions/scan")).status_code == 401


# ------------------------------------------------------------- mock client


@pytest.mark.asyncio
async def test_mock_client_returns_deterministic_data() -> None:
    client = MockKeeperHubClient()
    first = await client.get_opportunities("USDC", CHAIN)
    second = await client.get_opportunities("usdc", CHAIN)
    assert first == second  # case-insensitive, deterministic
    assert len(first) == len(MOCK_MARKET[CHAIN]["USDC"])
    assert all(o.asset == "USDC" for o in first)
    assert all(o.risk_level.value in {"low", "medium", "high"} for o in first)


@pytest.mark.asyncio
async def test_mock_client_empty_for_unknown_chain() -> None:
    client = MockKeeperHubClient()
    assert await client.get_opportunities("USDC", "999") == []
