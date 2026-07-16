"""TaxCalculationService — federal + state estimate, HSA/Roth comparisons.

Backs `estimate_taxes`, `calculate_hsa_tax_savings`, and
`calculate_roth_vs_traditional` AI tools, plus any `/simulations/tax*`
route added in a later phase.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.enums import FilingStatus
from app.simulation import tax_tables
from app.simulation.engine import compound_growth, estimate_federal_tax

ZERO = Decimal("0")

# Flat-rate state tax approximations for planning purposes only. A real
# implementation would load state-specific bracket tables the same way
# tax_tables.py does for federal; this keeps the interface stable for that
# swap (callers pass a state code, not a rate).
STATE_FLAT_RATE_ESTIMATES: dict[str, Decimal] = {
    "CA": Decimal("0.093"),
    "NY": Decimal("0.0685"),
    "NJ": Decimal("0.0637"),
    "TX": Decimal("0"),
    "FL": Decimal("0"),
    "WA": Decimal("0"),
    "MA": Decimal("0.05"),
    "IL": Decimal("0.0495"),
}
DEFAULT_STATE_RATE = Decimal("0.05")


@dataclass(slots=True, frozen=True)
class TaxEstimate:
    tax_year: int
    filing_status: FilingStatus
    taxable_income: Decimal
    federal_tax: Decimal
    state_tax: Decimal
    total_tax: Decimal
    effective_rate: Decimal
    marginal_federal_rate: Decimal


@dataclass(slots=True, frozen=True)
class RothVsTraditionalResult:
    traditional_after_tax_value_at_retirement: Decimal
    roth_after_tax_value_at_retirement: Decimal
    preferred: str
    rationale: str


class TaxCalculationService:
    def estimate(
        self,
        gross_income: Decimal,
        filing_status: FilingStatus,
        state: str | None = None,
        pretax_deductions: Decimal = ZERO,
        itemized_deduction: Decimal | None = None,
        tax_year: int = tax_tables.DEFAULT_TAX_YEAR,
    ) -> TaxEstimate:
        taxable_before_std_deduction = max(ZERO, gross_income - pretax_deductions)
        federal = estimate_federal_tax(
            taxable_before_std_deduction, filing_status, tax_year, itemized_deduction
        )
        state_rate = STATE_FLAT_RATE_ESTIMATES.get((state or "").upper(), DEFAULT_STATE_RATE)
        state_tax = (federal["taxable_income"] * state_rate).quantize(Decimal("0.01"))
        total_tax = federal["total_tax"] + state_tax
        effective_rate = (total_tax / gross_income).quantize(Decimal("0.0001")) if gross_income > ZERO else ZERO

        return TaxEstimate(
            tax_year=tax_year,
            filing_status=filing_status,
            taxable_income=federal["taxable_income"],
            federal_tax=federal["total_tax"],
            state_tax=state_tax,
            total_tax=total_tax,
            effective_rate=effective_rate,
            marginal_federal_rate=federal["marginal_rate"],
        )

    def calculate_hsa_tax_savings(
        self,
        annual_hsa_contribution: Decimal,
        marginal_federal_rate: Decimal,
        state_rate: Decimal = ZERO,
        fica_rate: Decimal = Decimal("0.0765"),
    ) -> Decimal:
        """HSA contributions are triple tax-advantaged; this estimates the
        immediate payroll-tax-year savings (federal + state + FICA) from
        contributing pretax via payroll, not the long-run growth benefit
        (use RetirementProjectionService for that)."""
        combined_rate = marginal_federal_rate + state_rate + fica_rate
        return (annual_hsa_contribution * combined_rate).quantize(Decimal("0.01"))

    def calculate_roth_vs_traditional(
        self,
        annual_contribution: Decimal,
        years_to_retirement: int,
        expected_return: Decimal,
        current_marginal_rate: Decimal,
        expected_retirement_marginal_rate: Decimal,
    ) -> RothVsTraditionalResult:
        """Classic comparison: traditional gets a tax deduction now and is
        taxed on withdrawal; Roth is taxed now and grows tax-free. Both
        contribute the same pretax dollar amount here so the comparison
        isolates the effect of *when* the tax is paid.
        """
        # Traditional: full pretax amount grows, then taxed at withdrawal.
        traditional_future_value = compound_growth(
            annual_contribution, expected_return, years_to_retirement
        )
        # Approximation using a lump-sum growth of a single year's contribution,
        # annualized comparison is intentional here — this tool answers "is
        # Roth or Traditional better for my next dollar", not a full schedule
        # (that's RetirementProjectionService's job for the full account).
        traditional_after_tax = traditional_future_value * (
            Decimal("1") - expected_retirement_marginal_rate
        )

        # Roth: contribution is taxed today, then grows tax-free.
        roth_contribution_after_tax = annual_contribution * (Decimal("1") - current_marginal_rate)
        roth_future_value = compound_growth(
            roth_contribution_after_tax, expected_return, years_to_retirement
        )

        if roth_future_value >= traditional_after_tax:
            preferred = "roth"
            rationale = (
                "Your current marginal rate is at or below your expected retirement "
                "rate, so paying tax today (Roth) leaves more after-tax value."
            )
        else:
            preferred = "traditional"
            rationale = (
                "Your expected retirement marginal rate is below your current rate, "
                "so deferring tax (Traditional) leaves more after-tax value."
            )

        return RothVsTraditionalResult(
            traditional_after_tax_value_at_retirement=traditional_after_tax.quantize(Decimal("0.01")),
            roth_after_tax_value_at_retirement=roth_future_value.quantize(Decimal("0.01")),
            preferred=preferred,
            rationale=rationale,
        )
