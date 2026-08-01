"""Execution service tests: lifecycle, guardrails, policy re-check, isolation."""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from agent.keeperhub.client import ExecutionReceipt
from backend.app.services import executions as executions_service
from database.models import (
    AuditLog,
    Execution,
    ExecutionStatus,
    Position,
    User,
    Wallet,
    WalletStatus,
)

CHAIN = "11155111"
TARGET = "fluid"


async def register(client, email: str) -> dict:
    resp = await client.post("/api/auth/register", json={"email": email})
    assert resp.status_code == 201
    return resp.json()


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def setup_user(client, db_session, email: str) -> dict:
    user = await register(client, email)
    wallet = Wallet(
        user_id=uuid.UUID(user["user"]["id"]),
        address="0x2222222222222222222222222222222222222222",
        chain=CHAIN,
        status=WalletStatus.ACTIVE,
    )
    db_session.add(wallet)
    await db_session.flush()
    db_session.add(
        Position(
            wallet_id=wallet.id,
            protocol="aave-v3",
            asset="USDC",
            amount=Decimal("10000"),
            apy=Decimal("4.0"),
        )
    )
    await db_session.commit()
    return {**user, "wallet_id": str(wallet.id)}


def exec_body(wallet_id: str, **overrides) -> dict:
    body = {
        "wallet_id": wallet_id,
        "asset": "USDC",
        "source_protocol": "aave-v3",
        "target_protocol": TARGET,
    }
    body.update(overrides)
    return body


class FailingClient:
    async def submit(self, action):
        return ExecutionReceipt(tx_hash="0x" + "ab" * 32, status="failed")

    async def get_receipt(self, tx_hash):
        return ExecutionReceipt(tx_hash=tx_hash, status="failed")


# ------------------------------------------------------------- happy lifecycle


@pytest.mark.asyncio
async def test_full_lifecycle(api_client, db_session) -> None:
    user = await setup_user(api_client, db_session, "lifecycle@example.com")
    token = user["access_token"]

    created = await api_client.post(
        "/api/executions", headers=auth(token), json=exec_body(user["wallet_id"])
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] == "pending"
    assert body["action"] == "migrate_yield"
    assert body["source_protocol"] == "aave-v3"
    assert body["target_protocol"] == "fluid"
    assert "Migrate USDC" in body["reason"]
    exec_id = body["id"]

    approved = await api_client.post(
        f"/api/executions/{exec_id}/approve", headers=auth(token)
    )
    assert approved.status_code == 200
    body = approved.json()
    # mock completes immediately: pending -> approved -> submitted -> completed
    assert body["status"] == "completed"
    assert body["transaction_hash"].startswith("0x")
    assert body["transaction_hash"] and len(body["transaction_hash"]) == 66
    assert body["completed_at"] is not None

    # audit trail links to the execution
    events = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.execution_id == uuid.UUID(exec_id))
        )
    ).scalars().all()
    event_names = [e.event for e in events]
    assert "execution.created" in event_names
    assert "execution.approved" in event_names
    assert "execution.submitted" in event_names
    assert "execution.completed" in event_names

    # list + get
    listed = (await api_client.get("/api/executions", headers=auth(token))).json()
    assert [e["id"] for e in listed] == [exec_id]
    got = (await api_client.get(f"/api/executions/{exec_id}", headers=auth(token))).json()
    assert got["status"] == "completed"


@pytest.mark.asyncio
async def test_approve_persists_transition_when_submitted_still_in_flight(
    api_client, db_session
) -> None:
    user = await setup_user(api_client, db_session, "inflight@example.com")
    token = user["access_token"]
    created = (
        await api_client.post(
            "/api/executions", headers=auth(token), json=exec_body(user["wallet_id"])
        )
    ).json()
    exec_id = created["id"]

    user_obj = await db_session.get(User, uuid.UUID(user["user"]["id"]))


    class SlowClient:
        async def submit(self, action):
            return ExecutionReceipt(tx_hash="0x" + "cd" * 32, status="submitted")

    result = await executions_service.approve_execution(
        db_session, user_obj, uuid.UUID(exec_id), client=SlowClient()
    )
    assert result.status == ExecutionStatus.SUBMITTED
    assert result.transaction_hash == "0x" + "cd" * 32

    refreshed = await executions_service.refresh_execution(
        db_session, user_obj, uuid.UUID(exec_id), client=FailingClient()
    )
    assert refreshed.status == ExecutionStatus.FAILED
    assert refreshed.completed_at is not None


# ------------------------------------------------------------- guardrails


