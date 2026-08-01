"""Contract tests for the real KeeperHub MCP client.

These exercise the exact transport the production client uses — Streamable
HTTP over the MCP protocol with a Bearer API key — against a local fake
KeeperHub MCP server, so no KeeperHub credentials are required.
"""

import json
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx2 import AsyncClient
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from agent.keeperhub import mcp_client
from agent.keeperhub.client import ExecutionAction, MockKeeperHubClient, get_keeperhub_client
from agent.keeperhub.errors import (
    KeeperHubAuthenticationError,
    KeeperHubExecutionError,
    KeeperHubUnavailableError,
)
from agent.keeperhub.mcp_client import KeeperHubMCPClient
from backend.app.core.config import Settings
from tests.fakes.keeperhub_mcp import FakeKeeperHubMCP

TEST_KEY = "kh_test_key"


def make_settings(**overrides) -> Settings:
    """Build settings accepting short names for the keeperhub_* fields."""
    short_names = {
        "mock": "keeperhub_mock",
        "timeout": "keeperhub_request_timeout",
        "max_retries": "keeperhub_max_retries",
        "retry_backoff": "keeperhub_retry_backoff",
        "poll_interval": "keeperhub_poll_interval",
        "poll_max_attempts": "keeperhub_poll_max_attempts",
        "max_pools": "keeperhub_market_max_pools",
        "default_gas": "keeperhub_default_gas_usd",
    }
    mapped = {short_names.get(k, k): v for k, v in overrides.items()}
    defaults = {
        "keeperhub_mock": False,
        "keeperhub_max_retries": 2,
        "keeperhub_retry_backoff": 0.01,
        "keeperhub_poll_interval": 0.05,
        "keeperhub_poll_max_attempts": 10,
    }
    defaults.update(mapped)
    return Settings(**defaults)


@pytest_asyncio.fixture(scope="module")
def mcp_server():
    fake = FakeKeeperHubMCP()
    url = fake.start()
    yield fake, url
    fake.stop()


@pytest.fixture()
def fake(mcp_server):
    server, _ = mcp_server
    server.reset()
    return server


def build_client(
    url: str,
    *,
    token: str = TEST_KEY,
    http_token: str | None = None,
    **settings_overrides,
) -> KeeperHubMCPClient:
    http_token = TEST_KEY if http_token is None else http_token
    return KeeperHubMCPClient(
        token,
        url,
        settings=make_settings(**settings_overrides),
        http_client=AsyncClient(
            headers={"Authorization": f"Bearer {http_token}"}
        ),
    )


def sample_action(**overrides) -> ExecutionAction:
    fields = {
        "wallet_address": "0xabc123",
        "chain": "11155111",
        "asset": "USDC",
        "amount": Decimal("1000"),
        "source_protocol": "aave-v3",
        "target_protocol": "fluid",
        "estimated_gas": 2.0,
    }
    fields.update(overrides)
    return ExecutionAction(**fields)


async def test_tools_listed_over_mcp(mcp_server) -> None:
    _, url = mcp_server
    async with streamable_http_client(
        url,
        http_client=AsyncClient(headers={"Authorization": f"Bearer {TEST_KEY}"}),
    ) as streams:
        async with ClientSession(streams[0], streams[1]) as session:
            await session.initialize()
            tools = await session.list_tools()
    names = {tool.name for tool in tools.tools}
    assert {
        "list_action_schemas",
        "execute_protocol_action",
        "get_direct_execution_status",
        "get_wallet_integration",
        "list_integrations",
        "search_protocol_actions",
        "tools_documentation",
    } <= names


async def test_submit_executes_both_legs_and_preflights_wallet(mcp_server, fake) -> None:
    _, url = mcp_server
    client = build_client(url)

    receipt = await client.submit(sample_action())

    assert receipt.status == "submitted"
    ids = json.loads(receipt.tx_hash)["executions"]
    assert len(ids) == 2

    tool_calls = [name for name, _ in fake.calls]
    assert tool_calls.count("list_integrations") == 1
    legs = [args for name, args in fake.calls if name == "execute_protocol_action"]
    assert [leg["actionType"] for leg in legs] == ["aave-v3/withdraw", "fluid/supply"]
    withdraw_params, supply_params = (leg["params"] for leg in legs)
    for params in (withdraw_params, supply_params):
        assert params["network"] == "11155111"
        assert params["asset"] == "USDC"
        assert params["amount"] == "1000"
    assert withdraw_params["to"] == "0xabc123"
    assert "onBehalfOf" not in withdraw_params
    assert supply_params["onBehalfOf"] == "0xabc123"
    assert "to" not in supply_params

    await client._http_client.aclose()


