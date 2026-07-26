from calendar import monthrange
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.domain.entities import User
from app.persistence.repositories.budget_repository import BudgetRepository
from app.schemas.budget import (
    BudgetCategoryCreateRequest,
    BudgetCategoryResponse,
    BudgetCategorySummaryResponse,
    BudgetCategoryUpdateRequest,
    BudgetSummaryResponse,
    MerchantRuleCreateRequest,
    MerchantRuleResponse,
    UncategorizedTransactionResponse,
    UncategorizedSpendResponse,
)
from app.services.budget_service import BudgetCategoryInput, BudgetService, BudgetTransactionInput, MerchantRuleInput

router = APIRouter(prefix="/budgets", tags=["budgets"])
service = BudgetService()


def _category_response(row) -> BudgetCategoryResponse:
    return BudgetCategoryResponse(
        id=row.id, name=row.name, group_name=row.group_name, monthly_limit=row.monthly_limit,
        sort_order=row.sort_order, active=row.active,
    )


@router.get("/categories", response_model=list[BudgetCategoryResponse])
async def list_categories(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = await BudgetRepository(db).list_categories(current_user.id)
    return [_category_response(row) for row in rows]


@router.post("/categories", response_model=BudgetCategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    body: BudgetCategoryCreateRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    row = await BudgetRepository(db).create_category(current_user.id, body.name, body.group_name, body.monthly_limit)
    await db.commit()
    return _category_response(row)


@router.patch("/categories/{category_id}", response_model=BudgetCategoryResponse)
async def update_category(
    category_id: UUID, body: BudgetCategoryUpdateRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    row = await BudgetRepository(db).update_category(current_user.id, category_id, **body.model_dump(exclude_unset=True))
    await db.commit()
    return _category_response(row)


@router.get("/merchant-rules", response_model=list[MerchantRuleResponse])
async def list_merchant_rules(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = await BudgetRepository(db).list_rules(current_user.id)
    return [
        MerchantRuleResponse(
            id=rule.id, budget_category_id=rule.budget_category_id,
            budget_category_name=category.name, merchant_pattern=rule.merchant_pattern,
        )
        for rule, category in rows
    ]


@router.post("/merchant-rules", response_model=MerchantRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_merchant_rule(
    body: MerchantRuleCreateRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    repo = BudgetRepository(db)
    rule = await repo.create_rule(current_user.id, body.budget_category_id, body.merchant_pattern)
    category = await repo.get_category_for_user(current_user.id, rule.budget_category_id)
    await db.commit()
    return MerchantRuleResponse(
        id=rule.id, budget_category_id=rule.budget_category_id,
        budget_category_name=category.name, merchant_pattern=rule.merchant_pattern,
    )


@router.delete("/merchant-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_merchant_rule(
    rule_id: UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    await BudgetRepository(db).delete_rule(current_user.id, rule_id)
    await db.commit()


@router.get("/summary", response_model=BudgetSummaryResponse)
async def budget_summary(
    month: date | None = None, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    selected_month = (month or date.today()).replace(day=1)
    end = selected_month.replace(day=monthrange(selected_month.year, selected_month.month)[1])
    repo = BudgetRepository(db)
    categories = await repo.list_categories(current_user.id)
    rules = await repo.list_rules(current_user.id)
    transactions = await repo.expense_transactions_for_month(current_user.id, selected_month, end)
    rollups, uncategorized_spent, uncategorized_pending, uncategorized_count = service.summarize(
        [BudgetCategoryInput(row.id, row.name, row.group_name, row.monthly_limit, row.active) for row in categories],
        [MerchantRuleInput(rule.budget_category_id, rule.merchant_pattern) for rule, _ in rules],
        [BudgetTransactionInput(row.merchant, row.amount, row.status, row.budget_category_id) for row in transactions],
        selected_month,
    )
    return BudgetSummaryResponse(
        month=selected_month,
        categories=[
            BudgetCategorySummaryResponse(
                budget_category_id=rollup.budget_category_id,
                name=rollup.name,
                group_name=rollup.group_name,
                budgeted=rollup.budgeted,
                spent=rollup.spent,
                pending=rollup.pending,
                remaining=rollup.remaining,
                forecast=rollup.forecast,
            )
            for rollup in rollups
        ],
        uncategorized=UncategorizedSpendResponse(
            spent=uncategorized_spent, pending=uncategorized_pending, transaction_count=uncategorized_count,
        ),
    )


@router.get("/uncategorized", response_model=list[UncategorizedTransactionResponse])
async def uncategorized_transactions(
    month: date | None = None, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    selected_month = (month or date.today()).replace(day=1)
    end = selected_month.replace(day=monthrange(selected_month.year, selected_month.month)[1])
    repo = BudgetRepository(db)
    categories = await repo.list_categories(current_user.id)
    rules = await repo.list_rules(current_user.id)
    active_category_ids = {row.id for row in categories if row.active}
    rule_inputs = [MerchantRuleInput(rule.budget_category_id, rule.merchant_pattern) for rule, _ in rules]
    rows = await repo.expense_transactions_for_month(current_user.id, selected_month, end)
    result = []
    for row in rows:
        classification = service.classify_category_id(
            BudgetTransactionInput(row.merchant, row.amount, row.status, row.budget_category_id),
            rule_inputs,
            active_category_ids,
        )
        if classification is None:
            result.append(
                UncategorizedTransactionResponse(
                    id=row.id,
                    posted_at=row.posted_at,
                    merchant=row.merchant,
                    provider_category=row.category,
                    amount=row.amount,
                    status=row.status,
                )
            )
    return result
