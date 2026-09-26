from datetime import date
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.domain.entities import Transaction, User
from app.domain.enums import TransactionType
from app.persistence.repositories.transaction_repository import TransactionRepository, import_fingerprints
from app.persistence.repositories.account_repository import AccountRepository
from app.persistence.repositories.budget_repository import BudgetRepository
from app.providers.csv_import_provider import CSVImportProvider
from app.schemas.transaction import (
    CSVImportRequest,
    CSVImportPreviewResponse,
    CSVImportPreviewRow,
    CSVImportResponse,
    TransactionCreateRequest,
    TransactionClassificationRequest,
    TransactionListResponse,
    TransactionResponse,
    TransactionUpdateRequest,
)
from app.schemas.budget import TransactionBudgetAssignmentRequest
from app.services.loan_balance_automation_service import LoanBalanceAutomationService

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _normalized_import_rows(body: CSVImportRequest):
    provider = CSVImportProvider(account_id=body.account_id, csv_text=body.csv_text)
    parsed = provider.parse_rows(since=body.since or date(1970, 1, 1))
    overrides = {override.row_number: override for override in body.overrides}
    known_rows = {row.row_number for row in parsed}
    unknown_rows = set(overrides) - known_rows
    if unknown_rows:
        raise ValueError(f"Overrides reference rows that are not in the file: {sorted(unknown_rows)}")
    for row in parsed:
        override = overrides.get(row.row_number)
        transaction = row.transaction
        if override is not None:
            for field in ("posted_at", "merchant", "category", "amount", "type"):
                value = getattr(override, field)
                if value is not None:
                    setattr(transaction, field, value)
            # An edited signed amount is authoritative: positive expenses are
            # refunds, while income/contribution classifications stay inflows.
            if override.type is not None:
                row.warnings = [warning for warning in row.warnings if not warning.startswith("Type was inferred")]
                if override.type.value in {"income", "contribution"}:
                    transaction.amount = abs(transaction.amount)

    # Use occurrence numbers within each normalized transaction identity,
    # rather than physical CSV line numbers. Compute them before filtering
    # excluded rows so an excluded occurrence keeps its place when retried.
    for row, identity in zip(parsed, import_fingerprints([item.transaction for item in parsed]), strict=True):
        row.identity_number = int(identity.rsplit(":", 1)[1])

    selected = []
    for row in parsed:
        override = overrides.get(row.row_number)
        if override is not None and not override.include:
            continue
        transaction = row.transaction
        if not transaction.merchant.strip():
            raise ValueError(f"Row {row.row_number}: Merchant is required")
        if transaction.amount == 0:
            raise ValueError(f"Row {row.row_number}: Amount cannot be zero")
        selected.append(row)
    return selected


