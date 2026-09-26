from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import case, func, select, update
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domain.enums import TransactionType
from app.domain.merchant_rules import normalize_merchant_rule
from app.persistence.models import BudgetCategoryModel, MerchantBudgetRuleModel, TransactionModel
from app.persistence.repositories.base import BaseRepository


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
        normalized_name = name.strip()
        existing = await self.list_categories(user_id)
        if await self._category_name_exists(user_id, normalized_name):
            raise ConflictError("A budget category with that name already exists")
        row = BudgetCategoryModel(
            id=uuid4(), user_id=user_id, name=normalized_name, group_name=group_name.strip(),
            monthly_limit=monthly_limit, sort_order=len(existing),
        )
        self.session.add(row)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            raise ConflictError("A budget category with that name already exists") from exc
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
        requested_name = fields.get("name")
        if requested_name is not None:
            requested_name = requested_name.strip()
            if await self._category_name_exists(user_id, requested_name, excluding_id=category_id):
                raise ConflictError("A budget category with that name already exists")
            fields["name"] = requested_name
        for key, value in fields.items():
            if value is not None:
                setattr(row, key, value.strip() if key in {"name", "group_name"} else value)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            raise ConflictError("A budget category with that name already exists") from exc
        return row

    async def _category_name_exists(
        self,
        user_id: UUID,
        name: str,
        *,
        excluding_id: UUID | None = None,
    ) -> bool:
        query = select(BudgetCategoryModel.id).where(
            BudgetCategoryModel.user_id == user_id,
            func.lower(BudgetCategoryModel.name) == name.lower(),
        )
        if excluding_id is not None:
            query = query.where(BudgetCategoryModel.id != excluding_id)
        return await self.session.scalar(query) is not None

    async def list_rules(self, user_id: UUID) -> list[tuple[MerchantBudgetRuleModel, BudgetCategoryModel | None]]:
        result = await self.session.execute(
            select(MerchantBudgetRuleModel, BudgetCategoryModel)
            .outerjoin(BudgetCategoryModel, BudgetCategoryModel.id == MerchantBudgetRuleModel.budget_category_id)
            .where(MerchantBudgetRuleModel.user_id == user_id)
            .order_by(MerchantBudgetRuleModel.created_at)
        )
        return list(result.all())

    async def create_rule(
        self,
        user_id: UUID,
        category_id: UUID | None,
        merchant_pattern: str,
        transaction_type: TransactionType | None = None,
    ) -> MerchantBudgetRuleModel:
        if category_id is not None:
            await self.get_category_for_user(user_id, category_id)
        elif transaction_type not in {
            TransactionType.INCOME, TransactionType.TRANSFER, TransactionType.CREDIT_CARD_PAYMENT
        }:
            raise ValidationError("Merchant rules require a budget category, income, transfer, or credit card payment treatment")
        normalized = normalize_merchant_rule(merchant_pattern)
        if not normalized:
            raise ValidationError("Merchant pattern cannot be blank")
        if any(normalize_merchant_rule(rule.merchant_pattern) == normalized for rule, _ in await self.list_rules(user_id)):
            raise ConflictError("A merchant rule with that pattern already exists")
        row = MerchantBudgetRuleModel(
            id=uuid4(), user_id=user_id, budget_category_id=category_id,
            transaction_type=transaction_type.value if transaction_type else None,
            merchant_pattern=normalized,
        )
        self.session.add(row)
        await self.session.flush()
        await self.apply_merchant_rules_for_user(user_id, include_reviewed=True)
        return row

    async def apply_merchant_rules_for_user(self, user_id: UUID, *, include_reviewed: bool = False) -> int:
        """Materialize active merchant rules on every currently unassigned
        expense. Persisting the assignment keeps the ledger, exports, and
        category filters consistent instead of applying rules only to budget
        rollups.
        """
        from app.persistence.models import AccountModel

        updated_count = 0
        for rule, category in await self.list_rules(user_id):
            if category is not None and not category.active:
                continue
            normalized_merchant = func.replace(func.lower(TransactionModel.merchant), "_", " ")
            stable_pattern = normalize_merchant_rule(rule.merchant_pattern)
            if not stable_pattern:
                continue
            conditions = [
                TransactionModel.deleted_at.is_(None),
                TransactionModel.account_id.in_(
                    select(AccountModel.id).where(AccountModel.user_id == user_id)
                ),
                *(normalized_merchant.contains(word, autoescape=True) for word in stable_pattern.split()),
            ]
            # Creating a rule intentionally applies it to past transactions.
            # Routine syncs only classify brand-new, unreviewed rows so a
            # later one-off user correction is never overwritten.
            if not include_reviewed:
                conditions.append(TransactionModel.reviewed_at.is_(None))
            if rule.budget_category_id is not None:
                conditions.append(TransactionModel.budget_category_id.is_(None) | TransactionModel.reviewed_at.is_(None))
                eligible_type = TransactionModel.type.in_(("expense", "transfer"))
                values = {
                    "budget_category_id": rule.budget_category_id,
                    "type": case((eligible_type, TransactionModel.type), else_="expense"),
                    "user_type_override": case(
                        (TransactionModel.type == "transfer", TransactionModel.user_type_override), else_="expense"
                    ),
                    "reviewed_at": datetime.now(timezone.utc),
                }
            else:
                values = {
                    "type": rule.transaction_type,
                    "budget_category_id": None,
                    "ignored_from_budget": False,
                    "reviewed_at": datetime.now(timezone.utc),
                }
            result = await self.session.execute(
                update(TransactionModel)
                .where(*conditions)
                .values(**values)
            )
            updated_count += result.rowcount or 0
        await self.session.flush()
        return updated_count

    async def apply_category_defaults_for_user(self, user_id: UUID) -> int:
        from app.domain.category_mapping import match_existing_category
        from app.persistence.models import AccountModel

        # Explicit merchant choices take precedence over provider defaults.
        await self.apply_merchant_rules_for_user(user_id)
        categories = [(row.id, row.name) for row in await self.list_categories(user_id) if row.active]
        if not categories:
            return 0
        rows = (await self.session.execute(
            select(TransactionModel).join(AccountModel, AccountModel.id == TransactionModel.account_id)
            .where(AccountModel.user_id == user_id, AccountModel.archived_at.is_(None),
                   TransactionModel.deleted_at.is_(None), TransactionModel.type == "expense",
                   TransactionModel.budget_category_id.is_(None), TransactionModel.reviewed_at.is_(None),
                   TransactionModel.ignored_from_budget.is_(False))
        )).scalars().all()
        count = 0
        for row in rows:
            category_id = match_existing_category(row.category, categories)
            if category_id is not None:
                row.budget_category_id = category_id
                count += 1
        await self.session.flush()
        return count

    async def delete_rule(self, user_id: UUID, rule_id: UUID) -> None:
        result = await self.session.execute(
            select(MerchantBudgetRuleModel).where(MerchantBudgetRuleModel.id == rule_id, MerchantBudgetRuleModel.user_id == user_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise NotFoundError("Merchant rule", str(rule_id))
        await self.session.delete(row)
        await self.session.flush()

    async def delete_category(self, user_id: UUID, category_id: UUID) -> None:
        row = await self.get_category_for_user(user_id, category_id)
        await self.session.delete(row)
        await self.session.flush()

    async def expense_transactions_for_month(self, user_id: UUID, start: date, end: date) -> list[TransactionModel]:
        from app.persistence.models import AccountModel

        result = await self.session.execute(
            select(TransactionModel)
            .join(AccountModel, AccountModel.id == TransactionModel.account_id)
            .where(
                AccountModel.user_id == user_id,
                AccountModel.archived_at.is_(None),
                TransactionModel.posted_at >= start,
                TransactionModel.posted_at <= end,
                TransactionModel.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())

    async def history_start(self, user_id: UUID) -> date | None:
        from app.persistence.models import AccountModel
        return await self.session.scalar(select(func.min(TransactionModel.posted_at))
            .join(AccountModel, AccountModel.id == TransactionModel.account_id)
            .where(AccountModel.user_id == user_id, AccountModel.archived_at.is_(None),
                   TransactionModel.deleted_at.is_(None)))

    async def unreviewed_transactions(self, user_id: UUID) -> list[TransactionModel]:
        from app.persistence.models import AccountModel

        result = await self.session.execute(
            select(TransactionModel)
            .join(AccountModel, AccountModel.id == TransactionModel.account_id)
            .where(
                AccountModel.user_id == user_id,
                AccountModel.archived_at.is_(None),
                TransactionModel.reviewed_at.is_(None),
                TransactionModel.deleted_at.is_(None),
            )
            .order_by(TransactionModel.posted_at.desc(), TransactionModel.id.desc())
        )
        return list(result.scalars().all())
