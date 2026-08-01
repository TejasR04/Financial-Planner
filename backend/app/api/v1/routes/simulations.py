from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.domain.entities import User
from app.domain.enums import DebtPayoffStrategy, TransactionType
from app.persistence.repositories.account_repository import AccountRepository
from app.persistence.repositories.income_source_repository import IncomeSourceRepository
from app.persistence.repositories.liability_repository import LiabilityRepository
from app.persistence.repositories.transaction_repository import TransactionRepository
from app.persistence.repositories.user_repository import UserRepository
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
    body: CashFlowSimulationRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> CashFlowSimulationResponse:
    from datetime import date, timedelta
    from decimal import Decimal
    income_sources = await IncomeSourceRepository(db).list_for_user(current_user.id)
    if not income_sources:
        from fastapi import HTTPException
        raise HTTPException(422, "Add an active planning income source before generating an outlook.")
    trailing_months = 3
    transactions = await TransactionRepository(db).list_since_for_income_expense(current_user.id, date.today() - timedelta(days=30 * trailing_months))
    expenses = sum((-row.amount for row in transactions if row.type == TransactionType.EXPENSE), Decimal("0"))
    if expenses <= 0:
        from fastapi import HTTPException
        raise HTTPException(422, "At least one recent expense is required to generate an outlook.")
    monthly_expenses = expenses / trailing_months
    profile = await UserRepository(db).get_planning_profile(current_user.id)
    result = cash_flow_service.project(
        income_sources=income_sources,
        monthly_expenses=monthly_expenses,
        months=body.months,
        inflation_rate=profile.inflation_rate,
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
        income_source="Saved planning income sources (pre-tax unless entered as take-home)",
        expense_source="Trailing 3-month tracked expense average",
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
        success_metric=result.success_metric,
        model_version=result.model_version,
        percentile_method=result.percentile_method,
        estimate_disclosure="Estimate based on randomized returns, not a guarantee or precise probability.",
        exclusions=["taxes", "investment fees", "advisory fees"],
    )


@router.post("/debt-optimization", response_model=DebtOptimizationResponse)
async def simulate_debt_optimization(
    body: DebtOptimizationRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> DebtOptimizationResponse:
    liabilities = []
    names = {}
    for account_id in body.account_ids:
        account = await AccountRepository(db).get_for_user(current_user.id, account_id)
        details = await LiabilityRepository(db).get_for_user_account(current_user.id, account_id)
        if not account.is_liability or details is None:
            from fastapi import HTTPException
            raise HTTPException(422, f"{account.name} needs debt terms before payoff planning.")
        details.principal = abs(account.balance)
        liabilities.append(details)
        names[str(len(liabilities) - 1)] = account.name
    strategy = DebtPayoffStrategy(body.strategy)
    plan = debt_service.optimize(
        liabilities=liabilities, extra_monthly_payment=body.extra_monthly_payment, strategy=strategy
    )
    paid_off = len(plan.payoff_order) == len(liabilities)
    return DebtOptimizationResponse(
        strategy=plan.strategy.value,
        months_to_debt_free=plan.months_to_debt_free,
        total_interest_paid=plan.total_interest_paid,
        payoff_order=[names[i] for i in plan.payoff_order],
        paid_off=paid_off,
        warning=None if paid_off else "The balances were not paid off within the 600-month calculation limit.",
    )
