from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.domain.entities import Holding, IncomeSource, User
from app.domain.enums import AccountType
from app.persistence.repositories.account_repository import AccountRepository
from app.persistence.repositories.holding_repository import HoldingRepository
from app.persistence.repositories.income_source_repository import IncomeSourceRepository
from app.persistence.repositories.liability_repository import LiabilityRepository
from app.schemas.financial_inputs import *

router = APIRouter(tags=["financial-inputs"])


@router.get("/income-sources", response_model=list[IncomeSourceResponse])
async def list_income_sources(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await IncomeSourceRepository(db).list_for_user(current_user.id, active_only=False)


@router.post("/income-sources", response_model=IncomeSourceResponse, status_code=201)
async def create_income_source(body: IncomeSourceCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row = await IncomeSourceRepository(db).create(current_user.id, IncomeSource(id=uuid4(), user_id=current_user.id, **body.model_dump()))
    await db.commit()
    return row


@router.patch("/income-sources/{source_id}", response_model=IncomeSourceResponse)
async def update_income_source(source_id: UUID, body: IncomeSourceUpdate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row = await IncomeSourceRepository(db).update_for_user(current_user.id, source_id, **body.model_dump(exclude_unset=True))
    await db.commit()
    return row


@router.delete("/income-sources/{source_id}", status_code=204)
async def delete_income_source(source_id: UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await IncomeSourceRepository(db).delete_for_user(current_user.id, source_id)
    await db.commit()


async def _eligible_account(user_id: UUID, account_id: UUID, db: AsyncSession, types: set[AccountType], manual_only: bool = False):
    account = await AccountRepository(db).get_for_user(user_id, account_id)
    if account.type not in types:
        raise HTTPException(422, "This input is not valid for that account type.")
    if manual_only and account.institution_id is not None:
        raise HTTPException(422, "Linked holdings are managed by the institution.")
    return account


@router.get("/accounts/{account_id}/liability", response_model=LiabilityResponse | None)
async def get_liability(account_id: UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _eligible_account(current_user.id, account_id, db, {AccountType.CREDIT, AccountType.LOAN})
    return await LiabilityRepository(db).get_for_user_account(current_user.id, account_id)


@router.put("/accounts/{account_id}/liability", response_model=LiabilityResponse)
async def put_liability(account_id: UUID, body: LiabilityDetails, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _eligible_account(current_user.id, account_id, db, {AccountType.CREDIT, AccountType.LOAN})
    row = await LiabilityRepository(db).upsert_for_user_account(current_user.id, account_id, **body.model_dump())
    await db.commit()
    return row


@router.delete("/accounts/{account_id}/liability", status_code=204)
async def delete_liability(account_id: UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _eligible_account(current_user.id, account_id, db, {AccountType.CREDIT, AccountType.LOAN})
    await LiabilityRepository(db).delete_for_user_account(current_user.id, account_id)
    await db.commit()


@router.get("/accounts/{account_id}/holdings", response_model=list[HoldingResponse])
async def list_holdings(account_id: UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _eligible_account(current_user.id, account_id, db, {AccountType.INVESTMENT, AccountType.RETIREMENT})
    return await HoldingRepository(db).list_for_account(account_id)


@router.post("/accounts/{account_id}/holdings", response_model=HoldingResponse, status_code=201)
async def create_holding(account_id: UUID, body: HoldingInput, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _eligible_account(current_user.id, account_id, db, {AccountType.INVESTMENT, AccountType.RETIREMENT}, manual_only=True)
    row = await HoldingRepository(db).create(Holding(id=uuid4(), account_id=account_id, **body.model_dump()))
    await db.commit()
    return row


@router.patch("/holdings/{holding_id}", response_model=HoldingResponse)
async def update_holding(holding_id: UUID, body: HoldingUpdate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row = await HoldingRepository(db).update_for_user(current_user.id, holding_id, **body.model_dump(exclude_unset=True))
    await db.commit()
    return row


@router.delete("/holdings/{holding_id}", status_code=204)
async def delete_holding(holding_id: UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await HoldingRepository(db).delete_for_user(current_user.id, holding_id)
    await db.commit()
