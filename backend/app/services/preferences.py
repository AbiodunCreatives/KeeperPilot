"""User preferences service: read/upsert, scoped to the authenticated user."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.schemas.preferences import PreferencesUpdate
from backend.app.services.policies import (
    DEFAULT_MAXIMUM_GAS_COST,
    DEFAULT_MINIMUM_YIELD_DIFFERENCE,
)
from database.models import AuditLog, RiskLevel, User, UserPreferences


async def get_preferences(
    db: AsyncSession, user: User
) -> UserPreferences:
    """Return stored preferences, or a transient object holding defaults."""
    prefs = await _find(db, user.id)
    if prefs is not None:
        return prefs
    return UserPreferences(
        user_id=user.id,
        risk_level=RiskLevel.MEDIUM,
        preferred_assets=[],
        minimum_yield_difference=DEFAULT_MINIMUM_YIELD_DIFFERENCE,
        maximum_gas_cost=DEFAULT_MAXIMUM_GAS_COST,
    )


async def upsert_preferences(
    db: AsyncSession, user: User, payload: PreferencesUpdate
) -> UserPreferences:
    """Create on first use, otherwise update only the provided fields."""
    prefs = await _find(db, user.id)
    if prefs is None:
        prefs = UserPreferences(user_id=user.id)
        db.add(prefs)
        await db.flush()  # apply column defaults (risk_level, assets, etc.)

    if payload.risk_level is not None:
        prefs.risk_level = payload.risk_level
    if payload.preferred_assets is not None:
        prefs.preferred_assets = payload.preferred_assets
    if payload.minimum_yield_difference is not None:
        prefs.minimum_yield_difference = payload.minimum_yield_difference
    if payload.maximum_gas_cost is not None:
        prefs.maximum_gas_cost = payload.maximum_gas_cost

    db.add(
        AuditLog(
            event="preferences.updated",
            description=(
                f"risk={prefs.risk_level.value} assets={prefs.preferred_assets} "
                f"min_yield={prefs.minimum_yield_difference}pp max_gas=${prefs.maximum_gas_cost}"
            ),
            user_id=user.id,
        )
    )
    await db.commit()
    await db.refresh(prefs)
    return prefs


async def _find(db: AsyncSession, user_id: object) -> UserPreferences | None:
    stmt = select(UserPreferences).where(UserPreferences.user_id == user_id)
    return (await db.execute(stmt)).scalar_one_or_none()
