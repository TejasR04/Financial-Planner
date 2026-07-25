from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.domain.entities import Account, Institution, User
from app.domain.enums import AccountStatus, AccountType
from app.persistence.repositories.account_repository import AccountRepository
from app.persistence.repositories.holding_repository import HoldingRepository
from app.persistence.repositories.institution_repository import InstitutionRepository
from app.persistence.repositories.user_repository import UserRepository
from app.schemas.account import (
    AccountCreateRequest,
    AccountListResponse,
    AccountResponse,
    AccountUpdateRequest,
    InstitutionResponse,
)
from app.schemas.plaid import PlaidRefreshInstitutionResponse
from app.providers.plaid_provider import PlaidProvider
from app.core.config import get_settings
from app.schemas.financial_health import (
    AllocationAnalysisResponse,
    AllocationBreakdownResponse,
    RebalanceSuggestionResponse,
)
from app.services.portfolio_allocation_service import PortfolioAllocationService

router = APIRouter(prefix="/accounts", tags=["accounts"])
allocation_service = PortfolioAllocationService()


def _to_response(account: Account, institutions: dict[UUID, Institution]) -> AccountResponse:
    response = AccountResponse.model_validate(account, from_attributes=True)
    if account.institution_id is not None:
        institution = institutions.get(account.institution_id)
        if institution is not None:
            response.institution = institution.name
            response.institution_id = institution.id
            response.institution_status = institution.status.value
            response.institution_last_synced_at = institution.last_synced_at
    return response


def _provider(db: AsyncSession) -> PlaidProvider:
    settings = get_settings()
    return PlaidProvider(db, settings.plaid_client_id, settings.plaid_secret, settings.plaid_env)


def _refresh_response(result) -> PlaidRefreshInstitutionResponse:
    return PlaidRefreshInstitutionResponse(
        institution_id=result.institution_id,
        institution_name=result.institution_name,
        status=result.status,
        accounts_synced=result.accounts_synced,
        transactions_created=result.transactions_created,
        transactions_updated=result.transactions_updated,
        transactions_removed=result.transactions_removed,
        holdings_synced=result.holdings_synced,
        error=result.error,
    )


@router.get("", response_model=AccountListResponse)
async def list_accounts(
    type: AccountType | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AccountListResponse:
    accounts = await AccountRepository(db).list_for_user(current_user.id, type)
    institutions = {institution.id: institution for institution in await InstitutionRepository(db).list_for_user(current_user.id)}
    assets = sum((a.balance for a in accounts if not a.is_liability), Decimal("0"))
    liabilities = sum((abs(a.balance) for a in accounts if a.is_liability), Decimal("0"))
    return AccountListResponse(
        data=[_to_response(a, institutions) for a in accounts],
        total_assets=assets,
        total_liabilities=liabilities,
        net_worth=sum((a.balance for a in accounts), Decimal("0")),
    )


@router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    body: AccountCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AccountResponse:
    account = Account(
        id=uuid4(),
        user_id=current_user.id,
        name=body.name,
        type=body.type,
        balance=body.balance,
        currency=body.currency,
        mask=body.mask,
        apy=body.apy,
        status=AccountStatus.MANUAL,
    )
    created = await AccountRepository(db).create(current_user.id, account)
    await db.commit()
    return _to_response(created, {})


@router.get("/institutions", response_model=list[InstitutionResponse])
async def list_institutions(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[InstitutionResponse]:
    institutions = await InstitutionRepository(db).list_for_user(current_user.id)
    counts = await AccountRepository(db).count_active_for_institutions(current_user.id)
    return [
        InstitutionResponse(
            id=institution.id,
            name=institution.name,
            provider=institution.provider.value,
            status=institution.status.value,
            last_synced_at=institution.last_synced_at,
            account_count=counts.get(institution.id, 0),
        )
        for institution in institutions
    ]


@router.delete("/institutions/{institution_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_institution(
    institution_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    institution = await InstitutionRepository(db).get_for_user(current_user.id, institution_id)
    if institution.provider.value != "plaid":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Only linked Plaid institutions can be unlinked.")
    accounts = AccountRepository(db)
    await accounts.archive_and_detach_institution(current_user.id, institution_id)
    await InstitutionRepository(db).delete_for_user(current_user.id, institution_id)
    await db.commit()


@router.get("/allocation", response_model=AllocationAnalysisResponse)
async def get_allocation(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> AllocationAnalysisResponse:
    holdings = await HoldingRepository(db).list_for_user(current_user.id)
    profile = await UserRepository(db).get_planning_profile(current_user.id)
    result = allocation_service.analyze(holdings, profile.target_equity_allocation)
    return AllocationAnalysisResponse(
        total_market_value=result.total_market_value,
        breakdown=[
            AllocationBreakdownResponse(asset_class=b.asset_class.value, market_value=b.market_value, weight=b.weight)
            for b in result.breakdown
        ],
        actual_equity_allocation=result.actual_equity_allocation,
        target_equity_allocation=result.target_equity_allocation,
        drift=result.drift,
        is_within_tolerance=result.is_within_tolerance,
        rebalance_suggestions=[
            RebalanceSuggestionResponse(asset_class=s.asset_class.value, action=s.action, amount=s.amount)
            for s in result.rebalance_suggestions
        ],
    )


@router.get("/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> AccountResponse:
    account = await AccountRepository(db).get_for_user(current_user.id, account_id)
    institutions = {institution.id: institution for institution in await InstitutionRepository(db).list_for_user(current_user.id)}
    return _to_response(account, institutions)


@router.patch("/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: UUID,
    body: AccountUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AccountResponse:
    updated = await AccountRepository(db).update_manual_for_user(
        current_user.id, account_id, **body.model_dump(exclude_unset=True)
    )
    await db.commit()
    return _to_response(updated, {})


@router.post("/{account_id}/sync", response_model=PlaidRefreshInstitutionResponse)
async def sync_account_institution(
    account_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlaidRefreshInstitutionResponse:
    account = await AccountRepository(db).get_for_user(current_user.id, account_id)
    if account.institution_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Manual accounts cannot be synced.")
    result = await _provider(db).refresh_institution(current_user.id, account.institution_id)
    await db.commit()
    return _refresh_response(result)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> None:
    account = await AccountRepository(db).get_for_user(current_user.id, account_id)
    if account.institution_id is not None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unlink the institution instead of deleting a linked account.")
    await AccountRepository(db).archive_for_user(current_user.id, account_id)
    await db.commit()
