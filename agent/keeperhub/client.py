"""KeeperHub client: mock market + executor for development/tests, real MCP stub.

KeeperHub is the execution layer. This package reads market/yield data and
submits executions. The mock is deterministic and fully offline.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from decimal import Decimal
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


@dataclass(frozen=True)
class ExecutionAction:
    """Everything KeeperHub needs to move an asset between venues."""

    wallet_address: str
    chain: str
    asset: str
    amount: Decimal
    source_protocol: str
    target_protocol: str
    estimated_gas: float


@dataclass(frozen=True)
class ExecutionReceipt:
    """Result of a submitted execution."""

    tx_hash: str
    status: str  # "submitted" | "completed" | "failed"


class KeeperHubClient(Protocol):
    async def get_opportunities(self, asset: str, chain: str) -> list[YieldOpportunity]:
        """Return yield opportunities for an asset on a chain."""

    async def submit(self, action: ExecutionAction) -> ExecutionReceipt:
        """Request an execution through KeeperHub."""

    async def get_receipt(self, tx_hash: str) -> ExecutionReceipt:
        """Poll the on-chain result of a submitted execution."""


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

    async def submit(self, action: ExecutionAction) -> ExecutionReceipt:
        """Simulate an immediate, successful on-chain execution.

        The tx hash is a stable function of the action, so re-submitting the
        same action yields the same hash (idempotency visible in tests).
        """
        digest = hashlib.sha256(
            json.dumps(asdict(action), default=str).encode()
        ).hexdigest()
        return ExecutionReceipt(tx_hash=f"0x{digest[:64]}", status="completed")

    async def get_receipt(self, tx_hash: str) -> ExecutionReceipt:
        return ExecutionReceipt(tx_hash=tx_hash, status="completed")


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

    async def submit(self, action: ExecutionAction) -> ExecutionReceipt:
        raise NotImplementedError(
            "Live KeeperHub execution requires the Task 7 MCP wiring"
        )

    async def get_receipt(self, tx_hash: str) -> ExecutionReceipt:
        raise NotImplementedError(
            "Live KeeperHub execution requires the Task 7 MCP wiring"
        )


def get_keeperhub_client(settings: Settings | None = None) -> KeeperHubClient:
    """Return the mock or real client based on settings."""
    settings = settings or get_settings()
    if settings.keeperhub_mock:
        return MockKeeperHubClient()
    return KeeperHubMCPClient(settings.keeperhub_api_key, settings.keeperhub_mcp_url)
