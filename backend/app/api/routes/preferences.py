"""User preferences routes (authenticated, user-scoped)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user
from backend.app.schemas.preferences import (
    DecisionRequest,
    DecisionResponse,
    PolicyCheckResponse,
    PreferencesResponse,
    PreferencesUpdate,
)
from backend.app.services import policies
from backend.app.services import preferences as preferences_service
from database.models import RiskLevel, User, UserPreferences
from database.session import get_db

router = APIRouter(prefix="/preferences", tags=["preferences"])

db_dep = Annotated[AsyncSession, Depends(get_db)]
current_user_dep = Annotated[User, Depends(get_current_user)]


def _response(prefs: UserPreferences) -> PreferencesResponse:
    return PreferencesResponse.model_validate(prefs)


@router.get("", response_model=PreferencesResponse)
async def get_preferences(
    db: db_dep, user: current_user_dep
) -> PreferencesResponse:
    """Return the caller's policy knobs (defaults if never customized)."""
    prefs = await preferences_service.get_preferences(db, user)
    return _response(prefs)


@router.put("", response_model=PreferencesResponse)
async def update_preferences(
    payload: PreferencesUpdate,
    db: db_dep,
    user: current_user_dep,
) -> PreferencesResponse:
    """Upsert the caller's policy knobs; omitted fields keep their current value."""
    prefs = await preferences_service.upsert_preferences(db, user, payload)
    return _response(prefs)


@router.post("/decide", response_model=DecisionResponse)
async def decide(
    payload: DecisionRequest,
    db: db_dep,
    user: current_user_dep,
) -> DecisionResponse:
    """Evaluate a candidate opportunity against the caller's policy.

    This is the gate the agent consults before acting (Task 5+).
    """
    prefs = await preferences_service.get_preferences(db, user)
    decision = policies.evaluate_opportunity(
        prefs,
        asset=payload.asset,
        current_apy=payload.current_apy,
        candidate_apy=payload.candidate_apy,
        gas_cost=payload.gas_cost,
        candidate_protocol_risk=(
            RiskLevel(payload.candidate_protocol_risk)
            if payload.candidate_protocol_risk is not None
            else None
        ),
    )
    return DecisionResponse(
        allowed=decision.allowed,
        reasons=decision.reasons,
        checks=[PolicyCheckResponse(**c.__dict__) for c in decision.checks],
    )
