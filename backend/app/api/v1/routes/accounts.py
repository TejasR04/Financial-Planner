from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.domain.entities import Account, User
from app.domain.enums import AccountStatus, AccountType
from app.persistence.repositories.account_repository import AccountRepository
from app.schemas.account import AccountCreateRequest, AccountListResponse, AccountResponse

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=AccountListResponse)
async def list_accounts(
    type: AccountType | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AccountListResponse:
    accounts = await AccountRepository(db).list_for_user(current_user.id, type)
    assets = sum((a.balance for a in accounts if a.balance >= 0), Decimal("0"))
    liabilities = sum((-a.balance for a in accounts if a.balance < 0), Decimal("0"))
    return AccountListResponse(
        data=[AccountResponse.model_validate(a, from_attributes=True) for a in accounts],
        total_assets=assets,
        total_liabilities=liabilities,
        net_worth=assets - liabilities,
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
    return AccountResponse.model_validate(created, from_attributes=True)


@router.get("/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> AccountResponse:
    account = await AccountRepository(db).get_by_id(account_id)
    return AccountResponse.model_validate(account, from_attributes=True)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> None:
    await AccountRepository(db).delete(account_id)
    await db.commit()
