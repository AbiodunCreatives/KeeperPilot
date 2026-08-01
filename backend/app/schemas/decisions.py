"""Pydantic schemas for decision-engine scan reports."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from backend.app.schemas.preferences import PolicyCheckResponse
from database.models import RiskLevel


class OpportunityResponse(BaseModel):
    """A candidate destination protocol."""

    protocol: str
    asset: str
    chain: str
    apy: float
    risk_level: RiskLevel
    estimated_gas: float


class RecommendationResponse(BaseModel):
    """One evaluated candidate, with the policy verdict behind it."""

    wallet_address: str
    chain: str
    current_protocol: str
    asset: str
    amount: Decimal
    current_apy: float
    opportunity: OpportunityResponse
    delta_apy: float
    allowed: bool
    reasons: list[str]
    checks: list[PolicyCheckResponse]


class ScanReport(BaseModel):
    """The full scan: ranked recommendations plus a plain-language briefing."""

    scanned_at: datetime
    recommendation_count: int
    allowed_count: int
    blocked_count: int
    summary: str
    recommendations: list[RecommendationResponse]
