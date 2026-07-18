from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.domain.entities import User
from app.domain.enums import TransactionType
from app.persistence.repositories.financial_health_repository import FinancialHealthScoreRepository
from app.persistence.repositories.holding_repository import HoldingRepository
from app.persistence.repositories.transaction_repository import TransactionRepository
from app.persistence.snapshot_builder import build_financial_snapshot
from app.schemas.financial_health import FinancialHealthRecalculateRequest, FinancialHealthScoreResponse
from app.services.financial_health_service import FinancialHealthService
from app.services.portfolio_allocation_service import PortfolioAllocationService

router = APIRouter(prefix="/financial-health", tags=["financial-health"])

health_service = FinancialHealthService()
allocation_service = PortfolioAllocationService()

DEFAULT_TARGET_SAVINGS_RATE = Decimal("0.20")
TRAILING_MONTHS_FOR_DEFAULTS = 3


@router.get("", response_model=FinancialHealthScoreResponse)
async def get_financial_health(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> FinancialHealthScoreResponse:
    row = await FinancialHealthScoreRepository(db).get_latest(current_user.id)
    if row is None:
        # No score computed yet — recalculate once with defaults so the
        # first visit to the Insights page isn't empty.
        return await recalculate_financial_health(
            FinancialHealthRecalculateRequest(), current_user, db
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
    """Assembles a FinancialSnapshot, fills in any inputs the caller didn't
    supply from real transaction/holding data where possible, and calls
    FinancialHealthService (the one place this scoring math lives).

    Defaults when not provided in the request body:
    - monthly_expenses: average monthly expense total over the trailing
      3 months of transactions (0 if there's no transaction history yet,
      which FinancialHealthService documents as a neutral liquidity score).
    - target_savings_rate: 20%, a standard planning guideline — there's no
      per-user field for this yet (see ARCHITECTURE.md for the
      PlanningProfile schema); flagged as a fields gap worth closing.
    - actual_savings_rate: (trailing income - trailing expenses) / trailing
      income over the same 3-month window, 0 if no income transactions.
    - actual_equity_allocation: computed from real Holdings via
      PortfolioAllocationService; falls back to the target (neutral score)
      if the user has no holdings on file yet.
    """
    snapshot = await build_financial_snapshot(db, current_user.id)

    monthly_expenses = body.monthly_expenses
    actual_savings_rate = body.actual_savings_rate
    if monthly_expenses is None or actual_savings_rate is None:
        from datetime import date, timedelta

        since = date.today() - timedelta(days=30 * TRAILING_MONTHS_FOR_DEFAULTS)
        transactions = await TransactionRepository(db).list_since_for_income_expense(current_user.id, since)
        total_expenses = sum(
            (-t.amount for t in transactions if t.type == TransactionType.EXPENSE), Decimal("0")
        )
        total_income = sum(
            (t.amount for t in transactions if t.type == TransactionType.INCOME), Decimal("0")
        )
        if monthly_expenses is None:
            monthly_expenses = (total_expenses / TRAILING_MONTHS_FOR_DEFAULTS) if total_expenses > 0 else Decimal("0")
        if actual_savings_rate is None:
            actual_savings_rate = (
                (total_income - total_expenses) / total_income if total_income > 0 else Decimal("0")
            )

    target_savings_rate = body.target_savings_rate or DEFAULT_TARGET_SAVINGS_RATE

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
