"""User preferences & risk policy tests: CRUD, validation, isolation, decision engine."""

import pytest
from sqlalchemy import select

from backend.app.services.policies import RISK_APY_CEILINGS, evaluate_opportunity
from database.models import AuditLog, RiskLevel, UserPreferences

CHAIN = "11155111"


async def register(client, email: str) -> str:
    resp = await client.post("/api/auth/register", json={"email": email})
    assert resp.status_code == 201
    return resp.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ------------------------------------------------------------- defaults & CRUD


@pytest.mark.asyncio
async def test_get_returns_defaults_for_fresh_user(api_client) -> None:
    token = await register(api_client, "fresh@example.com")
    resp = await api_client.get("/api/preferences", headers=auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "medium"
    assert data["preferred_assets"] == []
    assert data["minimum_yield_difference"] == 2.0
    assert data["maximum_gas_cost"] == 5.0


@pytest.mark.asyncio
async def test_put_creates_then_updates(api_client, db_session) -> None:
    token = await register(api_client, "savvy@example.com")
    headers = auth(token)

    created = await api_client.put(
        "/api/preferences",
        headers=headers,
        json={
            "risk_level": "low",
            "preferred_assets": ["USDC", "DAI"],
            "minimum_yield_difference": 3.5,
            "maximum_gas_cost": 2.0,
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["risk_level"] == "low"
    assert body["preferred_assets"] == ["DAI", "USDC"]
    assert body["minimum_yield_difference"] == 3.5

    updated = await api_client.put(
        "/api/preferences", headers=headers, json={"risk_level": "high"}
    )
    body = updated.json()
    assert body["risk_level"] == "high"
    assert body["preferred_assets"] == ["DAI", "USDC"]  # partial keeps the rest
    assert body["maximum_gas_cost"] == 2.0

    # persisted
    row = (await db_session.execute(select(UserPreferences))).scalar_one()
    assert row.user_id is not None
    assert row.risk_level == RiskLevel.HIGH

    # audit event written
    events = (await db_session.execute(select(AuditLog.event))).scalars().all()
    assert "preferences.updated" in events


@pytest.mark.asyncio
async def test_asset_normalization(api_client) -> None:
    token = await register(api_client, "norm@example.com")
    resp = await api_client.put(
        "/api/preferences",
        headers=auth(token),
        json={"preferred_assets": [" usdc ", "USDC", "usdt", "ETH"]},
    )
    assert resp.status_code == 200
    assert resp.json()["preferred_assets"] == ["ETH", "USDC", "USDT"]


# ------------------------------------------------------------- validation


@pytest.mark.asyncio
async def test_rejects_invalid_risk_level(api_client) -> None:
    token = await register(api_client, "badrisk@example.com")
    resp = await api_client.put(
        "/api/preferences", headers=auth(token), json={"risk_level": "extreme"}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_rejects_negative_values(api_client) -> None:
    token = await register(api_client, "neg@example.com")
    for payload in [
        {"minimum_yield_difference": -1},
        {"maximum_gas_cost": -0.01},
    ]:
        resp = await api_client.put("/api/preferences", headers=auth(token), json=payload)
        assert resp.status_code == 422, payload


@pytest.mark.asyncio
async def test_rejects_bad_asset_symbols(api_client) -> None:
    token = await register(api_client, "badasset@example.com")
    for assets in [
        ["not an asset"],
        ["WAYTOOLONGASSETNAME"],
        ["GOOD", ""],
    ]:
        resp = await api_client.put(
            "/api/preferences", headers=auth(token), json={"preferred_assets": assets}
        )
        assert resp.status_code == 422, assets


# ------------------------------------------------------------- isolation


@pytest.mark.asyncio
async def test_unauthenticated_rejected(api_client) -> None:
    assert (await api_client.get("/api/preferences")).status_code == 401
    assert (await api_client.post("/api/preferences/decide", json={})).status_code == 401


@pytest.mark.asyncio
async def test_preferences_are_per_user(api_client) -> None:
    token_a = await register(api_client, "prefa@example.com")
    token_b = await register(api_client, "prefb@example.com")
    await api_client.put(
        "/api/preferences",
        headers=auth(token_a),
        json={"risk_level": "high", "preferred_assets": ["USDC"]},
    )
    resp_b = await api_client.get("/api/preferences", headers=auth(token_b))
    assert resp_b.json()["risk_level"] == "medium"
    assert resp_b.json()["preferred_assets"] == []


# ----------------------------------------------------- policy engine (unit)


def make_prefs(**overrides) -> UserPreferences:
    defaults = {
        "risk_level": RiskLevel.MEDIUM,
        "preferred_assets": [],
        "minimum_yield_difference": 2.0,
        "maximum_gas_cost": 5.0,
    }
    defaults.update(overrides)
    return UserPreferences(**defaults)


def test_policy_allows_good_opportunity() -> None:
    prefs = make_prefs()
    decision = evaluate_opportunity(
        prefs, asset="USDC", current_apy=4.0, candidate_apy=7.5, gas_cost=1.2
    )
    assert decision.allowed is True
    assert decision.reasons == []


def test_policy_denies_insufficient_yield_delta() -> None:
    prefs = make_prefs(minimum_yield_difference=2.0)
    decision = evaluate_opportunity(
        prefs, asset="USDC", current_apy=6.0, candidate_apy=6.5, gas_cost=1.0
    )
    assert decision.allowed is False
    assert any("minimum_yield_difference" == c.rule and not c.passed for c in decision.checks)
    assert any("delta" in r for r in decision.reasons)


def test_policy_denies_expensive_gas() -> None:
    prefs = make_prefs(maximum_gas_cost=5.0)
    decision = evaluate_opportunity(
        prefs, asset="USDC", current_apy=4.0, candidate_apy=8.0, gas_cost=9.0
    )
    assert decision.allowed is False
    assert any("maximum_gas_cost" == c.rule and not c.passed for c in decision.checks)


def test_policy_denies_asset_outside_preference() -> None:
    prefs = make_prefs(preferred_assets=["USDC"])
    decision = evaluate_opportunity(
        prefs, asset="DAI", current_apy=4.0, candidate_apy=9.0, gas_cost=1.0
    )
    assert decision.allowed is False
    assert any("preferred_assets" == c.rule and not c.passed for c in decision.checks)
    # asset matching is case-insensitive
    ok = evaluate_opportunity(
        prefs, asset="usdc", current_apy=4.0, candidate_apy=9.0, gas_cost=1.0
    )
    assert ok.allowed is True


def test_policy_empty_preferred_assets_means_no_restriction() -> None:
    prefs = make_prefs(preferred_assets=[])
    decision = evaluate_opportunity(
        prefs, asset="SOL", current_apy=4.0, candidate_apy=9.0, gas_cost=1.0
    )
    assert decision.allowed is True
    assert not any(c.rule == "preferred_assets" for c in decision.checks)


def test_policy_low_risk_enforces_apy_ceiling() -> None:
    prefs = make_prefs(risk_level=RiskLevel.LOW)
    assert RISK_APY_CEILINGS[RiskLevel.LOW] == 10.0
    decision = evaluate_opportunity(
        prefs, asset="USDC", current_apy=4.0, candidate_apy=11.5, gas_cost=1.0
    )
    assert decision.allowed is False
    assert any("risk_apy_ceiling" == c.rule and not c.passed for c in decision.checks)

    inside = evaluate_opportunity(
        prefs, asset="USDC", current_apy=4.0, candidate_apy=9.5, gas_cost=1.0
    )
    assert inside.allowed is True


def test_policy_high_risk_has_no_apy_ceiling() -> None:
    prefs = make_prefs(risk_level=RiskLevel.HIGH)
    assert RISK_APY_CEILINGS[RiskLevel.HIGH] is None
    decision = evaluate_opportunity(
        prefs, asset="USDC", current_apy=4.0, candidate_apy=95.0, gas_cost=1.0
    )
    assert decision.allowed is True
    assert not any(c.rule == "risk_apy_ceiling" for c in decision.checks)


def test_policy_protocol_risk_tier_must_fit_tolerance() -> None:
    prefs = make_prefs(risk_level=RiskLevel.LOW)
    decision = evaluate_opportunity(
        prefs,
        asset="USDC",
        current_apy=4.0,
        candidate_apy=6.0,
        gas_cost=1.0,
        candidate_protocol_risk=RiskLevel.HIGH,
    )
    assert decision.allowed is False
    assert any("protocol_risk_tier" == c.rule and not c.passed for c in decision.checks)

    ok = evaluate_opportunity(
        prefs,
        asset="USDC",
        current_apy=4.0,
        candidate_apy=6.0,
        gas_cost=1.0,
        candidate_protocol_risk=RiskLevel.LOW,
    )
    assert ok.allowed is True


# ----------------------------------------------------- policy engine (HTTP)


@pytest.mark.asyncio
async def test_decide_endpoint_allows_and_denies(api_client) -> None:
    token = await register(api_client, "decider@example.com")
    headers = auth(token)

    good = await api_client.post(
        "/api/preferences/decide",
        headers=headers,
        json={"asset": "USDC", "current_apy": 4.0, "candidate_apy": 8.0, "gas_cost": 1.0},
    )
    assert good.status_code == 200
    assert good.json()["allowed"] is True
    assert good.json()["reasons"] == []

    bad = await api_client.post(
        "/api/preferences/decide",
        headers=headers,
        json={"asset": "USDC", "current_apy": 4.0, "candidate_apy": 4.2, "gas_cost": 1.0},
    )
    assert bad.status_code == 200
    assert bad.json()["allowed"] is False
    assert any("delta" in r for r in bad.json()["reasons"])


@pytest.mark.asyncio
async def test_decide_uses_saved_preferences(api_client) -> None:
    token = await register(api_client, "strict@example.com")
    headers = auth(token)
    await api_client.put(
        "/api/preferences",
        headers=headers,
        json={"risk_level": "low", "preferred_assets": ["USDC"], "minimum_yield_difference": 5.0},
    )
    resp = await api_client.post(
        "/api/preferences/decide",
        headers=headers,
        json={
            "asset": "DAI",
            "current_apy": 4.0,
            "candidate_apy": 6.0,
            "gas_cost": 1.0,
            "candidate_protocol_risk": "high",
        },
    )
    data = resp.json()
    assert data["allowed"] is False
    failing = {c["rule"] for c in data["checks"] if not c["passed"]}
    assert failing == {"preferred_assets", "minimum_yield_difference", "protocol_risk_tier"}

    inside = await api_client.post(
        "/api/preferences/decide",
        headers=headers,
        json={"asset": "USDC", "current_apy": 3.0, "candidate_apy": 9.0, "gas_cost": 1.0},
    )
    assert inside.json()["allowed"] is True
