"""RecommendationEngine — composes other services into ranked, explainable
recommendations. Contains no financial math of its own: every number in a
Recommendation traces back to a call into another service.

Backs `GET/POST /recommendations` and the `generate_financial_health_score`
tool's sibling, `get_recommendations`.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from app.domain.entities import FinancialSnapshot
from app.domain.enums import AccountType, RecommendationEffort

ZERO = Decimal("0")


@dataclass(slots=True, frozen=True)
class RecommendationDraft:
    title: str
    body: str
    category: str
    impact_value: Decimal
    effort: RecommendationEffort
    confidence: float


class RecommendationEngine:
    """Rule-based v1: each rule inspects the snapshot (already assembled
    from real account/income data) and, if triggered, produces a draft with
    an impact figure computed by calling the relevant service. This is
    intentionally simple and extensible — later phases can add
    model-scored rules without changing the shape callers see
    (`list[RecommendationDraft]`).
    """

    def generate(self, snapshot: FinancialSnapshot) -> list[RecommendationDraft]:
        drafts: list[RecommendationDraft] = []
        drafts.extend(self._idle_cash_rule(snapshot))
        # Retirement headroom is intentionally suppressed until the product
        # models plan eligibility and the user's actual contribution election.
        return sorted(drafts, key=lambda d: d.impact_value, reverse=True)

    def _idle_cash_rule(self, snapshot: FinancialSnapshot) -> list[RecommendationDraft]:
        """Estimate incremental yield from moving excess low-yield cash."""
        cash_accounts = [
            a for a in snapshot.accounts if a.type == AccountType.DEPOSITORY and a.balance > 0
        ]
        if not cash_accounts:
            return []

        best_apy_account = max(
            (a for a in cash_accounts if a.apy is not None),
            key=lambda a: a.apy or ZERO,
            default=None,
        )
        if best_apy_account is None:
            return []

        reserve_target = snapshot.profile.cash_reserve_target
        if reserve_target is None:
            return []
        total_cash = sum((account.balance for account in cash_accounts), ZERO)
        excess = total_cash - reserve_target
        if excess <= Decimal("1000") or not best_apy_account.apy:
            return []

        # Move only enough low-yield source cash to account for the total
        # amount above the reserve. Funds already in the destination neither
        # need moving nor generate a new benefit.
        remaining_to_move = excess
        moved = ZERO
        annual_interest_gain = ZERO
        weighted_source_interest = ZERO
        sources = sorted(
            (a for a in cash_accounts if a.id != best_apy_account.id),
            key=lambda a: a.apy or ZERO,
        )
        for source in sources:
            source_apy = source.apy or ZERO
            apy_spread = best_apy_account.apy - source_apy
            if apy_spread <= ZERO or remaining_to_move <= ZERO:
                continue
            transfer = min(source.balance, remaining_to_move)
            moved += transfer
            remaining_to_move -= transfer
            annual_interest_gain += transfer * apy_spread / Decimal("100")
            weighted_source_interest += transfer * source_apy

        if moved <= Decimal("1000") or annual_interest_gain <= ZERO:
            return []
        annual_interest_gain = annual_interest_gain.quantize(Decimal("0.01"))
        current_weighted_apy = (weighted_source_interest / moved).quantize(Decimal("0.01"))
        return [RecommendationDraft(
            title=f"Move excess cash to {best_apy_account.name}",
            body=(f"Move about ${moved:,.0f} of cash above your configured "
                  f"${reserve_target:,.0f} reserve target from accounts averaging "
                  f"{current_weighted_apy}% APY to {best_apy_account.apy}% APY. "
                  f"The estimated incremental annual interest is ${annual_interest_gain:,.0f} before tax."),
            category="Cash Management", impact_value=annual_interest_gain,
            effort=RecommendationEffort.LOW, confidence=0.85,
        )]
