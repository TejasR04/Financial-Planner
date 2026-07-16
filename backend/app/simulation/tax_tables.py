"""Federal tax bracket data, versioned by year.

These are illustrative brackets intended for long-horizon planning
projections, not tax filing. `TaxCalculationService` should surface the
`tax_year` it used so the frontend/agent can disclose that. Update this
table annually; never inline bracket numbers anywhere else in the codebase.
"""
from __future__ import annotations

from decimal import Decimal

from app.domain.enums import FilingStatus

# (upper_bound_of_bracket, marginal_rate) — last bracket upper_bound is None (unbounded)
Bracket = tuple[Decimal | None, Decimal]

FEDERAL_BRACKETS_2025: dict[FilingStatus, list[Bracket]] = {
    FilingStatus.SINGLE: [
        (Decimal("11925"), Decimal("0.10")),
        (Decimal("48475"), Decimal("0.12")),
        (Decimal("103350"), Decimal("0.22")),
        (Decimal("197300"), Decimal("0.24")),
        (Decimal("250525"), Decimal("0.32")),
        (Decimal("626350"), Decimal("0.35")),
        (None, Decimal("0.37")),
    ],
    FilingStatus.MARRIED_JOINT: [
        (Decimal("23850"), Decimal("0.10")),
        (Decimal("96950"), Decimal("0.12")),
        (Decimal("206700"), Decimal("0.22")),
        (Decimal("394600"), Decimal("0.24")),
        (Decimal("501050"), Decimal("0.32")),
        (Decimal("751600"), Decimal("0.35")),
        (None, Decimal("0.37")),
    ],
    FilingStatus.MARRIED_SEPARATE: [
        (Decimal("11925"), Decimal("0.10")),
        (Decimal("48475"), Decimal("0.12")),
        (Decimal("103350"), Decimal("0.22")),
        (Decimal("197300"), Decimal("0.24")),
        (Decimal("250525"), Decimal("0.32")),
        (Decimal("375800"), Decimal("0.35")),
        (None, Decimal("0.37")),
    ],
    FilingStatus.HEAD_OF_HOUSEHOLD: [
        (Decimal("17000"), Decimal("0.10")),
        (Decimal("64850"), Decimal("0.12")),
        (Decimal("103350"), Decimal("0.22")),
        (Decimal("197300"), Decimal("0.24")),
        (Decimal("250500"), Decimal("0.32")),
        (Decimal("626350"), Decimal("0.35")),
        (None, Decimal("0.37")),
    ],
}

STANDARD_DEDUCTION_2025: dict[FilingStatus, Decimal] = {
    FilingStatus.SINGLE: Decimal("15000"),
    FilingStatus.MARRIED_JOINT: Decimal("30000"),
    FilingStatus.MARRIED_SEPARATE: Decimal("15000"),
    FilingStatus.HEAD_OF_HOUSEHOLD: Decimal("22500"),
}

# IRS annual contribution limits, by year.
CONTRIBUTION_LIMITS_2025 = {
    "401k_employee": Decimal("23500"),
    "401k_employee_catchup_50plus": Decimal("7500"),
    "ira": Decimal("7000"),
    "ira_catchup_50plus": Decimal("1000"),
    "hsa_individual": Decimal("4300"),
    "hsa_family": Decimal("8550"),
}

DEFAULT_TAX_YEAR = 2025


def get_brackets(tax_year: int, filing_status: FilingStatus) -> list[Bracket]:
    if tax_year != DEFAULT_TAX_YEAR:
        # Only one table is loaded today; documented extension point.
        raise ValueError(f"No bracket table loaded for tax year {tax_year}")
    return FEDERAL_BRACKETS_2025[filing_status]


def get_standard_deduction(tax_year: int, filing_status: FilingStatus) -> Decimal:
    if tax_year != DEFAULT_TAX_YEAR:
        raise ValueError(f"No standard deduction loaded for tax year {tax_year}")
    return STANDARD_DEDUCTION_2025[filing_status]


def get_contribution_limits(tax_year: int) -> dict[str, Decimal]:
    if tax_year != DEFAULT_TAX_YEAR:
        raise ValueError(f"No contribution limits loaded for tax year {tax_year}")
    return CONTRIBUTION_LIMITS_2025
