"""RecommendationEngine — composes other services into ranked, explainable
recommendations. Contains no financial math of its own: every number in a
Recommendation traces back to a call into another service.

Backs `GET/POST /recommendations` and the `generate_financial_health_score`
tool's sibling, `get_recommendations`.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import uuid4

from app.domain.entities import FinancialSnapshot
from app.domain.enums import AccountType, RecommendationEffort, RecommendationStatus

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
        drafts.extend(self._retirement_headroom_rule(snapshot))
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

        drafts = []
        spend_buffer = Decimal("12000")  # a simple placeholder; a later phase
        # should derive this from CashFlowProjectionService's monthly expense
        # figure (e.g. 1x projected monthly expenses) rather than a constant.
        for account in checking_accounts:
            if account.id == best_apy_account.id:
                continue
            idle = account.balance - spend_buffer
            if idle <= Decimal("1000"):
                continue
            annual_interest_gain = (idle * (best_apy_account.apy or ZERO) / Decimal(100)).quantize(Decimal("0.01"))
            drafts.append(
                RecommendationDraft(
                    title=f"Sweep idle cash from {account.name} into {best_apy_account.name}",
                    body=(
                        f"{account.name} is holding roughly ${idle:,.0f} above a reasonable "
                        f"spend buffer. Moving it to {best_apy_account.name} at "
                        f"{best_apy_account.apy}% APY yields incremental interest with no "
                        "liquidity impact."
                    ),
                    category="Cash Management",
                    impact_value=annual_interest_gain,
                    effort=RecommendationEffort.LOW,
                    confidence=0.85,
                )
            )
        return drafts

    def _retirement_headroom_rule(self, snapshot: FinancialSnapshot) -> list[RecommendationDraft]:
        """Flags contribution headroom against the current-year 401(k)
        limit using the same engine primitive the AI tool layer calls."""
        from app.simulation.engine import contribution_limit_headroom

        retirement_income_sources = [s for s in snapshot.income_sources if s.active]
        if not retirement_income_sources:
            return []

        # In a fuller model this would read the user's actual elected
        # contribution rate from a RetirementAccount entity; using zero here
        # as an explicit placeholder for "no election on file yet".
        planned_contribution = ZERO
        age = snapshot.user.age_on(snapshot.as_of) or 30
        headroom = contribution_limit_headroom(planned_contribution, "401k_employee", age)
        if headroom["headroom"] <= ZERO:
            return []

        return [
            RecommendationDraft(
                title="Elect a 401(k) contribution to capture available tax-advantaged space",
                body=(
                    f"You have ${headroom['headroom']:,.0f} of unused 401(k) contribution "
                    "room this year based on the IRS limit. Electing a contribution "
                    "captures tax-deferred growth on that headroom."
                ),
                category="Retirement",
                impact_value=headroom["headroom"],
                effort=RecommendationEffort.LOW,
                confidence=0.7,
            )
        ]
