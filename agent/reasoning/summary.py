"""Human-readable recommendation summaries.

Template-based today so the scan is explainable without an LLM key; an
LLM-enriched narrative is a later enhancement (OpenAI key is optional).
"""

from __future__ import annotations

from decimal import Decimal


class RecommendationView:
    """Minimal view of a recommendation for summary text."""

    def __init__(
        self,
        *,
        asset: str,
        amount: Decimal | None,
        current_protocol: str,
        opportunity_protocol: str,
        delta_apy: float,
        allowed: bool,
        reasons: list[str],
    ) -> None:
        self.asset = asset
        self.amount = amount
        self.current_protocol = current_protocol
        self.opportunity_protocol = opportunity_protocol
        self.delta_apy = delta_apy
        self.allowed = allowed
        self.reasons = reasons


def _format_amount(amount: Decimal | None) -> str:
    if amount is None:
        return ""
    return f"{amount:.2f}"


def summarize_scan(recommendations: list[RecommendationView]) -> str:
    """Build a short, plain-language briefing of the scan."""
    allowed = [r for r in recommendations if r.allowed]
    denied = [r for r in recommendations if not r.allowed]

    if not recommendations:
        return "No tracked positions to analyze yet. Connect a wallet with a yield position first."

    lines: list[str] = []
    if allowed:
        best = max(allowed, key=lambda r: r.delta_apy)
        lines.append(
            f"Best move: move {_format_amount(best.amount)} {best.asset} "
            f"from {best.current_protocol} to {best.opportunity_protocol} "
            f"for +{best.delta_apy:.2f}pp APY."
        )
        for rec in sorted(allowed, key=lambda r: -r.delta_apy)[1:3]:
            lines.append(
                f"Also actionable: {rec.current_protocol} -> {rec.opportunity_protocol} "
                f"(+{rec.delta_apy:.2f}pp APY)."
            )
    else:
        lines.append("No opportunity currently clears your risk policy.")

    if denied:
        blocked = len({r.reasons[0] for r in denied if r.reasons})
        lines.append(
            f"{len(allowed)} actionable move(s) found; "
            f"{len(denied)} candidate(s) blocked by {blocked} distinct policy rule(s)."
        )
    return " ".join(lines)
