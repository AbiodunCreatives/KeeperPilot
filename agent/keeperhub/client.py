"""KeeperHub client: mock market for development/tests, real MCP client stub.

KeeperHub is the execution layer — this package only *reads* market/yield data
here; submitting executions is the Task 7 concern.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from agent.keeperhub.mock_data import MOCK_MARKET
from backend.app.core.config import Settings, get_settings
from database.models import RiskLevel


@dataclass(frozen=True)
class YieldOpportunity:
    """A candidate destination for a user's asset."""

    protocol: str
    asset: str
    chain: str
    apy: float
    risk_level: RiskLevel
    estimated_gas: float


class KeeperHubClient(Protocol):
    async def get_opportunities(self, asset: str, chain: str) -> list[YieldOpportunity]:
        """Return yield opportunities for an asset on a chain."""


class MockKeeperHubClient:
    """Deterministic in-process market — no network, no credentials."""

    async def get_opportunities(self, asset: str, chain: str) -> list[YieldOpportunity]:
        asset = asset.upper()
        rows = MOCK_MARKET.get(chain, {}).get(asset, [])
        return [
            YieldOpportunity(
                protocol=str(row["protocol"]),
                asset=asset,
                chain=chain,
                apy=float(row["apy"]),
                risk_level=RiskLevel(str(row["risk"])),
                estimated_gas=float(row["estimated_gas"]),
            )
            for row in rows
        ]


class KeeperHubMCPClient:
    """Real KeeperHub client.

    Requires credentials (``KEEPERHUB_MOCK=false`` + ``KEEPERHUB_API_KEY``).
    Full MCP wiring lands in Task 7 together with execution.
    """

    def __init__(self, api_key: str, mcp_url: str) -> None:
        if not api_key:
            raise RuntimeError(
                "KEEPERHUB_MOCK is false but KEEPERHUB_API_KEY is not set"
            )
        self.api_key = api_key
        self.mcp_url = mcp_url

    async def get_opportunities(self, asset: str, chain: str) -> list[YieldOpportunity]:
        raise NotImplementedError(
            "Live KeeperHub market data requires the Task 7 MCP wiring"
        )


def get_keeperhub_client(settings: Settings | None = None) -> KeeperHubClient:
    """Return the mock or real client based on settings."""
    settings = settings or get_settings()
    if settings.keeperhub_mock:
        return MockKeeperHubClient()
    return KeeperHubMCPClient(settings.keeperhub_api_key, settings.keeperhub_mcp_url)
