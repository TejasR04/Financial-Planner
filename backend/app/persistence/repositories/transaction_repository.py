from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select

from app.core.exceptions import NotFoundError, ValidationError
from app.domain.entities import Transaction
from app.domain.enums import TransactionStatus, TransactionType
from app.persistence.models import AccountModel, TransactionModel
from app.persistence.repositories.base import BaseRepository


class TransactionRepository(BaseRepository[TransactionModel]):
    model = TransactionModel

    async def list_for_user(
        self,
        user_id: UUID,
        account_id: UUID | None = None,
        category: str | None = None,
        since: date | None = None,
        until: date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Transaction], int]:
        query = (
            select(TransactionModel)
            .join(AccountModel, AccountModel.id == TransactionModel.account_id)
            .where(AccountModel.user_id == user_id)
        )
        if account_id is not None:
            query = query.where(TransactionModel.account_id == account_id)
        if category is not None and category.strip():
            # Categories arrive from providers as identifiers such as
            # "rent_and_utilities". Match the typed characters anywhere in
            # that identifier, regardless of case, while treating underscores
            # like spaces for a natural search experience.
            normalized_category = func.replace(func.lower(TransactionModel.category), "_", " ")
            normalized_query = " ".join(category.lower().replace("_", " ").split())
            query = query.where(normalized_category.contains(normalized_query, autoescape=True))
        if since is not None:
            query = query.where(TransactionModel.posted_at >= since)
        if until is not None:
            query = query.where(TransactionModel.posted_at <= until)

        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        query = query.order_by(TransactionModel.posted_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(query)
        rows = result.scalars().all()
        return [_to_domain(row) for row in rows], total

    async def create(self, account_id: UUID, transaction: Transaction) -> Transaction:
        row = TransactionModel(
            id=transaction.id or uuid4(),
            account_id=account_id,
            posted_at=transaction.posted_at,
            merchant=transaction.merchant,
            category=transaction.category,
            amount=transaction.amount,
            type=transaction.type.value,
            status=transaction.status.value,
            external_transaction_id=transaction.external_transaction_id,
        )
        self.session.add(row)
        await self.session.flush()
        return _to_domain(row)

    async def bulk_create(self, transactions: list[Transaction]) -> list[Transaction]:
        rows = [
            TransactionModel(
                id=t.id or uuid4(),
                account_id=t.account_id,
                posted_at=t.posted_at,
                merchant=t.merchant,
                category=t.category,
                amount=t.amount,
                type=t.type.value,
                status=t.status.value,
                external_transaction_id=t.external_transaction_id,
            )
            for t in transactions
        ]
        self.session.add_all(rows)
        await self.session.flush()
        return [_to_domain(row) for row in rows]

    async def apply_plaid_updates(
        self,
        transactions: list[Transaction],
        removed_external_transaction_ids: list[str],
    ) -> tuple[int, int, int]:
        """Apply one complete `/transactions/sync` patch set.

        Plaid can send the same transaction in ``added`` and ``modified``
        across a sync lifecycle, so external transaction IDs are the stable
        identity rather than a new local row for each response.
        """
        transactions_by_external_id: dict[str, Transaction] = {}
        for transaction in transactions:
            external_id = transaction.external_transaction_id
            if external_id is None:
                raise ValueError("Plaid transactions require an external_transaction_id")
            transactions_by_external_id[external_id] = transaction

        existing_by_external_id: dict[str, TransactionModel] = {}
        if transactions_by_external_id:
            result = await self.session.execute(
                select(TransactionModel).where(
                    TransactionModel.external_transaction_id.in_(transactions_by_external_id)
                )
            )
            existing_by_external_id = {
                row.external_transaction_id: row
                for row in result.scalars().all()
                if row.external_transaction_id is not None
            }

        created = updated = 0
        for external_id, transaction in transactions_by_external_id.items():
            row = existing_by_external_id.get(external_id)
            if row is None:
                row = TransactionModel(
                    id=transaction.id or uuid4(),
                    account_id=transaction.account_id,
                    posted_at=transaction.posted_at,
                    merchant=transaction.merchant,
                    category=transaction.category,
                    amount=transaction.amount,
                    type=transaction.type.value,
                    status=transaction.status.value,
                    external_transaction_id=external_id,
                )
                self.session.add(row)
                created += 1
            else:
                row.account_id = transaction.account_id
                row.posted_at = transaction.posted_at
                row.merchant = transaction.merchant
                row.category = transaction.category
                row.amount = transaction.amount
                row.type = transaction.type.value
                row.status = transaction.status.value
                updated += 1

        removed = 0
        if removed_external_transaction_ids:
            result = await self.session.execute(
                delete(TransactionModel)
                .where(TransactionModel.external_transaction_id.in_(removed_external_transaction_ids))
                .returning(TransactionModel.id)
            )
            removed = len(result.scalars().all())

        await self.session.flush()
        return created, updated, removed

    async def update_for_user(
        self,
        user_id: UUID,
        transaction_id: UUID,
        **fields,
    ) -> Transaction:
        result = await self.session.execute(
            select(TransactionModel)
            .join(AccountModel, AccountModel.id == TransactionModel.account_id)
            .where(
                TransactionModel.id == transaction_id,
                AccountModel.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise NotFoundError("Transaction", str(transaction_id))
        account = await self.session.get(AccountModel, row.account_id)
        linked = account is not None and account.institution_id is not None
        if linked and any(key != "category" for key in fields):
            raise ValidationError("Linked transaction details are managed by the institution; only category can be edited.")
        for key, value in fields.items():
            if value is not None:
                setattr(row, key, value.value if hasattr(value, "value") else value)
        await self.session.flush()
        return _to_domain(row)

    async def update_budget_category(
        self, user_id: UUID, transaction_id: UUID, budget_category_id: UUID | None
    ) -> Transaction:
        result = await self.session.execute(
            select(TransactionModel)
            .join(AccountModel, AccountModel.id == TransactionModel.account_id)
            .where(TransactionModel.id == transaction_id, AccountModel.user_id == user_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            from app.core.exceptions import NotFoundError

            raise NotFoundError("Transaction", str(transaction_id))
        row.budget_category_id = budget_category_id
        await self.session.flush()
        return _to_domain(row)

    async def list_since_for_income_expense(self, user_id: UUID, since: date) -> list[Transaction]:
        """All income/expense transactions since a date, unfiltered by
        account — used by services that need real transaction history
        rather than a projection (e.g. computing an actual savings rate)."""
        result = await self.session.execute(
            select(TransactionModel)
            .join(AccountModel, AccountModel.id == TransactionModel.account_id)
            .where(
                AccountModel.user_id == user_id,
                TransactionModel.posted_at >= since,
            )
            .order_by(TransactionModel.posted_at.desc(), TransactionModel.id.desc())
        )
        return [_to_domain(row) for row in result.scalars().all()]

    async def totals_by_type_since(
        self,
        user_id: UUID,
        since: date,
        *,
        absolute: bool = False,
    ) -> dict[TransactionType, Decimal]:
        """Compute complete transaction totals in SQL without materializing history."""
        amount = func.abs(TransactionModel.amount) if absolute else TransactionModel.amount
        result = await self.session.execute(
            select(TransactionModel.type, func.sum(amount))
            .join(AccountModel, AccountModel.id == TransactionModel.account_id)
            .where(
                AccountModel.user_id == user_id,
                TransactionModel.posted_at >= since,
            )
            .group_by(TransactionModel.type)
        )
        return {TransactionType(type_): Decimal(total) for type_, total in result.all()}


def _to_domain(row: TransactionModel) -> Transaction:
    return Transaction(
        id=row.id,
        account_id=row.account_id,
        posted_at=row.posted_at,
        merchant=row.merchant,
        category=row.category,
        amount=row.amount,
        type=TransactionType(row.type),
        status=TransactionStatus(row.status),
        external_transaction_id=row.external_transaction_id,
        budget_category_id=row.budget_category_id,
    )
