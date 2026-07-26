from collections import defaultdict
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.domain.entities import User
from app.domain.enums import AccountType
from app.persistence.repositories.account_repository import AccountRepository
from app.persistence.repositories.holding_repository import HoldingRepository
from app.persistence.repositories.institution_repository import InstitutionRepository
from app.persistence.repositories.investment_value_snapshot_repository import InvestmentValueSnapshotRepository
from app.schemas.investment import (
    InvestmentAccountResponse,
    InvestmentAllocationResponse,
    InvestmentDashboardResponse,
    InvestmentHoldingResponse,
    InvestmentValuePointResponse,
)

router = APIRouter(prefix="/investments", tags=["investments"])
ZERO = Decimal("0")


@router.get("/dashboard", response_model=InvestmentDashboardResponse)
async def get_investment_dashboard(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> InvestmentDashboardResponse:
    all_accounts = await AccountRepository(db).list_for_user(current_user.id)
    accounts = [account for account in all_accounts if account.type in {AccountType.INVESTMENT, AccountType.RETIREMENT}]
    account_ids = {account.id for account in accounts}
    institutions = {item.id: item for item in await InstitutionRepository(db).list_for_user(current_user.id)}
    holdings = [holding for holding in await HoldingRepository(db).list_for_user(current_user.id) if holding.account_id in account_ids]
    account_name_by_id = {account.id: account.name for account in accounts}

    total_value = sum((account.balance for account in accounts), ZERO)
    total_holdings_value = sum((holding.market_value for holding in holdings), ZERO)
    total_cost_basis = sum((holding.cost_basis for holding in holdings), ZERO)
    allocation_values: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for holding in holdings:
        allocation_values[holding.asset_class.value] += holding.market_value
    allocation = [
        InvestmentAllocationResponse(
            asset_class=asset_class,
            market_value=value,
            weight=value / total_holdings_value if total_holdings_value else ZERO,
        )
        for asset_class, value in sorted(allocation_values.items(), key=lambda item: item[1], reverse=True)
    ]

    history_rows = await InvestmentValueSnapshotRepository(db).daily_totals_for_user(current_user.id)
    history = [InvestmentValuePointResponse(date=as_of, value=value) for as_of, value in history_rows]
    # A newly linked account has no previous sync yet. Show the honest current
    # value rather than inventing a historical performance line.
    if not history and accounts:
        history = [InvestmentValuePointResponse(date=date.today(), value=total_value)]

    return InvestmentDashboardResponse(
        total_value=total_value,
        total_holdings_value=total_holdings_value,
        total_cost_basis=total_cost_basis,
        total_gain_loss=total_holdings_value - total_cost_basis,
        account_count=len(accounts),
        holding_count=len(holdings),
        accounts=[
            InvestmentAccountResponse(
                id=account.id,
                name=account.name,
                type=account.type.value,
                balance=account.balance,
                institution=institutions[account.institution_id].name if account.institution_id in institutions else None,
                updated_at=account.updated_at.date() if account.updated_at else None,
            )
            for account in accounts
        ],
        holdings=[
            InvestmentHoldingResponse(
                account_id=holding.account_id,
                account_name=account_name_by_id[holding.account_id],
                symbol=holding.symbol,
                quantity=holding.quantity,
                cost_basis=holding.cost_basis,
                market_value=holding.market_value,
                gain_loss=holding.market_value - holding.cost_basis,
                asset_class=holding.asset_class.value,
                as_of=holding.as_of,
            )
            for holding in sorted(holdings, key=lambda holding: holding.market_value, reverse=True)
        ],
        allocation=allocation,
        history=history,
    )
