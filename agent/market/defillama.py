"""Real APY market data sourced from the DefiLlama yields API.

DefiLlama does not track testnets, so ``CHAIN_ALIASES`` maps our chain ids to
the mainnet chain DefiLlama uses as a representative market. DefiLlama does not
publish gas estimates, so a configurable default is used for policy checks.
"""

from __future__ import annotations

import httpx

from agent.keeperhub.client import YieldOpportunity
from agent.keeperhub.errors import MarketDataUnavailableError
from backend.app.core.config import get_settings
from database.models import RiskLevel

DEFILLAMA_POOLS_URL = "https://yields.llama.fi/pools"

# Our chain id -> DefiLlama chain name. Testnets fall back to the mainnet
# DefiLlama tracks, since testnet yield venues are not indexed there.
CHAIN_ALIASES = {
    "1": "Ethereum",
    "11155111": "Ethereum",
    "8453": "Base",
    "84532": "Base",
    "42161": "Arbitrum",
    "137": "Polygon",
}

# DefiLlama project slug -> normalized protocol name (matches KeeperHub action
# prefixes such as ``aave-v3/supply`` and the mock market).
PROTOCOL_ALIASES = {
    "aave": "aave-v3",
    "morpho-blue": "morpho",
}

STABLECOIN_SYMBOLS = frozenset(
    {"USDC", "USDT", "DAI", "USDE", "FRAX", "USDS", "LUSD", "PYUSD", "GHO", "USD0"}
)

_RISKY_CATEGORIES = frozenset(
    {"yield", "liquid staking", "leveraged", "boost", "degen"}
)


def _normalize_protocol(project: str) -> str:
    slug = project.lower()
    return PROTOCOL_ALIASES.get(slug, slug)


def _risk_level(symbol: str, category: str) -> RiskLevel:
    if symbol in STABLECOIN_SYMBOLS:
        return RiskLevel.LOW
    if category.lower() in _RISKY_CATEGORIES:
        return RiskLevel.HIGH
    return RiskLevel.MEDIUM


def _map_pool(pool: dict, chain: str, default_gas: float) -> YieldOpportunity | None:
    symbol = str(pool.get("symbol", "")).upper()
    apy = float(pool.get("apy") or 0.0)
    if not symbol or apy <= 0:
        return None
    return YieldOpportunity(
        protocol=_normalize_protocol(str(pool.get("project", ""))),
        asset=symbol,
        chain=chain,
        apy=apy,
        risk_level=_risk_level(symbol, str(pool.get("category", ""))),
        estimated_gas=default_gas,
    )


async def fetch_yields(
    asset: str,
    chain: str,
    *,
    http_client: httpx.AsyncClient | None = None,
    max_pools: int | None = None,
    default_gas: float | None = None,
) -> list[YieldOpportunity]:
    """Fetch and rank yield opportunities for ``asset`` on ``chain``.

    Pools are filtered to the target chain and asset, mapped to
    ``YieldOpportunity``, sorted by APY descending, and capped at ``max_pools``.
    Pass an ``http_client`` (e.g. ``httpx.MockTransport``) for tests; otherwise a
    short-lived client is created.
    """
    asset = asset.upper()
    dl_chain = CHAIN_ALIASES.get(chain, chain)
    settings = get_settings()
    max_pools = settings.keeperhub_market_max_pools if max_pools is None else max_pools
    default_gas = (
        settings.keeperhub_default_gas_usd if default_gas is None else default_gas
    )

    close = http_client is None
    client = http_client or httpx.AsyncClient(timeout=settings.keeperhub_request_timeout)
    try:
        response = await client.get(DEFILLAMA_POOLS_URL)
        response.raise_for_status()
        data = response.json().get("data", [])
    except (httpx.HTTPError, ValueError) as exc:
        raise MarketDataUnavailableError(
            f"DefiLlama yields request failed: {exc}"
        ) from exc
    finally:
        if close:
            await client.aclose()

    pools = [
        pool
        for pool in data
        if str(pool.get("chain", "")).lower() == dl_chain.lower()
        and str(pool.get("symbol", "")).upper() == asset
    ]
    opportunities = [
        mapped
        for pool in pools
        if (mapped := _map_pool(pool, chain, default_gas)) is not None
    ]
    opportunities.sort(key=lambda op: op.apy, reverse=True)
    return opportunities[:max_pools]
