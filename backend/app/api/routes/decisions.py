"""Decision-engine routes (authenticated, user-scoped)."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user
from backend.app.schemas.decisions import (
    OpportunityResponse,
    RecommendationResponse,
    ScanReport,
)
from backend.app.services import decisions as decisions_service
from database.models import User
from database.session import get_db

router = APIRouter(prefix="/decisions", tags=["decisions"])

db_dep = Annotated[AsyncSession, Depends(get_db)]
current_user_dep = Annotated[User, Depends(get_current_user)]


@router.get("/scan", response_model=ScanReport)
async def scan(db: db_dep, user: current_user_dep) -> ScanReport:
    """Scan the caller's positions and recommend best moves under their policy."""
    report = await decisions_service.analyze(db, user)

    recommendations = [
        RecommendationResponse(
            wallet_address=r.wallet_address,
            chain=r.chain,
            current_protocol=r.current_protocol,
            asset=r.asset,
            amount=r.amount,
            current_apy=r.current_apy,
            opportunity=OpportunityResponse(
                protocol=r.opportunity.protocol,
                asset=r.opportunity.asset,
                chain=r.opportunity.chain,
                apy=r.opportunity.apy,
                risk_level=r.opportunity.risk_level,
                estimated_gas=r.opportunity.estimated_gas,
            ),
            delta_apy=r.delta_apy,
            allowed=r.allowed,
            reasons=r.decision.reasons,
            checks=[c.__dict__ for c in r.decision.checks],
        )
        for r in report["recommendations"]
    ]

    return ScanReport(
        scanned_at=datetime.now(UTC),
        recommendation_count=len(recommendations),
        allowed_count=int(report["allowed_count"]),
        blocked_count=int(report["blocked_count"]),
        summary=str(report["summary"]),
        recommendations=recommendations,
    )
