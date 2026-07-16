from decimal import Decimal

from pydantic import BaseModel

from app.ai.tool_registry import registry
from app.domain.enums import FilingStatus
from app.services.tax_calculation_service import TaxCalculationService

_tax_service = TaxCalculationService()


class EstimateTaxesInput(BaseModel):
    gross_income: Decimal
    filing_status: FilingStatus
    state: str | None = None
    pretax_deductions: Decimal = Decimal("0")


@registry.register(
    "estimate_taxes",
    "Estimate federal and state income tax for a given gross income and "
    "filing status. Planning-grade estimate, not a filing calculation.",
    EstimateTaxesInput,
)
def estimate_taxes(args: EstimateTaxesInput):
    return _tax_service.estimate(
        gross_income=args.gross_income,
        filing_status=args.filing_status,
        state=args.state,
        pretax_deductions=args.pretax_deductions,
    )


class HsaTaxSavingsInput(BaseModel):
    annual_hsa_contribution: Decimal
    marginal_federal_rate: Decimal
    state_rate: Decimal = Decimal("0")


@registry.register(
    "calculate_hsa_tax_savings",
    "Calculate the immediate payroll-tax-year savings from contributing to "
    "an HSA pretax (federal + state + FICA).",
    HsaTaxSavingsInput,
)
def calculate_hsa_tax_savings(args: HsaTaxSavingsInput):
    savings = _tax_service.calculate_hsa_tax_savings(
        annual_hsa_contribution=args.annual_hsa_contribution,
        marginal_federal_rate=args.marginal_federal_rate,
        state_rate=args.state_rate,
    )
    return {"annual_tax_savings": savings}


class RothVsTraditionalInput(BaseModel):
    annual_contribution: Decimal
    years_to_retirement: int
    expected_return: Decimal = Decimal("0.065")
    current_marginal_rate: Decimal
    expected_retirement_marginal_rate: Decimal


@registry.register(
    "calculate_roth_vs_traditional",
    "Compare the after-tax retirement value of contributing to a Roth vs. "
    "a Traditional retirement account given current and expected future "
    "marginal tax rates.",
    RothVsTraditionalInput,
)
def calculate_roth_vs_traditional(args: RothVsTraditionalInput):
    return _tax_service.calculate_roth_vs_traditional(
        annual_contribution=args.annual_contribution,
        years_to_retirement=args.years_to_retirement,
        expected_return=args.expected_return,
        current_marginal_rate=args.current_marginal_rate,
        expected_retirement_marginal_rate=args.expected_retirement_marginal_rate,
    )
