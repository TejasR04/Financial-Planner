"""InsightService — produces `Insight` drafts (observation/alert/opportunity),
distinct from `RecommendationEngine`'s actionable `Recommendation` drafts.
Pure Python, composes off the same `FinancialSnapshot` and a computed
`FinancialHealthScore` rather than duplicating any scoring logic.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.entities import FinancialSnapshot
from app.domain.enums import InsightKind
from app.services.financial_health_service import FinancialHealthScore


@dataclass(slots=True, frozen=True)
class InsightDraft:
    kind: InsightKind
    text: str
    meta: str


class InsightService:
    def generate(self, snapshot: FinancialSnapshot, health_score: FinancialHealthScore) -> list[InsightDraft]:
        drafts: list[InsightDraft] = []

        if health_score.liquidity < 40:
            drafts.append(
                InsightDraft(
                    kind=InsightKind.ALERT,
                    text="Liquid savings are below a 6-month expense buffer. Consider building "
                    "an emergency fund before increasing investment contributions.",
                    meta="liquidity",
                )
            )

        if health_score.debt_ratio < 50:
            drafts.append(
                InsightDraft(
                    kind=InsightKind.ALERT,
                    text="Liabilities are large relative to total assets. Paying down "
                    "high-interest debt would meaningfully improve overall financial health.",
                    meta="debt_ratio",
                )
            )

        if health_score.diversification < 70:
            drafts.append(
                InsightDraft(
                    kind=InsightKind.OPPORTUNITY,
                    text="Portfolio allocation has drifted from target. Rebalancing could "
                    "reduce risk without changing your long-term return assumptions.",
                    meta="diversification",
                )
            )

        if health_score.savings_discipline >= 100:
            drafts.append(
                InsightDraft(
                    kind=InsightKind.OBSERVATION,
                    text="Savings rate is at or above target. This is a strong position to "
                    "increase retirement contributions if there's IRS headroom available.",
                    meta="savings_discipline",
                )
            )

        if snapshot.net_worth > 0 and not drafts:
            drafts.append(
                InsightDraft(
                    kind=InsightKind.OBSERVATION,
                    text="No urgent issues detected across liquidity, debt, diversification, "
                    "or savings discipline based on current data.",
                    meta="overall",
                )
            )

        return drafts
