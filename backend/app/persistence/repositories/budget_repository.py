from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import select

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.persistence.models import BudgetCategoryModel, MerchantBudgetRuleModel, TransactionModel
from app.persistence.repositories.base import BaseRepository


def normalize_merchant(value: str) -> str:
    return " ".join(value.lower().replace("_", " ").split())


class BudgetRepository(BaseRepository[BudgetCategoryModel]):
    model = BudgetCategoryModel

    async def list_categories(self, user_id: UUID) -> list[BudgetCategoryModel]:
        result = await self.session.execute(
            select(BudgetCategoryModel)
            .where(BudgetCategoryModel.user_id == user_id)
            .order_by(BudgetCategoryModel.sort_order, BudgetCategoryModel.name)
        )
        return list(result.scalars().all())

    async def create_category(self, user_id: UUID, name: str, group_name: str, monthly_limit) -> BudgetCategoryModel:
        existing = await self.list_categories(user_id)
        if any(category.name.casefold() == name.strip().casefold() for category in existing):
            raise ConflictError("A budget category with that name already exists")
        row = BudgetCategoryModel(
            id=uuid4(), user_id=user_id, name=name.strip(), group_name=group_name.strip(),
            monthly_limit=monthly_limit, sort_order=len(existing),
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def get_category_for_user(self, user_id: UUID, category_id: UUID) -> BudgetCategoryModel:
        result = await self.session.execute(
            select(BudgetCategoryModel).where(BudgetCategoryModel.id == category_id, BudgetCategoryModel.user_id == user_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise NotFoundError("Budget category", str(category_id))
        return row

    async def update_category(self, user_id: UUID, category_id: UUID, **fields) -> BudgetCategoryModel:
        row = await self.get_category_for_user(user_id, category_id)
        for key, value in fields.items():
            if value is not None:
                setattr(row, key, value.strip() if key in {"name", "group_name"} else value)
        await self.session.flush()
        return row

    async def list_rules(self, user_id: UUID) -> list[tuple[MerchantBudgetRuleModel, BudgetCategoryModel]]:
        result = await self.session.execute(
            select(MerchantBudgetRuleModel, BudgetCategoryModel)
            .join(BudgetCategoryModel, BudgetCategoryModel.id == MerchantBudgetRuleModel.budget_category_id)
            .where(MerchantBudgetRuleModel.user_id == user_id)
            .order_by(MerchantBudgetRuleModel.created_at)
        )
        return list(result.all())

    async def create_rule(self, user_id: UUID, category_id: UUID, merchant_pattern: str) -> MerchantBudgetRuleModel:
        await self.get_category_for_user(user_id, category_id)
        normalized = normalize_merchant(merchant_pattern)
        if not normalized:
            raise ValidationError("Merchant pattern cannot be blank")
        existing = await self.session.execute(
            select(MerchantBudgetRuleModel.id).where(
                MerchantBudgetRuleModel.user_id == user_id,
                MerchantBudgetRuleModel.merchant_pattern == normalized,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError("A merchant rule with that pattern already exists")
        row = MerchantBudgetRuleModel(
            id=uuid4(), user_id=user_id, budget_category_id=category_id, merchant_pattern=normalized
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def delete_rule(self, user_id: UUID, rule_id: UUID) -> None:
        result = await self.session.execute(
            select(MerchantBudgetRuleModel).where(MerchantBudgetRuleModel.id == rule_id, MerchantBudgetRuleModel.user_id == user_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise NotFoundError("Merchant rule", str(rule_id))
        await self.session.delete(row)
        await self.session.flush()

    async def expense_transactions_for_month(self, user_id: UUID, start: date, end: date) -> list[TransactionModel]:
        from app.persistence.models import AccountModel

        result = await self.session.execute(
            select(TransactionModel)
            .join(AccountModel, AccountModel.id == TransactionModel.account_id)
            .where(
                AccountModel.user_id == user_id,
                TransactionModel.posted_at >= start,
                TransactionModel.posted_at <= end,
                TransactionModel.type == "expense",
            )
        )
        return list(result.scalars().all())
