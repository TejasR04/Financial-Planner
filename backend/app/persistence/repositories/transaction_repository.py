from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select

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
        if category is not None:
            query = query.where(TransactionModel.category == category)
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
        created = updated = 0
        for transaction in transactions:
            external_id = transaction.external_transaction_id
            if external_id is None:
                raise ValueError("Plaid transactions require an external_transaction_id")
            result = await self.session.execute(
                select(TransactionModel).where(TransactionModel.external_transaction_id == external_id)
            )
            row = result.scalar_one_or_none()
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

    async def update_category(self, transaction_id: UUID, category: str) -> Transaction:
        row = await self._get_or_raise("Transaction", transaction_id)
        row.category = category
        await self.session.flush()
        return _to_domain(row)

    async def list_since_for_income_expense(self, user_id: UUID, since: date) -> list[Transaction]:
        """All income/expense transactions since a date, unfiltered by
        account — used by services that need real transaction history
        rather than a projection (e.g. computing an actual savings rate)."""
        transactions, _ = await self.list_for_user(user_id, since=since, limit=10_000, offset=0)
        return transactions


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
    )
