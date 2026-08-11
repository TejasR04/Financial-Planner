from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
            .where(LoanBalanceRuleModel.account_id == account_id)
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
        await self.session.delete(rule)
        await self.session.flush()

    async def apply(self, user_id: UUID, account_id: UUID | None = None) -> int:
        query = (
            select(LoanBalanceRuleModel, AccountModel)
            .join(AccountModel, AccountModel.id == LoanBalanceRuleModel.account_id)
            .where(
                AccountModel.user_id == user_id,
                AccountModel.institution_id.is_(None),
                AccountModel.archived_at.is_(None),
                LoanBalanceRuleModel.active.is_(True),
            )
        )
        if account_id is not None:
            query = query.where(AccountModel.id == account_id)
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
                TransactionModel.deleted_at.is_(None),
                TransactionModel.posted_at >= rule.created_at.date(),
                TransactionModel.merchant.ilike(f"%{pattern}%"),
            )
            .order_by(TransactionModel.posted_at, TransactionModel.id)
        )
        count = 0
        for transaction in result.scalars().all():
            if account.balance >= 0:
                rule.active = False
                break
            event_key = f"transaction:{transaction.id}"
            if await self._already_applied(rule.id, event_key):
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
                )
            )
        ) is not None

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
                transaction_id=transaction_id,
                event_key=event_key,
                amount_applied=amount,
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
