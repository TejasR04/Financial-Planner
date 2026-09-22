from __future__ import annotations

import calendar
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.config import get_settings
from app.persistence.models import (
    AccountModel,
    InvestmentContributionAdjustmentModel,
    InvestmentContributionRuleModel,
)
from app.persistence.repositories.account_repository import AccountRepository
from app.persistence.repositories.investment_value_snapshot_repository import (
    InvestmentValueSnapshotRepository,
)


def scheduled_date(year: int, month: int, day_of_month: int) -> date:
    return date(year, month, min(day_of_month, calendar.monthrange(year, month)[1]))


def next_scheduled_date(day_of_month: int, on_or_after: date) -> date:
    candidate = scheduled_date(on_or_after.year, on_or_after.month, day_of_month)
    if candidate >= on_or_after:
        return candidate
    year = on_or_after.year + (1 if on_or_after.month == 12 else 0)
    month = 1 if on_or_after.month == 12 else on_or_after.month + 1
    return scheduled_date(year, month, day_of_month)


def following_scheduled_date(day_of_month: int, current: date) -> date:
    year = current.year + (1 if current.month == 12 else 0)
    month = 1 if current.month == 12 else current.month + 1
    return scheduled_date(year, month, day_of_month)


def contribution_today() -> date:
    return datetime.now(ZoneInfo(get_settings().financial_timezone)).date()


class InvestmentContributionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.accounts = AccountRepository(session)
        self.history = InvestmentValueSnapshotRepository(session)

    async def list_rules(self, user_id: UUID, account_id: UUID) -> list[InvestmentContributionRuleModel]:
        await self._eligible_account(user_id, account_id)
        result = await self.session.execute(
            select(InvestmentContributionRuleModel)
            .where(
                InvestmentContributionRuleModel.account_id == account_id,
                InvestmentContributionRuleModel.deleted_at.is_(None),
            )
            .order_by(InvestmentContributionRuleModel.day_of_month, InvestmentContributionRuleModel.created_at)
        )
        return list(result.scalars().all())

    async def create_rule(
        self, user_id: UUID, account_id: UUID, amount: Decimal, day_of_month: int
    ) -> InvestmentContributionRuleModel:
        await self._eligible_account(user_id, account_id)
        rule = InvestmentContributionRuleModel(
            account_id=account_id,
            amount=amount,
            day_of_month=day_of_month,
            next_run_date=next_scheduled_date(day_of_month, contribution_today()),
        )
        self.session.add(rule)
        await self.session.flush()
        await self.apply(user_id, account_id=account_id)
        return rule

    async def delete_rule(self, user_id: UUID, account_id: UUID, rule_id: UUID) -> None:
        await self._eligible_account(user_id, account_id)
        rule = await self.session.scalar(
            select(InvestmentContributionRuleModel).where(
                InvestmentContributionRuleModel.id == rule_id,
                InvestmentContributionRuleModel.account_id == account_id,
            )
        )
        if rule is None:
            raise NotFoundError("Investment contribution rule", str(rule_id))
        rule.active = False
        rule.deleted_at = datetime.now(timezone.utc)
        await self.session.flush()

    async def apply(self, user_id: UUID, account_id: UUID | None = None) -> int:
        query = (
            select(InvestmentContributionRuleModel, AccountModel)
            .join(AccountModel, AccountModel.id == InvestmentContributionRuleModel.account_id)
            .where(
                AccountModel.user_id == user_id,
                AccountModel.type.in_(["investment", "retirement"]),
                AccountModel.institution_id.is_(None),
                AccountModel.archived_at.is_(None),
                InvestmentContributionRuleModel.active.is_(True),
                InvestmentContributionRuleModel.deleted_at.is_(None),
            )
        )
        if account_id is not None:
            query = query.where(AccountModel.id == account_id)
        pairs = (
            await self.session.execute(
                query.order_by(AccountModel.id, InvestmentContributionRuleModel.id).with_for_update()
            )
        ).all()
        today = contribution_today()
        applied = 0
        changed_account_ids: set[UUID] = set()
        for rule, account in pairs:
            while rule.next_run_date <= today:
                event_date = rule.next_run_date
                exists = await self.session.scalar(
                    select(InvestmentContributionAdjustmentModel.id).where(
                        InvestmentContributionAdjustmentModel.rule_id == rule.id,
                        InvestmentContributionAdjustmentModel.scheduled_for == event_date,
                    )
                )
                if exists is None:
                    account.balance += rule.amount
                    account.updated_at = datetime.now(timezone.utc)
                    self.session.add(
                        InvestmentContributionAdjustmentModel(
                            rule_id=rule.id,
                            account_id=account.id,
                            scheduled_for=event_date,
                            amount=rule.amount,
                        )
                    )
                    changed_account_ids.add(account.id)
                    applied += 1
                rule.next_run_date = following_scheduled_date(rule.day_of_month, event_date)
        await self.session.flush()
        if changed_account_ids:
            changed_accounts = [
                await self.accounts.get_for_user(user_id, changed_account_id)
                for changed_account_id in changed_account_ids
            ]
            await self.history.record_for_accounts(changed_accounts, as_of=today)
        return applied

    async def _eligible_account(self, user_id: UUID, account_id: UUID) -> AccountModel:
        account = await self.session.scalar(
            select(AccountModel).where(
                AccountModel.id == account_id,
                AccountModel.user_id == user_id,
                AccountModel.archived_at.is_(None),
            )
        )
        if account is None:
            raise NotFoundError("Account", str(account_id))
        if account.institution_id is not None or account.type not in {"investment", "retirement"}:
            raise ValidationError(
                "Recurring contributions are only available for manual investment or retirement accounts."
            )
        return account
