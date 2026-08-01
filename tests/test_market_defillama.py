"""Tests for the DefiLlama yields market source."""

import httpx
import pytest

from agent.keeperhub.client import YieldOpportunity
from agent.keeperhub.errors import MarketDataUnavailableError
from agent.market.defillama import (
    PROTOCOL_ALIASES,
    _map_pool,
    _normalize_protocol,
    _risk_level,
    fetch_yields,
)
from database.models import RiskLevel


def sample_pools() -> dict:
    return {
        "data": [
            {
                "chain": "Ethereum",
                "project": "aave-v3",
                "symbol": "USDC",
                "apy": 5.2,
                "category": "Lending",
                "tvlUsd": 1_000_000_000,
            },
            {
                "chain": "Ethereum",
                "project": "morpho-blue",
                "symbol": "USDC",
                "apy": 8.1,
                "category": "Lending",
                "tvlUsd": 500_000_000,
            },
            {
                "chain": "Ethereum",
                "project": "fluid",
                "symbol": "USDC",
                "apy": 12.0,
                "category": "Yield",
                "tvlUsd": 200_000_000,
            },
            {
                "chain": "Ethereum",
                "project": "aave-v3",
                "symbol": "USDT",
                "apy": 5.0,
                "category": "Lending",
                "tvlUsd": 900_000_000,
            },
            {
                "chain": "Base",
                "project": "morpho-blue",
                "symbol": "USDC",
                "apy": 7.0,
                "category": "Lending",
                "tvlUsd": 100_000_000,
            },
            {
                "chain": "Ethereum",
                "project": "unsupported",
                "symbol": "USDC",
                "apy": 0.0,
                "category": "Lending",
                "tvlUsd": 0,
            },
        ]
    }


def make_transport(payload: dict):
    return httpx.MockTransport(
        lambda request: httpx.Response(200, json=payload)
    )


async def test_fetch_yields_filters_sorts_and_caps() -> None:
    client = httpx.AsyncClient(transport=make_transport(sample_pools()))
    opportunities = await fetch_yields(
        "usdc", "1", http_client=client, max_pools=2, default_gas=2.0
    )
    assert [op.protocol for op in opportunities] == ["fluid", "morpho"]
    assert [op.apy for op in opportunities] == [12.0, 8.1]
    assert all(op.estimated_gas == 2.0 for op in opportunities)
    assert all(op.asset == "USDC" for op in opportunities)
    assert all(op.chain == "1" for op in opportunities)
    await client.aclose()


async def test_fetch_yields_maps_sepolia_to_ethereum_market() -> None:
    client = httpx.AsyncClient(transport=make_transport(sample_pools()))
    opportunities = await fetch_yields(
        "USDC", "11155111", http_client=client, max_pools=20, default_gas=2.0
    )
    assert len(opportunities) == 3  # Base + USDT + zero-apy excluded
    await client.aclose()


async def test_fetch_yields_unknown_chain_returns_empty() -> None:
    client = httpx.AsyncClient(transport=make_transport(sample_pools()))
    opportunities = await fetch_yields(
        "USDC", "999", http_client=client, max_pools=20, default_gas=2.0
    )
    assert opportunities == []
    await client.aclose()


async def test_fetch_yields_surfaces_http_errors() -> None:
    def fail(request):
        raise httpx.ConnectError("boom", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(fail))
    with pytest.raises(MarketDataUnavailableError):
        await fetch_yields(
            "USDC", "1", http_client=client, max_pools=20, default_gas=2.0
        )
    await client.aclose()


async def test_fetch_yields_raises_on_non_200() -> None:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(500, json={})
        )
    )
    with pytest.raises(MarketDataUnavailableError):
        await fetch_yields(
            "USDC", "1", http_client=client, max_pools=20, default_gas=2.0
        )
    await client.aclose()


def test_protocol_normalization() -> None:
    assert _normalize_protocol("morpho-blue") == "morpho"
    assert _normalize_protocol("Morpho-Blue") == "morpho"
    assert _normalize_protocol("aave") == "aave-v3"
    assert _normalize_protocol("fluid") == "fluid"
    assert PROTOCOL_ALIASES["morpho-blue"] == "morpho"


def test_risk_level_heuristic() -> None:
    assert _risk_level("USDC", "Lending") == RiskLevel.LOW
    assert _risk_level("USDT", "Yield") == RiskLevel.LOW
    assert _risk_level("WBTC", "Lending") == RiskLevel.MEDIUM
    assert _risk_level("WBTC", "Leveraged") == RiskLevel.HIGH
    assert _risk_level("ETH", "Liquid Staking") == RiskLevel.HIGH


def test_map_pool_skips_zero_apy_and_blank_symbol() -> None:
    assert (
        _map_pool(
            {"symbol": "USDC", "apy": 0.0, "project": "x", "category": "Lending"},
            "1",
            2.0,
        )
        is None
    )
    assert (
        _map_pool(
            {"symbol": "", "apy": 5.0, "project": "x", "category": "Lending"},
            "1",
            2.0,
        )
        is None
    )
    mapped = _map_pool(
        {
            "symbol": "USDC",
            "apy": 5.0,
            "project": "aave-v3",
            "category": "Lending",
        },
        "1",
        2.0,
    )
    assert isinstance(mapped, YieldOpportunity)
    assert mapped.protocol == "aave-v3"
