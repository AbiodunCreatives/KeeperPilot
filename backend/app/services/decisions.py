"""Decision engine: scan tracked positions, evaluate candidates, recommend.

Orchestrates the pieces of Task 5:
* load the user's active wallets and their positions (eager-loaded),
* pull candidate opportunities from the KeeperHub client (mock today),
* run each candidate through the risk-policy engine,
* rank (allowed first, then by APY delta) and emit an explainable report.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agent.keeperhub.client import YieldOpportunity, get_keeperhub_client
from agent.reasoning.summary import RecommendationView, summarize_scan
from backend.app.core.config import get_settings
from backend.app.services import preferences as preferences_service
from backend.app.services.policies import PolicyDecision, evaluate_opportunity
from database.models import AuditLog, User, Wallet, WalletStatus


@dataclass
class Recommendation:
    """One evaluated candidate for one position."""

    wallet_address: str
    chain: str
    current_protocol: str
    asset: str
    amount: Decimal
    current_apy: float
    opportunity: YieldOpportunity
    delta_apy: float
    decision: PolicyDecision

    @property
    def allowed(self) -> bool:
        return self.decision.allowed

    def to_view(self) -> RecommendationView:
        return RecommendationView(
            asset=self.asset,
            amount=self.amount,
            current_protocol=self.current_protocol,
            opportunity_protocol=self.opportunity.protocol,
            delta_apy=self.delta_apy,
            allowed=self.allowed,
            reasons=self.decision.reasons,
        )


async def scan_user_opportunities(db: AsyncSession, user: User) -> list[Recommendation]:
    """Evaluate every candidate opportunity for every tracked position."""
    settings = get_settings()
    prefs = await preferences_service.get_preferences(db, user)
    client = get_keeperhub_client(settings)

    stmt = (
        select(Wallet)
        .where(Wallet.user_id == user.id, Wallet.status == WalletStatus.ACTIVE)
        .options(selectinload(Wallet.positions))
    )
    wallets = list((await db.execute(stmt)).scalars().all())

    recommendations: list[Recommendation] = []
    for wallet in wallets:
        for position in wallet.positions:
            current_apy = float(position.apy)
            opportunities = await client.get_opportunities(position.asset, wallet.chain)
            for opportunity in opportunities:
                if opportunity.protocol.lower() == position.protocol.lower():
                    continue  # same venue -> not a move
                decision = evaluate_opportunity(
                    prefs,
                    asset=position.asset,
                    current_apy=current_apy,
                    candidate_apy=opportunity.apy,
                    gas_cost=opportunity.estimated_gas,
                    candidate_protocol_risk=opportunity.risk_level,
                )
                recommendations.append(
                    Recommendation(
                        wallet_address=wallet.address,
                        chain=wallet.chain,
                        current_protocol=position.protocol,
                        asset=position.asset,
                        amount=position.amount,
                        current_apy=current_apy,
                        opportunity=opportunity,
                        delta_apy=opportunity.apy - current_apy,
                        decision=decision,
                    )
                )

    # Allowed first (by APY delta desc), then denied (stable order).
    recommendations.sort(key=lambda r: (not r.allowed, -r.delta_apy))
    return recommendations


async def analyze(db: AsyncSession, user: User) -> dict[str, object]:
    """Produce the full scan report and log an audit event."""
    recommendations = await scan_user_opportunities(db, user)
    allowed_count = sum(1 for r in recommendations if r.allowed)
    position_count = len({(r.wallet_address, r.current_protocol, r.asset) for r in recommendations})

    db.add(
        AuditLog(
            event="decision.scanned",
            description=(
                f"analyzed {len(recommendations)} candidate(s) across "
                f"{position_count} position(s); {allowed_count} allowed by policy"
            ),
            user_id=user.id,
        )
    )
    await db.commit()

    summary = summarize_scan([r.to_view() for r in recommendations])
    return {
        "recommendations": recommendations,
        "allowed_count": allowed_count,
        "blocked_count": len(recommendations) - allowed_count,
        "summary": summary,
    }
