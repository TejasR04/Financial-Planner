from __future__ import annotations

import calendar
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.domain.merchant_rules import merchant_matches_rule
from app.core.exceptions import NotFoundError, ValidationError
from app.persistence.models import (
    AccountModel,
    LoanBalanceAdjustmentModel,
    LoanBalanceRuleModel,
    TransactionModel,
)


def _next_month(value: date) -> date:
    year = value.year + (1 if value.month == 12 else 0)
    month = 1 if value.month == 12 else value.month + 1
    return value.replace(year=year, month=month, day=min(value.day, calendar.monthrange(year, month)[1]))


class LoanBalanceAutomationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_rules(self, user_id: UUID, account_id: UUID) -> list[LoanBalanceRuleModel]:
        await self._eligible_account(user_id, account_id)
        result = await self.session.execute(
            select(LoanBalanceRuleModel)
            .where(LoanBalanceRuleModel.account_id == account_id, LoanBalanceRuleModel.deleted_at.is_(None))
            .order_by(LoanBalanceRuleModel.created_at)
        )
        return list(result.scalars().all())

    async def create_rule(self, user_id: UUID, account_id: UUID, **fields) -> LoanBalanceRuleModel:
        await self._eligible_account(user_id, account_id)
        rule = LoanBalanceRuleModel(account_id=account_id, **fields)
        self.session.add(rule)
        await self.session.flush()
        await self.apply(user_id, account_id=account_id)
        return rule

    async def delete_rule(self, user_id: UUID, account_id: UUID, rule_id: UUID) -> None:
        await self._eligible_account(user_id, account_id)
        result = await self.session.execute(
            select(LoanBalanceRuleModel).where(
                LoanBalanceRuleModel.id == rule_id,
                LoanBalanceRuleModel.account_id == account_id,
            )
        )
        rule = result.scalar_one_or_none()
        if rule is None:
            raise NotFoundError("Loan balance rule", str(rule_id))
        rule.active = False
        rule.deleted_at = datetime.now(timezone.utc)
        await self.session.flush()

    async def apply(self, user_id: UUID, account_id: UUID | None = None) -> int:
        await self.reconcile(user_id, account_id)
        query = (
            select(LoanBalanceRuleModel, AccountModel)
            .join(AccountModel, AccountModel.id == LoanBalanceRuleModel.account_id)
            .where(
                AccountModel.user_id == user_id,
                AccountModel.institution_id.is_(None),
                AccountModel.archived_at.is_(None),
                LoanBalanceRuleModel.active.is_(True),
                LoanBalanceRuleModel.deleted_at.is_(None),
            )
        )
        if account_id is not None:
            query = query.where(AccountModel.id == account_id)
        query = query.order_by(AccountModel.id, LoanBalanceRuleModel.id).with_for_update(of=AccountModel)
        pairs = (await self.session.execute(query)).all()
        applied = 0
        for rule, account in pairs:
            if account.balance >= 0:
                rule.active = False
                continue
            if rule.mode == "scheduled":
                applied += await self._apply_scheduled(rule, account)
            else:
                applied += await self._apply_merchant(rule, account, user_id)
        await self.session.flush()
        return applied

    async def reconcile(self, user_id: UUID, account_id: UUID | None = None) -> None:
        """Replay merchant adjustments so edits, removals, and caps cascade correctly."""
        source_account = aliased(AccountModel)
        query = (
            select(LoanBalanceAdjustmentModel, LoanBalanceRuleModel, AccountModel, TransactionModel, source_account)
            .join(LoanBalanceRuleModel, LoanBalanceRuleModel.id == LoanBalanceAdjustmentModel.rule_id)
            .join(AccountModel, AccountModel.id == LoanBalanceAdjustmentModel.account_id)
            .outerjoin(TransactionModel, TransactionModel.id == LoanBalanceAdjustmentModel.transaction_id)
            .outerjoin(source_account, source_account.id == TransactionModel.account_id)
            .where(
                AccountModel.user_id == user_id,
                LoanBalanceAdjustmentModel.transaction_id.is_not(None),
                LoanBalanceAdjustmentModel.reversed_at.is_(None),
            )
            .order_by(AccountModel.id, TransactionModel.posted_at, TransactionModel.id, LoanBalanceAdjustmentModel.id)
            .with_for_update(of=AccountModel)
        )
        if account_id is not None:
            query = query.where(AccountModel.id == account_id)
        grouped: dict[UUID, list[Any]] = {}
        for values in (await self.session.execute(query)).all():
            grouped.setdefault(values[2].id, []).append(values)
        for rows in grouped.values():
            account = rows[0][2]
            account.balance -= sum((row[0].amount_applied for row in rows), Decimal("0"))
            seen: set[UUID] = set()
            for adjustment, rule, _, transaction, source in rows:
                valid = (
                    transaction is not None
                    and source is not None
                    and source.user_id == user_id
                    and source.archived_at is None
                    and source.id != account.id
                    and transaction.deleted_at is None
                    and transaction.status == "cleared"
                    and transaction.amount < 0
                    and transaction.posted_at > rule.created_at.date()
                    and merchant_matches_rule(transaction.merchant, rule.merchant_pattern or "", collapse_transfers=False)
                    and transaction.id not in seen
                )
                requested = abs(transaction.amount) if valid else Decimal("0")
                expected = min(abs(account.balance), requested) if account.balance < 0 else Decimal("0")
                unchanged = (
                    valid
                    and requested == adjustment.source_amount
                    and expected == adjustment.amount_applied
                )
                if valid:
                    seen.add(transaction.id)
                if unchanged:
                    account.balance += expected
                else:
                    adjustment.reversed_at = datetime.now(timezone.utc)
                    adjustment.reversal_reason = "source_changed" if valid else "source_removed_or_ineligible"
                    await self.session.flush()
                    if valid and expected > 0:
                        rule.active = True
                        self._reduce(account, rule, requested, adjustment.event_key, transaction.id)
            for _, rule, _, _, _ in rows:
                if rule.deleted_at is None:
                    rule.active = account.balance < 0
        await self.session.flush()

    async def _apply_scheduled(self, rule: LoanBalanceRuleModel, account: AccountModel) -> int:
        today = date.today()
        count = 0
        while rule.active and rule.next_run_date is not None and rule.next_run_date <= today and account.balance < 0:
            event_date = rule.next_run_date
            if not await self._already_applied(rule.id, f"scheduled:{event_date.isoformat()}"):
                self._reduce(account, rule, rule.amount or Decimal("0"), f"scheduled:{event_date.isoformat()}")
                count += 1
            if rule.frequency == "once":
                rule.active = False
            else:
                rule.next_run_date = _next_month(event_date)
        return count

    async def _apply_merchant(self, rule: LoanBalanceRuleModel, account: AccountModel, user_id: UUID) -> int:
        pattern = (rule.merchant_pattern or "").lower()
        result = await self.session.execute(
            select(TransactionModel)
            .join(AccountModel, AccountModel.id == TransactionModel.account_id)
            .where(
                AccountModel.user_id == user_id,
                TransactionModel.account_id != account.id,
                TransactionModel.status == "cleared",
                AccountModel.archived_at.is_(None),
                TransactionModel.amount < 0,
                TransactionModel.deleted_at.is_(None),
                TransactionModel.posted_at > rule.created_at.date(),
            )
            .order_by(TransactionModel.posted_at, TransactionModel.id)
        )
        count = 0
        for transaction in result.scalars().all():
            if not merchant_matches_rule(transaction.merchant, pattern, collapse_transfers=False):
                continue
            if account.balance >= 0:
                rule.active = False
                break
            event_key = f"transaction:{transaction.id}"
            if await self._already_applied(rule.id, event_key):
                continue
            if await self._transaction_already_applied(account.id, transaction.id):
                continue
            self._reduce(account, rule, abs(transaction.amount), event_key, transaction.id)
            count += 1
        return count

    async def _already_applied(self, rule_id: UUID, event_key: str) -> bool:
        return (
            await self.session.scalar(
                select(LoanBalanceAdjustmentModel.id).where(
                    LoanBalanceAdjustmentModel.rule_id == rule_id,
                    LoanBalanceAdjustmentModel.event_key == event_key,
                    LoanBalanceAdjustmentModel.reversed_at.is_(None),
                )
            )
        ) is not None

    async def _transaction_already_applied(self, account_id: UUID, transaction_id: UUID) -> bool:
        return (await self.session.scalar(select(LoanBalanceAdjustmentModel.id).where(
            LoanBalanceAdjustmentModel.account_id == account_id,
            LoanBalanceAdjustmentModel.transaction_id == transaction_id,
            LoanBalanceAdjustmentModel.reversed_at.is_(None),
        ))) is not None

    def _reduce(
        self,
        account: AccountModel,
        rule: LoanBalanceRuleModel,
        requested: Decimal,
        event_key: str,
        transaction_id: UUID | None = None,
    ) -> None:
        amount = min(abs(account.balance), requested)
        if amount <= 0:
            return
        account.balance += amount
        self.session.add(
            LoanBalanceAdjustmentModel(
                rule_id=rule.id,
                account_id=account.id,
                transaction_id=transaction_id,
                event_key=event_key,
                amount_applied=amount,
                source_amount=requested,
            )
        )
        if account.balance >= 0:
            account.balance = Decimal("0")
            rule.active = False

    async def _eligible_account(self, user_id: UUID, account_id: UUID) -> AccountModel:
        result = await self.session.execute(
            select(AccountModel).where(
                AccountModel.id == account_id,
                AccountModel.user_id == user_id,
                AccountModel.archived_at.is_(None),
            )
        )
        account = result.scalar_one_or_none()
        if account is None:
            raise NotFoundError("Account", str(account_id))
        if account.institution_id is not None or account.type not in {"loan", "credit"}:
            raise ValidationError("Automatic balance reductions are only available for manual loan or credit accounts.")
        return account
