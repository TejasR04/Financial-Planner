from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import re
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.exceptions import NotFoundError, ValidationError
from app.domain.entities import Transaction
from app.domain.enums import TransactionStatus, TransactionType
from app.persistence.models import AccountModel, BudgetCategoryModel, TransactionModel
from app.persistence.repositories.base import BaseRepository


class TransactionRepository(BaseRepository[TransactionModel]):
    model = TransactionModel

    async def list_for_user(
        self,
        user_id: UUID,
        account_id: UUID | None = None,
        category: str | None = None,
        budget_category_id: UUID | None = None,
        direction: str | None = None,
        search: str | None = None,
        merchant: str | None = None,
        since: date | None = None,
        until: date | None = None,
        limit: int = 50,
        offset: int = 0,
        include_archived: bool = False,
        cash_flow_only: bool = False,
        transaction_type: str | None = None,
    ) -> tuple[list[Transaction], int]:
        query = (
            select(TransactionModel, AccountModel.name, AccountModel.archived_at, BudgetCategoryModel.name)
            .join(AccountModel, AccountModel.id == TransactionModel.account_id)
            .outerjoin(BudgetCategoryModel, BudgetCategoryModel.id == TransactionModel.budget_category_id)
            .where(AccountModel.user_id == user_id, TransactionModel.deleted_at.is_(None))
        )
        if not include_archived:
            query = query.where(AccountModel.archived_at.is_(None))
        if account_id is not None:
            query = query.where(TransactionModel.account_id == account_id)
        if transaction_type is not None:
            query = query.where(TransactionModel.type == transaction_type)
        if category is not None and category.strip():
            # Categories arrive from providers as identifiers such as
            # "rent_and_utilities". Match the typed characters anywhere in
            # that identifier, regardless of case, while treating underscores
            # like spaces for a natural search experience.
            normalized_category = func.replace(func.lower(TransactionModel.category), "_", " ")
            normalized_query = " ".join(category.lower().replace("_", " ").split())
            query = query.where(
                normalized_category.contains(normalized_query, autoescape=True)
                | func.lower(BudgetCategoryModel.name).contains(normalized_query, autoescape=True)
            )
        if budget_category_id is not None:
            query = query.where(TransactionModel.budget_category_id == budget_category_id)
        search_value = search if search is not None else merchant
        if search_value is not None and search_value.strip():
            normalized_search = " ".join(search_value.lower().split())
            search_filter = func.lower(TransactionModel.merchant).contains(normalized_search, autoescape=True)
            try:
                candidate_amount = Decimal(normalized_search.replace("$", "").replace(",", ""))
                searched_amount = abs(candidate_amount) if candidate_amount.is_finite() else None
            except InvalidOperation:
                searched_amount = None
            if searched_amount is not None:
                search_filter = search_filter | (func.abs(TransactionModel.amount) == searched_amount)
            query = query.where(search_filter)
        if direction == "inflow":
            query = query.where(TransactionModel.amount > 0)
        elif direction == "outflow":
            query = query.where(TransactionModel.amount < 0)
        if cash_flow_only:
            upper_category = func.upper(TransactionModel.category)
            upper_merchant = func.upper(TransactionModel.merchant)
            recognized_card_payment = (
                (upper_category == "LOAN_PAYMENTS_CREDIT_CARD_PAYMENT")
                | upper_merchant.contains("PAYMENT - BILT")
                | (
                    (upper_category == "LOAN_PAYMENTS")
                    & (
                        upper_merchant.contains("CREDIT CRD")
                        | upper_merchant.contains("CREDIT CARD")
                        | upper_merchant.contains("AUTOPAY PAYMENT")
                        | upper_merchant.contains("AUTOMATIC PAYMENT")
                        | upper_merchant.contains("PAYMENT - THANK")
                    )
                )
            )
            query = query.where(
                TransactionModel.type.not_in(["transfer", "credit_card_payment"]),
                ~recognized_card_payment,
            )
        if since is not None:
            query = query.where(TransactionModel.posted_at >= since)
        if until is not None:
            query = query.where(TransactionModel.posted_at <= until)

        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        query = query.order_by(
            TransactionModel.posted_at.desc(), TransactionModel.id.desc()
        ).limit(limit).offset(offset)
        result = await self.session.execute(query)
        rows = result.all()
        return [
            _to_domain(row, account_name=name, account_archived=archived_at is not None, budget_category_name=budget_name)
            for row, name, archived_at, budget_name in rows
        ], total

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

    async def bulk_create_deduplicated(self, transactions: list[Transaction]) -> tuple[list[Transaction], int]:
        """Insert CSV rows unless a likely copy already exists."""
        if not transactions:
            return [], 0
        account_ids = {transaction.account_id for transaction in transactions}
        first_date = min(transaction.posted_at for transaction in transactions) - timedelta(days=IMPORT_DATE_TOLERANCE_DAYS)
        last_date = max(transaction.posted_at for transaction in transactions) + timedelta(days=IMPORT_DATE_TOLERANCE_DAYS)
        existing = list((await self.session.execute(
            select(TransactionModel).where(
                TransactionModel.account_id.in_(account_ids),
                TransactionModel.posted_at >= first_date,
                TransactionModel.posted_at <= last_date,
                TransactionModel.deleted_at.is_(None),
            )
        )).scalars().all())

        existing_by_account_amount: dict[tuple[UUID, Decimal], list[TransactionModel]] = {}
        for row in existing:
            existing_by_account_amount.setdefault((row.account_id, row.amount), []).append(row)

        accepted: list[Transaction] = []
        accepted_by_account_amount: dict[tuple[UUID, Decimal], list[Transaction]] = {}
        skipped = 0
        for transaction in transactions:
            key = (transaction.account_id, transaction.amount)
            duplicate_existing = any(
                abs((row.posted_at - transaction.posted_at).days) <= IMPORT_DATE_TOLERANCE_DAYS
                and merchants_likely_match(row.merchant, transaction.merchant)
                for row in existing_by_account_amount.get(key, [])
            )
            duplicate_in_file = any(
                abs((row.posted_at - transaction.posted_at).days) <= IMPORT_DATE_TOLERANCE_DAYS
                and merchants_likely_match(row.merchant, transaction.merchant)
                for row in accepted_by_account_amount.get(key, [])
            )
            if duplicate_existing or duplicate_in_file:
                skipped += 1
            else:
                accepted.append(transaction)
                accepted_by_account_amount.setdefault(key, []).append(transaction)
        if not accepted:
            return [], skipped
        values = [
            {
                "id": transaction.id or uuid4(),
                "account_id": transaction.account_id,
                "posted_at": transaction.posted_at,
                "merchant": transaction.merchant,
                "category": transaction.category,
                "amount": transaction.amount,
                "type": transaction.type.value,
                "status": transaction.status.value,
                "external_transaction_id": transaction.external_transaction_id,
                "import_fingerprint": import_fingerprint(transaction),
            }
            for transaction in accepted
        ]
        result = await self.session.execute(
            pg_insert(TransactionModel)
            .values(values)
            .on_conflict_do_nothing()
            .returning(TransactionModel)
        )
        rows = list(result.scalars().all())
        await self.session.flush()
        return [_to_domain(row) for row in rows], skipped + len(accepted) - len(rows)

    async def import_duplicate_flags(self, transactions: list[Transaction]) -> list[bool]:
        """Return likely-duplicate decisions without changing the database."""
        if not transactions:
            return []
        account_ids = {transaction.account_id for transaction in transactions}
        first_date = min(row.posted_at for row in transactions) - timedelta(days=IMPORT_DATE_TOLERANCE_DAYS)
        last_date = max(row.posted_at for row in transactions) + timedelta(days=IMPORT_DATE_TOLERANCE_DAYS)
        existing = list((await self.session.execute(
            select(TransactionModel).where(
                TransactionModel.account_id.in_(account_ids),
                TransactionModel.posted_at >= first_date,
                TransactionModel.posted_at <= last_date,
                TransactionModel.deleted_at.is_(None),
            )
        )).scalars().all())
        existing_by_account_amount: dict[tuple[UUID, Decimal], list[TransactionModel | Transaction]] = {}
        for row in existing:
            existing_by_account_amount.setdefault((row.account_id, row.amount), []).append(row)
        seen: list[Transaction] = []
        flags: list[bool] = []
        for transaction in transactions:
            key = (transaction.account_id, transaction.amount)
            duplicate = any(
                abs((row.posted_at - transaction.posted_at).days) <= IMPORT_DATE_TOLERANCE_DAYS
                and merchants_likely_match(row.merchant, transaction.merchant)
                for row in existing_by_account_amount.get(key, [])
            )
            flags.append(duplicate)
            if not duplicate:
                seen.append(transaction)
                existing_by_account_amount.setdefault(key, []).append(transaction)
        return flags

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

        # A CSV import can precede the institution sync. Reuse a uniquely
        # matching imported row (amount, merchant, and nearby posting date)
        # and attach Plaid's stable ID instead of creating a duplicate.
        import_candidates: list[TransactionModel] = []
        if transactions_by_external_id:
            incoming = list(transactions_by_external_id.values())
            result = await self.session.execute(
                select(TransactionModel).where(
                    TransactionModel.account_id.in_({row.account_id for row in incoming}),
                    TransactionModel.external_transaction_id.is_(None),
                    TransactionModel.import_fingerprint.is_not(None),
                    TransactionModel.deleted_at.is_(None),
                    TransactionModel.posted_at >= min(row.posted_at for row in incoming) - timedelta(days=IMPORT_DATE_TOLERANCE_DAYS),
                    TransactionModel.posted_at <= max(row.posted_at for row in incoming) + timedelta(days=IMPORT_DATE_TOLERANCE_DAYS),
                )
            )
            import_candidates = list(result.scalars().all())

        created = updated = 0
        for external_id, transaction in transactions_by_external_id.items():
            row = existing_by_external_id.get(external_id)
            if row is None:
                matches = [
                    candidate for candidate in import_candidates
                    if candidate.account_id == transaction.account_id
                    and candidate.amount == transaction.amount
                    and abs((candidate.posted_at - transaction.posted_at).days) <= IMPORT_DATE_TOLERANCE_DAYS
                    and merchants_likely_match(candidate.merchant, transaction.merchant)
                ]
                if len(matches) == 1:
                    row = matches[0]
                    import_candidates.remove(row)
                    row.posted_at = transaction.posted_at
                    row.merchant = transaction.merchant
                    row.category = transaction.category
                    row.amount = transaction.amount
                    row.type = transaction.type.value
                    row.status = transaction.status.value
                    row.external_transaction_id = external_id
                    updated += 1
                    continue
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
                .where(
                    TransactionModel.external_transaction_id.in_(removed_external_transaction_ids),
                    TransactionModel.deleted_at.is_(None),
                )
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
                TransactionModel.deleted_at.is_(None),
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
        self, user_id: UUID, transaction_id: UUID, budget_category_id: UUID | None, ignored_from_budget: bool | None = None
    ) -> Transaction:
        result = await self.session.execute(
            select(TransactionModel)
            .join(AccountModel, AccountModel.id == TransactionModel.account_id)
            .where(TransactionModel.id == transaction_id, AccountModel.user_id == user_id, TransactionModel.deleted_at.is_(None))
        )
        row = result.scalar_one_or_none()
        if row is None:
            from app.core.exceptions import NotFoundError

            raise NotFoundError("Transaction", str(transaction_id))
        row.budget_category_id = budget_category_id
        if ignored_from_budget is not None:
            row.ignored_from_budget = ignored_from_budget
        row.reviewed_at = datetime.now(timezone.utc)
        await self.session.flush()
        return _to_domain(row)

    async def mark_reviewed(self, user_id: UUID, transaction_id: UUID) -> None:
        result = await self.session.execute(
            select(TransactionModel)
            .join(AccountModel, AccountModel.id == TransactionModel.account_id)
            .where(TransactionModel.id == transaction_id, AccountModel.user_id == user_id, TransactionModel.deleted_at.is_(None))
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise NotFoundError("Transaction", str(transaction_id))
        row.reviewed_at = datetime.now(timezone.utc)
        await self.session.flush()

    async def set_user_classification(
        self, user_id: UUID, transaction_id: UUID, transaction_type: TransactionType
    ) -> Transaction:
        result = await self.session.execute(
            select(TransactionModel)
            .join(AccountModel, AccountModel.id == TransactionModel.account_id)
            .where(TransactionModel.id == transaction_id, AccountModel.user_id == user_id, TransactionModel.deleted_at.is_(None))
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise NotFoundError("Transaction", str(transaction_id))
        row.type = transaction_type.value
        if transaction_type in {
            TransactionType.TRANSFER, TransactionType.INCOME, TransactionType.CREDIT_CARD_PAYMENT
        }:
            row.budget_category_id = None
            row.ignored_from_budget = False
        row.reviewed_at = datetime.now(timezone.utc)
        await self.session.flush()
        return _to_domain(row)

    async def delete_for_user(self, user_id: UUID, transaction_id: UUID) -> None:
        result = await self.session.execute(
            select(TransactionModel)
            .join(AccountModel, AccountModel.id == TransactionModel.account_id)
            .where(
                TransactionModel.id == transaction_id,
                AccountModel.user_id == user_id,
                TransactionModel.deleted_at.is_(None),
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise NotFoundError("Transaction", str(transaction_id))
        row.deleted_at = datetime.now(timezone.utc)
        await self.session.flush()

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
                TransactionModel.deleted_at.is_(None),
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
                TransactionModel.deleted_at.is_(None),
            )
            .group_by(TransactionModel.type)
        )
        return {TransactionType(type_): Decimal(total) for type_, total in result.all()}


_MERCHANT_NOISE = {
    "ach", "card", "checkcard", "credit", "debit", "id", "payment", "paymentrec",
    "pos", "ppd", "purchase", "recurring", "sq", "square", "visa",
}
IMPORT_DATE_TOLERANCE_DAYS = 3


def _normalized_merchant(value: str) -> str:
    tokens = re.findall(r"[a-z0-9]+", value.lower())
    meaningful = [token for token in tokens if token not in _MERCHANT_NOISE and not (token.isdigit() and len(token) >= 4)]
    return " ".join(meaningful)


def merchants_likely_match(left: str, right: str) -> bool:
    left_normalized = _normalized_merchant(left)
    right_normalized = _normalized_merchant(right)
    if not left_normalized or not right_normalized:
        return False
    if left_normalized == right_normalized:
        return True
    left_tokens = set(left_normalized.split())
    right_tokens = set(right_normalized.split())
    shared = left_tokens & right_tokens
    smaller_size = min(len(left_tokens), len(right_tokens))
    # A single-word name must match exactly ("Uber" is not "Uber Eats").
    # Multi-word names match when most words from the shorter variant appear
    # in the longer one ("Dept Education" matches "Dept Education Loan").
    return smaller_size >= 2 and len(shared) >= 2 and len(shared) / smaller_size >= (2 / 3)


def import_fingerprint(transaction: Transaction) -> str:
    identity = "|".join((
        str(transaction.account_id),
        transaction.posted_at.isoformat(),
        format(transaction.amount, "f"),
        _normalized_merchant(transaction.merchant),
    ))
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _to_domain(
    row: TransactionModel,
    account_name: str | None = None,
    account_archived: bool = False,
    budget_category_name: str | None = None,
) -> Transaction:
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
        budget_category_name=budget_category_name,
        ignored_from_budget=getattr(row, "ignored_from_budget", False),
        account_name=account_name,
        account_archived=account_archived,
    )
