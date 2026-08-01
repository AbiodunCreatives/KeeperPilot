"""Pydantic schemas for user preferences and policy evaluation."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from database.models import RiskLevel


class PreferencesUpdate(BaseModel):
    """Partial update of a user's policy knobs. Omitted fields are kept."""

    risk_level: RiskLevel | None = None
    preferred_assets: list[str] | None = Field(default=None, max_length=20)
    minimum_yield_difference: float | None = Field(default=None, ge=0, le=100)
    maximum_gas_cost: float | None = Field(default=None, ge=0, le=10000)

    @field_validator("preferred_assets")
    @classmethod
    def _normalize_assets(cls, assets: list[str] | None) -> list[str] | None:
        if assets is None:
            return None
        seen: dict[str, str] = {}
        for asset in assets:
            token = asset.strip().upper()
            if not token or len(token) > 16 or not token.replace("-", "").isalnum():
                raise ValueError(f"Invalid asset symbol: {asset!r}")
            seen[token] = token
        return sorted(seen)


class PreferencesResponse(BaseModel):
    """Full preference state. Mirrors the ORM row plus defaults for a fresh user."""

    model_config = ConfigDict(from_attributes=True)

    risk_level: RiskLevel
    preferred_assets: list[str]
    minimum_yield_difference: float
    maximum_gas_cost: float
    updated_at: datetime | None = None


class DecisionRequest(BaseModel):
    """A candidate opportunity for the agent to consider."""

    asset: str = Field(min_length=1, max_length=16)
    current_apy: float = Field(ge=0, le=10000)
    candidate_apy: float = Field(ge=0, le=10000)
    gas_cost: float = Field(ge=0, le=100000)
    candidate_protocol_risk: RiskLevel | None = None


class PolicyCheckResponse(BaseModel):
    """Outcome of one policy rule."""

    rule: str
    passed: bool
    detail: str


class DecisionResponse(BaseModel):
    """Allow/deny verdict with per-rule detail for explanations and audit."""

    allowed: bool
    reasons: list[str]
    checks: list[PolicyCheckResponse]
