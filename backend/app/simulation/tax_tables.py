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
    FilingStatus.SINGLE: Decimal("15750"),
    FilingStatus.MARRIED_JOINT: Decimal("31500"),
    FilingStatus.MARRIED_SEPARATE: Decimal("15750"),
    FilingStatus.HEAD_OF_HOUSEHOLD: Decimal("23625"),
}

FEDERAL_BRACKETS_2026: dict[FilingStatus, list[Bracket]] = {
    FilingStatus.SINGLE: [
        (Decimal("12400"), Decimal("0.10")), (Decimal("50400"), Decimal("0.12")),
        (Decimal("105700"), Decimal("0.22")), (Decimal("201775"), Decimal("0.24")),
        (Decimal("256225"), Decimal("0.32")), (Decimal("640600"), Decimal("0.35")),
        (None, Decimal("0.37")),
    ],
    FilingStatus.MARRIED_JOINT: [
        (Decimal("24800"), Decimal("0.10")), (Decimal("100800"), Decimal("0.12")),
        (Decimal("211400"), Decimal("0.22")), (Decimal("403550"), Decimal("0.24")),
        (Decimal("512450"), Decimal("0.32")), (Decimal("768700"), Decimal("0.35")),
        (None, Decimal("0.37")),
    ],
    FilingStatus.MARRIED_SEPARATE: [
        (Decimal("12400"), Decimal("0.10")), (Decimal("50400"), Decimal("0.12")),
        (Decimal("105700"), Decimal("0.22")), (Decimal("201775"), Decimal("0.24")),
        (Decimal("256225"), Decimal("0.32")), (Decimal("384350"), Decimal("0.35")),
        (None, Decimal("0.37")),
    ],
    FilingStatus.HEAD_OF_HOUSEHOLD: [
        (Decimal("17700"), Decimal("0.10")), (Decimal("67450"), Decimal("0.12")),
        (Decimal("105700"), Decimal("0.22")), (Decimal("201750"), Decimal("0.24")),
        (Decimal("256200"), Decimal("0.32")), (Decimal("640600"), Decimal("0.35")),
        (None, Decimal("0.37")),
    ],
}

STANDARD_DEDUCTION_2026: dict[FilingStatus, Decimal] = {
    FilingStatus.SINGLE: Decimal("16100"),
    FilingStatus.MARRIED_JOINT: Decimal("32200"),
    FilingStatus.MARRIED_SEPARATE: Decimal("16100"),
    FilingStatus.HEAD_OF_HOUSEHOLD: Decimal("24150"),
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

CONTRIBUTION_LIMITS_2026 = {
    "401k_employee": Decimal("24500"),
    "401k_employee_catchup_50plus": Decimal("8000"),
    "ira": Decimal("7500"),
    "ira_catchup_50plus": Decimal("1100"),
    "hsa_individual": Decimal("4400"),
    "hsa_family": Decimal("8750"),
}

DEFAULT_TAX_YEAR = 2026

BRACKETS_BY_YEAR = {2025: FEDERAL_BRACKETS_2025, 2026: FEDERAL_BRACKETS_2026}
DEDUCTIONS_BY_YEAR = {2025: STANDARD_DEDUCTION_2025, 2026: STANDARD_DEDUCTION_2026}
LIMITS_BY_YEAR = {2025: CONTRIBUTION_LIMITS_2025, 2026: CONTRIBUTION_LIMITS_2026}


def get_brackets(tax_year: int, filing_status: FilingStatus) -> list[Bracket]:
    if tax_year not in BRACKETS_BY_YEAR:
        raise ValueError(f"No bracket table loaded for tax year {tax_year}")
    return BRACKETS_BY_YEAR[tax_year][filing_status]


def get_standard_deduction(tax_year: int, filing_status: FilingStatus) -> Decimal:
    if tax_year not in DEDUCTIONS_BY_YEAR:
        raise ValueError(f"No standard deduction loaded for tax year {tax_year}")
    return DEDUCTIONS_BY_YEAR[tax_year][filing_status]


def get_contribution_limits(tax_year: int) -> dict[str, Decimal]:
    if tax_year not in LIMITS_BY_YEAR:
        raise ValueError(f"No contribution limits loaded for tax year {tax_year}")
    return LIMITS_BY_YEAR[tax_year]
