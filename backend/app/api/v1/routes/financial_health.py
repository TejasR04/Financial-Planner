from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.domain.entities import User
from app.persistence.repositories.financial_health_repository import FinancialHealthScoreRepository
from app.persistence.repositories.holding_repository import HoldingRepository
from app.persistence.activity_history import load_activity_history
from app.persistence.snapshot_builder import build_financial_snapshot
from app.schemas.financial_health import FinancialHealthRecalculateRequest, FinancialHealthScoreResponse
from app.services.financial_health_service import FinancialHealthService
from app.services.portfolio_allocation_service import PortfolioAllocationService

router = APIRouter(prefix="/financial-health", tags=["financial-health"])

health_service = FinancialHealthService()
allocation_service = PortfolioAllocationService()

@router.get("", response_model=FinancialHealthScoreResponse)
async def get_financial_health(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> FinancialHealthScoreResponse:
    row = await FinancialHealthScoreRepository(db).get_latest(current_user.id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No financial-health score has been calculated yet.",
        )
    return FinancialHealthScoreResponse(
        overall=row.overall, liquidity=row.liquidity, diversification=row.diversification,
        debt_ratio=row.debt_ratio, savings_discipline=row.savings_discipline, calculated_at=row.calculated_at,
    )


@router.post("/recalculate", response_model=FinancialHealthScoreResponse)
async def recalculate_financial_health(
    body: FinancialHealthRecalculateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FinancialHealthScoreResponse:
    """Use the same completed-month averages as the spending and outlook views."""
    snapshot = await build_financial_snapshot(db, current_user.id)

    monthly_expenses = body.monthly_expenses
    actual_savings_rate = body.actual_savings_rate
    if monthly_expenses is None or actual_savings_rate is None:
        history = await load_activity_history(db, current_user.id)
        if not history.months:
            raise HTTPException(422, "A completed month of transaction history is needed to calculate financial health.")
        total_income, total_expenses = history.monthly_cash_flow
        if monthly_expenses is None:
            monthly_expenses = max(Decimal("0"), total_expenses)
        if actual_savings_rate is None:
            actual_savings_rate = (
                (total_income - total_expenses) / total_income if total_income > 0 else Decimal("0")
            )

    target_savings_rate = body.target_savings_rate if body.target_savings_rate is not None else snapshot.profile.target_savings_rate
    if target_savings_rate is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Set a target savings rate in Planning inputs before calculating financial health.",
        )

    holdings = await HoldingRepository(db).list_for_user(current_user.id)
    allocation = allocation_service.analyze(holdings, snapshot.profile.target_equity_allocation)

    score = health_service.score(
        snapshot,
        monthly_expenses=monthly_expenses,
        target_savings_rate=target_savings_rate,
        actual_savings_rate=actual_savings_rate,
        target_equity_allocation=snapshot.profile.target_equity_allocation,
        actual_equity_allocation=allocation.actual_equity_allocation,
    )

    row = await FinancialHealthScoreRepository(db).save(current_user.id, score)
    await db.commit()
    return FinancialHealthScoreResponse(
        overall=row.overall, liquidity=row.liquidity, diversification=row.diversification,
        debt_ratio=row.debt_ratio, savings_discipline=row.savings_discipline, calculated_at=row.calculated_at,
    )
