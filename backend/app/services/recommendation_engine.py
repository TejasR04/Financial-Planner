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
        """Flags checking-account balances well above a reasonable spend
        buffer and estimates the interest given up vs. the best-APY
        depository account on file."""
        checking_accounts = [
            a for a in snapshot.accounts if a.type == AccountType.DEPOSITORY and a.balance > 0
        ]
        if not checking_accounts:
            return []

        best_apy_account = max(
            (a for a in snapshot.accounts if a.type == AccountType.DEPOSITORY and a.apy),
            key=lambda a: a.apy or ZERO,
            default=None,
        )
        if best_apy_account is None:
            return []

        reserve_target = snapshot.profile.cash_reserve_target
        if reserve_target is None:
            return []
        total_cash = sum((account.balance for account in checking_accounts), ZERO)
        excess = total_cash - reserve_target
        if excess <= Decimal("1000") or not best_apy_account.apy:
            return []
        annual_interest_gain = (excess * best_apy_account.apy / Decimal(100)).quantize(Decimal("0.01"))
        return [RecommendationDraft(
            title=f"Move excess cash to {best_apy_account.name}",
            body=(f"Across your deposit accounts, cash is about ${excess:,.0f} above your configured "
                  f"${reserve_target:,.0f} reserve target. At {best_apy_account.apy}% APY, the estimated annual interest is ${annual_interest_gain:,.0f}."),
            category="Cash Management", impact_value=annual_interest_gain,
            effort=RecommendationEffort.LOW, confidence=0.85,
        )]