async def test_get_receipt_polls_until_completed(mcp_server, fake) -> None:
    _, url = mcp_server
    client = build_client(url)

    receipt = await client.submit(sample_action())
    final = await client.get_receipt(receipt.tx_hash)

    assert final.status == "completed"
    poll_calls = [
        args
        for name, args in fake.calls
        if name == "get_direct_execution_status"
    ]
    assert len(poll_calls) >= 2  # both legs polled at least once

    await client._http_client.aclose()


async def test_get_receipt_bounded_when_execution_stays_in_flight(mcp_server, fake) -> None:
    fake.reset(completion_after_polls=100)
    _, url = mcp_server
    client = build_client(url, poll_interval=0.01, poll_max_attempts=3)

    receipt = await client.submit(sample_action())
    final = await client.get_receipt(receipt.tx_hash)

    assert final.status == "submitted"
    poll_calls = [
        args
        for name, args in fake.calls
        if name == "get_direct_execution_status"
    ]
    # bounded: 3 attempts x 2 legs
    assert len(poll_calls) == 6

    await client._http_client.aclose()


async def test_submit_rejects_without_wallet_integration() -> None:
    fake = FakeKeeperHubMCP(wallet_configured=False)
    url = fake.start()
    try:
        client = build_client(url)
        with pytest.raises(KeeperHubExecutionError) as excinfo:
            await client.submit(sample_action())
        assert "wallet" in str(excinfo.value).lower()
        await client._http_client.aclose()
    finally:
        fake.stop()


async def test_submit_rejects_unknown_action_type(mcp_server, fake) -> None:
    _, url = mcp_server
    client = build_client(url)

    action = sample_action(target_protocol="not-a-protocol")
    with pytest.raises(KeeperHubExecutionError) as excinfo:
        await client.submit(action)
    assert "unknown action type" in str(excinfo.value)

    await client._http_client.aclose()


async def test_wrong_api_key_maps_to_authentication_error() -> None:
    fake = FakeKeeperHubMCP()
    url = fake.start()
    try:
        client = build_client(url, token="kh_wrong_key", http_token="kh_wrong_key")
        with pytest.raises(KeeperHubAuthenticationError):
            await client._call_tool("list_action_schemas", {"category": "web3"})
        await client._http_client.aclose()
    finally:
        fake.stop()


async def test_transient_500_is_retried_and_recovers() -> None:
    fake = FakeKeeperHubMCP(fail_first_http_status=500)
    url = fake.start()
    try:
        client = build_client(url)
        result = await client._call_tool(
            "list_action_schemas", {"category": "web3"}
        )
        assert "actions" in result.content[0].text
        await client._http_client.aclose()
    finally:
        fake.stop()


async def test_unreachable_server_raises_unavailable_after_retries() -> None:
    import socket

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    client = build_client(
        f"http://127.0.0.1:{port}/mcp",
        max_retries=1,
        retry_backoff=0.01,
    )
    with pytest.raises(KeeperHubUnavailableError):
        await client._call_tool("list_action_schemas", {"category": "web3"})
    await client._http_client.aclose()


async def test_get_opportunities_delegates_to_market_source(mcp_server, fake, monkeypatch) -> None:
    _, url = mcp_server
    client = build_client(url)

    async def fake_fetch(asset, chain, *, max_pools=None, default_gas=None):
        assert asset == "USDC"
        assert chain == "11155111"
        return [{"protocol": "fluid", "apy": 12.0}]

    monkeypatch.setattr(mcp_client, "fetch_yields", fake_fetch)

    opportunities = await client.get_opportunities("USDC", "11155111")
    assert opportunities == [{"protocol": "fluid", "apy": 12.0}]

    await client._http_client.aclose()


def test_factory_selects_mock_and_real_clients() -> None:
    assert isinstance(
        get_keeperhub_client(Settings(keeperhub_mock=True)), MockKeeperHubClient
    )
    real = get_keeperhub_client(
        Settings(keeperhub_mock=False, keeperhub_api_key="kh_test")
    )
    assert isinstance(real, KeeperHubMCPClient)

    with pytest.raises(RuntimeError):
        KeeperHubMCPClient("", "https://app.keeperhub.com/mcp")
