"""Risk-policy engine: turns user preferences into an allow/deny decision.

Pure functions — no I/O — so the decision loop (Task 5+) and the audit dashboard
(Task 9) can both reuse them. Every check produces a `PolicyCheck` so rejections
are explainable to the user.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from database.models import RiskLevel, UserPreferences

# Cap on candidate APY implied by each risk tolerance. A capped level means the
# agent will not chase yield above the ceiling (higher APY usually means higher
# risk). HIGH is uncapped.
RISK_APY_CEILINGS: dict[RiskLevel, float | None] = {
    RiskLevel.LOW: 10.0,
    RiskLevel.MEDIUM: 30.0,
    RiskLevel.HIGH: None,
}

# Ordering used to compare a protocol's risk tier against the user's tolerance.
RISK_ORDER: dict[RiskLevel, int] = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
}

DEFAULT_MINIMUM_YIELD_DIFFERENCE = 2.0
DEFAULT_MAXIMUM_GAS_COST = 5.0


@dataclass
class PolicyCheck:
    """Outcome of a single policy rule."""

    rule: str
    passed: bool
    detail: str


@dataclass
class PolicyDecision:
    """Aggregate result of evaluating an opportunity against a user's policy."""

    allowed: bool
    checks: list[PolicyCheck] = field(default_factory=list)

    @property
    def reasons(self) -> list[str]:
        """Human-readable list of every failing rule."""
        return [c.detail for c in self.checks if not c.passed]


def evaluate_opportunity(
    prefs: UserPreferences,
    *,
    asset: str,
    current_apy: float,
    candidate_apy: float,
    gas_cost: float,
    candidate_protocol_risk: RiskLevel | None = None,
) -> PolicyDecision:
    """Decide whether the agent may migrate ``asset`` to a new opportunity.

    All numeric comparisons are in percentage points for APY and USD for gas.
    An empty ``preferred_assets`` list means "no asset restriction".
    """
    checks: list[PolicyCheck] = []
    asset = asset.upper()

    if prefs.preferred_assets:
        allowed_assets = {a.upper() for a in prefs.preferred_assets}
        passed = asset in allowed_assets
        checks.append(
            PolicyCheck(
                "preferred_assets",
                passed,
                f"{asset} allowed by preferred assets"
                if passed
                else f"{asset} not in preferred assets",
            )
        )

    delta = candidate_apy - current_apy
    passed = delta >= prefs.minimum_yield_difference
    checks.append(
        PolicyCheck(
            "minimum_yield_difference",
            passed,
            f"yield delta {delta:.2f}pp >= {prefs.minimum_yield_difference:.2f}pp"
            if passed
            else f"yield delta {delta:.2f}pp < required {prefs.minimum_yield_difference:.2f}pp",
        )
    )

    passed = gas_cost <= prefs.maximum_gas_cost
    checks.append(
        PolicyCheck(
            "maximum_gas_cost",
            passed,
            f"gas cost ${gas_cost:.2f} <= max ${prefs.maximum_gas_cost:.2f}"
            if passed
            else f"gas cost ${gas_cost:.2f} > max ${prefs.maximum_gas_cost:.2f}",
        )
    )

    ceiling = RISK_APY_CEILINGS[prefs.risk_level]
    if ceiling is not None:
        passed = candidate_apy <= ceiling
        checks.append(
            PolicyCheck(
                "risk_apy_ceiling",
                passed,
                f"candidate APY {candidate_apy:.2f}% within "
                f"{prefs.risk_level.value}-risk ceiling of {ceiling:.2f}%"
                if passed
                else f"candidate APY {candidate_apy:.2f}% exceeds "
                f"{prefs.risk_level.value}-risk ceiling of {ceiling:.2f}%",
            )
        )

    if candidate_protocol_risk is not None:
        passed = RISK_ORDER[candidate_protocol_risk] <= RISK_ORDER[prefs.risk_level]
        checks.append(
            PolicyCheck(
                "protocol_risk_tier",
                passed,
                f"protocol risk {candidate_protocol_risk.value} within "
                f"{prefs.risk_level.value} tolerance"
                if passed
                else f"protocol risk {candidate_protocol_risk.value} exceeds "
                f"{prefs.risk_level.value} tolerance",
            )
        )

    return PolicyDecision(allowed=all(c.passed for c in checks), checks=checks)
