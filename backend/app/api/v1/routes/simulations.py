from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.domain.entities import User
from app.persistence.repositories.account_repository import AccountRepository
from app.schemas.simulation import (
    NetWorthSimulationRequest,
    NetWorthSimulationResponse,
    NetWorthYearPointResponse,
    RetirementSimulationRequest,
    RetirementSimulationResponse,
)
from app.services.net_worth_projection_service import NetWorthProjectionService
from app.services.retirement_projection_service import RetirementProjectionService
from app.simulation.assumptions import PlanningAssumptions

router = APIRouter(prefix="/simulations", tags=["simulations"])

retirement_service = RetirementProjectionService()
net_worth_service = NetWorthProjectionService()


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
