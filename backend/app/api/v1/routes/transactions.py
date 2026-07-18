from datetime import date
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.exceptions import NotFoundError, ValidationError
from app.domain.entities import Transaction, User
from app.persistence.repositories.transaction_repository import TransactionRepository
from app.providers.csv_import_provider import CSVImportProvider
from app.schemas.transaction import (
    CSVImportRequest,
    CSVImportResponse,
    TransactionCreateRequest,
    TransactionListResponse,
    TransactionResponse,
    TransactionUpdateRequest,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=TransactionListResponse)
async def list_transactions(
    account_id: UUID | None = None,
    category: str | None = None,
    since: date | None = None,
    until: date | None = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransactionListResponse:
    transactions, total = await TransactionRepository(db).list_for_user(
        current_user.id, account_id=account_id, category=category, since=since, until=until,
        limit=limit, offset=offset,
    )
    return TransactionListResponse(
        data=[TransactionResponse.model_validate(t, from_attributes=True) for t in transactions],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    body: TransactionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransactionResponse:
    transaction = Transaction(
        id=uuid4(),
        account_id=body.account_id,
        posted_at=body.posted_at,
        merchant=body.merchant,
        category=body.category,
        amount=body.amount,
        type=body.type,
        status=body.status,
    )
    created = await TransactionRepository(db).create(body.account_id, transaction)
    await db.commit()
    return TransactionResponse.model_validate(created, from_attributes=True)


@router.patch("/{transaction_id}", response_model=TransactionResponse)
async def update_transaction_category(
    transaction_id: UUID,
    body: TransactionUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransactionResponse:
    updated = await TransactionRepository(db).update_category(transaction_id, body.category)
    await db.commit()
    return TransactionResponse.model_validate(updated, from_attributes=True)


@router.post("/import/csv", response_model=CSVImportResponse, status_code=status.HTTP_201_CREATED)
async def import_csv(
    body: CSVImportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CSVImportResponse:
    """Normalizes an uploaded CSV via CSVImportProvider, then persists the
    result through the same TransactionRepository every other write path
    uses — the provider never touches the DB directly.
    """
    provider = CSVImportProvider(account_id=body.account_id, csv_text=body.csv_text)
    try:
        normalized = await provider.get_transactions(current_user.id, since=body.since or date(1970, 1, 1))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    created = await TransactionRepository(db).bulk_create(normalized)
    await db.commit()
    return CSVImportResponse(
        imported_count=len(created),
        data=[TransactionResponse.model_validate(t, from_attributes=True) for t in created],
    )