@router.get("/merchants", response_model=list[str])
async def search_merchants(
    search: str = "",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select, func
    from app.persistence.models import AccountModel, TransactionModel

    query = (
        select(TransactionModel.merchant).distinct()
        .join(AccountModel, AccountModel.id == TransactionModel.account_id)
        .where(
            AccountModel.user_id == current_user.id,
            AccountModel.archived_at.is_(None),
            TransactionModel.deleted_at.is_(None),
            TransactionModel.amount < 0,
            func.lower(TransactionModel.merchant).contains(search.strip().lower(), autoescape=True),
        )
        .order_by(TransactionModel.merchant).limit(30)
    )
    return list((await db.scalars(query)).all())


@router.get("", response_model=TransactionListResponse)
async def list_transactions(
    account_id: UUID | None = None,
    category: str | None = None,
    budget_category_id: UUID | None = None,
    direction: str | None = Query(default=None, pattern="^(inflow|outflow)$"),
    search: str | None = None,
    merchant: str | None = None,
    since: date | None = None,
    until: date | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    include_archived: bool = False,
    cash_flow_only: bool = False,
    type: TransactionType | None = None,
    include_totals: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransactionListResponse:
    await BudgetRepository(db).apply_category_defaults_for_user(current_user.id)
    await db.commit()
    filters: dict[str, Any] = dict(account_id=account_id, category=category,
        budget_category_id=budget_category_id, direction=direction, search=search, merchant=merchant, since=since, until=until,
        include_archived=include_archived, cash_flow_only=cash_flow_only,
        transaction_type=type.value if type else None,
    )
    repository = TransactionRepository(db)
    transactions, total = await repository.list_for_user(current_user.id, limit=limit, offset=offset, **filters)
    totals = await repository.totals_for_user(current_user.id, **filters) if include_totals else None
    return TransactionListResponse(
        data=[TransactionResponse.model_validate(t, from_attributes=True) for t in transactions],
        total=total,
        limit=limit,
        offset=offset,
        totals=totals,
    )


@router.post("", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    body: TransactionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransactionResponse:
    await AccountRepository(db).get_for_user(current_user.id, body.account_id)
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
    await LoanBalanceAutomationService(db).apply(current_user.id)
    await db.commit()
    return TransactionResponse.model_validate(created, from_attributes=True)


@router.patch("/{transaction_id}", response_model=TransactionResponse)
async def update_transaction(
    transaction_id: UUID,
    body: TransactionUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransactionResponse:
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=422, detail="Provide at least one field to update.")
    updated = await TransactionRepository(db).update_for_user(
        current_user.id, transaction_id, **fields
    )
    await LoanBalanceAutomationService(db).apply(current_user.id)
    await db.commit()
    return TransactionResponse.model_validate(updated, from_attributes=True)


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    transaction_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await TransactionRepository(db).delete_for_user(current_user.id, transaction_id)
    await LoanBalanceAutomationService(db).apply(current_user.id)
    await db.commit()


@router.post("/{transaction_id}/review", status_code=status.HTTP_204_NO_CONTENT)
async def review_transaction(
    transaction_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await TransactionRepository(db).mark_reviewed(current_user.id, transaction_id)
    await db.commit()


@router.patch("/{transaction_id}/classification", response_model=TransactionResponse)
async def classify_transaction(
    transaction_id: UUID,
    body: TransactionClassificationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransactionResponse:
    updated = await TransactionRepository(db).set_user_classification(
        current_user.id, transaction_id, body.type
    )
    await db.commit()
    return TransactionResponse.model_validate(updated, from_attributes=True)


@router.patch("/{transaction_id}/budget-category", response_model=TransactionResponse)
async def update_transaction_budget_category(
    transaction_id: UUID,
    body: TransactionBudgetAssignmentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransactionResponse:
    category_name = None
    if body.budget_category_id is not None:
        category = await BudgetRepository(db).get_category_for_user(
            current_user.id, body.budget_category_id
        )
        category_name = category.name
    updated = await TransactionRepository(db).update_budget_category(
        current_user.id, transaction_id, body.budget_category_id, body.ignored_from_budget
    )
    updated.budget_category_name = category_name
    await db.commit()
    return TransactionResponse.model_validate(updated, from_attributes=True)


@router.post("/import/csv/preview", response_model=CSVImportPreviewResponse)
async def preview_csv_import(
    body: CSVImportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CSVImportPreviewResponse:
    await AccountRepository(db).get_for_user(current_user.id, body.account_id)
    try:
        parsed = _normalized_import_rows(body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    duplicate_flags = await TransactionRepository(db).import_duplicate_flags(
        [row.transaction for row in parsed], [int(row.identity_number) for row in parsed]
    )
    rows = [
        CSVImportPreviewRow(
            row_number=row.row_number,
            posted_at=row.transaction.posted_at,
            merchant=row.transaction.merchant,
            category=row.transaction.category,
            amount=row.transaction.amount,
            type=row.transaction.type,
            likely_duplicate=duplicate,
            warnings=row.warnings,
        )
        for row, duplicate in zip(parsed, duplicate_flags, strict=True)
    ]
    return CSVImportPreviewResponse(
        rows=rows,
        importable_count=sum(not row.likely_duplicate for row in rows),
        duplicate_count=sum(row.likely_duplicate for row in rows),
    )


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
    await AccountRepository(db).get_for_user(current_user.id, body.account_id)
    try:
        parsed = _normalized_import_rows(body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    overrides = {override.row_number: override for override in body.overrides}
    created, skipped = await TransactionRepository(db).bulk_create_deduplicated(
        [row.transaction for row in parsed],
        [overrides[row.row_number].force_import if row.row_number in overrides else False for row in parsed],
        [int(row.identity_number) for row in parsed],
    )
    await LoanBalanceAutomationService(db).apply(current_user.id)
    await db.commit()
    return CSVImportResponse(
        imported_count=len(created),
        skipped_duplicate_count=skipped,
        data=[TransactionResponse.model_validate(t, from_attributes=True) for t in created],
    )
