"""Assembles a `FinancialSnapshot` from the repositories for a given user.

This is the one place that's allowed to combine multiple repositories into
the object `RecommendationEngine` and `FinancialHealthService` operate on.
It lives in `app/persistence/` (not `app/services/`) specifically because it
*is* DB-aware — every pure service downstream of this stays DB-free.
"""
from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import FinancialSnapshot
from app.persistence.repositories.account_repository import AccountRepository
from app.persistence.repositories.goal_repository import GoalRepository
from app.persistence.repositories.holding_repository import HoldingRepository
from app.persistence.repositories.income_source_repository import IncomeSourceRepository
from app.persistence.repositories.liability_repository import LiabilityRepository
from app.persistence.repositories.user_repository import UserRepository


async def build_financial_snapshot(session: AsyncSession, user_id: UUID) -> FinancialSnapshot:
    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(user_id)
    profile = await user_repo.get_planning_profile(user_id)

    accounts = await AccountRepository(session).list_for_user(user_id)
    holdings = await HoldingRepository(session).list_for_user(user_id)
    liabilities = await LiabilityRepository(session).list_for_user(user_id)
    income_sources = await IncomeSourceRepository(session).list_for_user(user_id)
    goals = await GoalRepository(session).list_for_user(user_id)

    return FinancialSnapshot(
        user=user,
        profile=profile,
        accounts=accounts,
        holdings=holdings,
        liabilities=liabilities,
        income_sources=income_sources,
        goals=goals,
        as_of=date.today(),
    )
