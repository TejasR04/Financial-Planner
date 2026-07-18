from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.domain.entities import IncomeSource, Liability, User
from app.domain.enums import DebtPayoffStrategy
from app.persistence.repositories.account_repository import AccountRepository
from app.schemas.simulation import (
    CashFlowMonthPointResponse,
    CashFlowSimulationRequest,
    CashFlowSimulationResponse,
    DebtOptimizationRequest,
    DebtOptimizationResponse,
    MonteCarloSimulationRequest,
    MonteCarloSimulationResponse,
    NetWorthSimulationRequest,
    NetWorthSimulationResponse,
    NetWorthYearPointResponse,
    RetirementSimulationRequest,
    RetirementSimulationResponse,
)
from app.services.cash_flow_projection_service import CashFlowProjectionService
from app.services.debt_optimization_service import DebtOptimizationService
from app.services.net_worth_projection_service import NetWorthProjectionService
from app.services.retirement_projection_service import RetirementProjectionService
from app.simulation.assumptions import PlanningAssumptions
from app.simulation.monte_carlo import run_monte_carlo

router = APIRouter(prefix="/simulations", tags=["simulations"])

retirement_service = RetirementProjectionService()
net_worth_service = NetWorthProjectionService()
cash_flow_service = CashFlowProjectionService()
debt_service = DebtOptimizationService()


@router.post("/retirement", response_model=RetirementSimulationResponse)
async def simulate_retirement(
    body: RetirementSimulationRequest, current_user: User = Depends(get_current_user)
) -> RetirementSimulationResponse:
    assumptions = PlanningAssumptions(
        current_age=body.current_age,
        retirement_age=body.retirement_age,
        life_expectancy_age=body.life_expectancy_age,
        expected_return=body.expected_return,
        inflation_rate=body.inflation_rate,
        withdrawal_rate=body.withdrawal_rate,
    )
    result = retirement_service.project(
        current_retirement_balance=body.current_retirement_balance,
        annual_contribution=body.annual_contribution,
        assumptions=assumptions,
        annual_spending_target=body.annual_spending_target,
    )
    return RetirementSimulationResponse(
        projected_balance_at_retirement=result.projected_balance_at_retirement,
        annual_sustainable_withdrawal=result.annual_sustainable_withdrawal,
        monthly_sustainable_withdrawal=result.monthly_sustainable_withdrawal,
        is_feasible=result.is_feasible,
        shortfall_or_surplus=result.shortfall_or_surplus,
        years_to_retirement=assumptions.years_to_retirement,
    )


@router.post("/net-worth", response_model=NetWorthSimulationResponse)
async def simulate_net_worth(
    body: NetWorthSimulationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NetWorthSimulationResponse:
    accounts = await AccountRepository(db).list_for_user(current_user.id)

    assumptions = PlanningAssumptions(
        current_age=body.current_age,
        retirement_age=body.retirement_age,
        expected_return=body.expected_return,
    )
    result = net_worth_service.project(
        accounts=accounts,
        assumptions=assumptions,
        years=body.years,
        annual_net_contribution=body.annual_net_contribution,
    )
    return NetWorthSimulationResponse(
        net_worth_today=result.net_worth_today,
        projected_net_worth_at_horizon=result.projected_net_worth_at_horizon,
        series=[
            NetWorthYearPointResponse(
                year_index=p.year_index, age=p.age, assets=p.assets, liabilities=p.liabilities, net=p.net
            )
            for p in result.series
        ],
    )


@router.post("/cash-flow", response_model=CashFlowSimulationResponse)
async def simulate_cash_flow(
    body: CashFlowSimulationRequest, current_user: User = Depends(get_current_user)
) -> CashFlowSimulationResponse:
    from uuid import uuid4

    income_sources = [
        IncomeSource(
            id=uuid4(),
            user_id=current_user.id,
            name="Primary income",
            annual_amount=body.monthly_gross_income * 12,
            growth_rate=body.income_growth_rate,
        )
    ]
    result = cash_flow_service.project(
        income_sources=income_sources,
        monthly_expenses=body.monthly_expenses,
        months=body.months,
        inflation_rate=body.inflation_rate,
    )
    return CashFlowSimulationResponse(
        series=[
            CashFlowMonthPointResponse(
                month_index=p.month_index, income=p.income, expenses=p.expenses, net=p.net
            )
            for p in result.series
        ],
        average_monthly_surplus=result.average_monthly_surplus,
        projected_savings_rate=result.projected_savings_rate,
    )


@router.post("/monte-carlo", response_model=MonteCarloSimulationResponse)
async def simulate_monte_carlo(
    body: MonteCarloSimulationRequest, current_user: User = Depends(get_current_user)
) -> MonteCarloSimulationResponse:
    result = run_monte_carlo(
        starting_balance=body.starting_balance,
        annual_contribution=body.annual_contribution,
        expected_return=body.expected_return,
        return_volatility=body.return_volatility,
        years=body.years,
        starting_age=body.current_age,
        target_balance=body.target_balance,
        trials=body.trials,
        seed=body.seed,
    )
    return MonteCarloSimulationResponse(
        trials=result.trials,
        success_rate=result.success_rate,
        median_ending_balance=result.median_ending_balance,
        p10_ending_balance=result.p10_ending_balance,
        p90_ending_balance=result.p90_ending_balance,
        seed=result.seed,
    )


@router.post("/debt-optimization", response_model=DebtOptimizationResponse)
async def simulate_debt_optimization(
    body: DebtOptimizationRequest, current_user: User = Depends(get_current_user)
) -> DebtOptimizationResponse:
    from datetime import date
    from uuid import uuid4

    liabilities = [
        Liability(
            id=uuid4(),
            account_id=uuid4(),
            principal=item.principal,
            interest_rate=item.interest_rate,
            term_months=item.term_months,
            minimum_payment=item.minimum_payment,
            origination_date=date.today(),
        )
        for item in body.liabilities
    ]
    strategy = DebtPayoffStrategy(body.strategy)
    plan = debt_service.optimize(
        liabilities=liabilities, extra_monthly_payment=body.extra_monthly_payment, strategy=strategy
    )
    name_by_index = {str(i): item.name for i, item in enumerate(body.liabilities)}
    return DebtOptimizationResponse(
        strategy=plan.strategy.value,
        months_to_debt_free=plan.months_to_debt_free,
        total_interest_paid=plan.total_interest_paid,
        payoff_order=[name_by_index[i] for i in plan.payoff_order],
    )