@pytest.mark.asyncio
async def test_create_rejects_policy_blocked_move(api_client, db_session) -> None:
    user = await setup_user(api_client, db_session, "blocked@example.com")
    token = user["access_token"]
    await api_client.put(
        "/api/preferences",
        headers=auth(token),
        json={"risk_level": "low", "minimum_yield_difference": 3.0, "maximum_gas_cost": 2.0},
    )
    # fluid: delta 4.4pp ok, but gas 2.2 > 2 -> blocked by policy
    resp = await api_client.post(
        "/api/executions", headers=auth(token), json=exec_body(user["wallet_id"])
    )
    assert resp.status_code == 400
    assert "blocked by policy" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_rejects_same_protocol_move(api_client, db_session) -> None:
    user = await setup_user(api_client, db_session, "sameproto@example.com")
    resp = await api_client.post(
        "/api/executions",
        headers=auth(user["access_token"]),
        json=exec_body(user["wallet_id"], target_protocol="aave-v3"),
    )
    assert resp.status_code == 400
    assert "current protocol" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_rejects_unknown_target(api_client, db_session) -> None:
    user = await setup_user(api_client, db_session, "badtarget@example.com")
    resp = await api_client.post(
        "/api/executions",
        headers=auth(user["access_token"]),
        json=exec_body(user["wallet_id"], target_protocol="not-a-protocol"),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_duplicate_in_flight_execution_rejected(api_client, db_session) -> None:
    user = await setup_user(api_client, db_session, "dup@example.com")
    token = user["access_token"]
    first = await api_client.post(
        "/api/executions", headers=auth(token), json=exec_body(user["wallet_id"])
    )
    assert first.status_code == 201
    second = await api_client.post(
        "/api/executions", headers=auth(token), json=exec_body(user["wallet_id"])
    )
    assert second.status_code == 409
    assert "already in flight" in second.json()["detail"]


@pytest.mark.asyncio
async def test_state_machine_guards(api_client, db_session) -> None:
    user = await setup_user(api_client, db_session, "statemachine@example.com")
    token = user["access_token"]
    exec_id = (
        await api_client.post(
            "/api/executions", headers=auth(token), json=exec_body(user["wallet_id"])
        )
    ).json()["id"]

    # approve -> completed; further transitions are rejected
    await api_client.post(f"/api/executions/{exec_id}/approve", headers=auth(token))
    for action in ("approve", "reject", "cancel"):
        resp = await api_client.post(
            f"/api/executions/{exec_id}/{action}", headers=auth(token)
        )
        assert resp.status_code == 400, action

    # reject a pending execution works
    exec2 = (
        await api_client.post(
            "/api/executions", headers=auth(token), json=exec_body(user["wallet_id"])
        )
    ).json()  # duplicate guardrail released after first completed
    rejected = await api_client.post(
        f"/api/executions/{exec2['id']}/reject", headers=auth(token)
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"

    # cancel a pending execution works
    exec3 = (
        await api_client.post(
            "/api/executions", headers=auth(token), json=exec_body(user["wallet_id"])
        )
    ).json()
    cancelled = await api_client.post(
        f"/api/executions/{exec3['id']}/cancel", headers=auth(token)
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


# ------------------------------------------------------------- isolation


@pytest.mark.asyncio
async def test_cross_user_access_rejected(api_client, db_session) -> None:
    user_a = await setup_user(api_client, db_session, "alice@example.com")
    user_b = await setup_user(api_client, db_session, "bob@example.com")

    exec_id = (
        await api_client.post(
            "/api/executions",
            headers=auth(user_a["access_token"]),
            json=exec_body(user_a["wallet_id"]),
        )
    ).json()["id"]

    # B cannot fetch A's execution (GET -> 404)
    fetched = await api_client.get(
        f"/api/executions/{exec_id}", headers=auth(user_b["access_token"])
    )
    assert fetched.status_code == 404
    # B cannot act on A's execution (POST -> 404)
    for action in ("approve", "reject"):
        resp = await api_client.post(
            f"/api/executions/{exec_id}/{action}", headers=auth(user_b["access_token"])
        )
        assert resp.status_code == 404, action

    listed_b = await api_client.get("/api/executions", headers=auth(user_b["access_token"]))
    assert listed_b.json() == []


@pytest.mark.asyncio
async def test_unauthenticated_rejected(api_client) -> None:
    assert (await api_client.get("/api/executions")).status_code == 401
    assert (await api_client.post("/api/executions", json={})).status_code == 401


# ------------------------------------------------------------- failure path


@pytest.mark.asyncio
async def test_submit_failure_marks_execution_failed(api_client, db_session) -> None:
    user = await setup_user(api_client, db_session, "fails@example.com")
    exec_id = (
        await api_client.post(
            "/api/executions",
            headers=auth(user["access_token"]),
            json=exec_body(user["wallet_id"]),
        )
    ).json()["id"]

    user_obj = await db_session.get(User, uuid.UUID(user["user"]["id"]))
    result = await executions_service.approve_execution(
        db_session, user_obj, uuid.UUID(exec_id), client=FailingClient()
    )
    assert result.status == ExecutionStatus.FAILED
    assert result.transaction_hash == "0x" + "ab" * 32

    row = await db_session.get(Execution, uuid.UUID(exec_id))
    assert row.status == ExecutionStatus.FAILED
