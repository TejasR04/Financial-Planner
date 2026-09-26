from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.domain.entities import Account, Transaction
from app.domain.enums import (
    AccountType,
    RecommendationEffort,
    RecommendationStatus,
    TransactionStatus,
    TransactionType,
)
from app.persistence.repositories.account_repository import AccountRepository
from app.persistence.repositories.budget_repository import BudgetRepository
from app.persistence.repositories.holding_repository import HoldingRepository
from app.persistence.repositories.investment_value_snapshot_repository import (
    InvestmentValueSnapshotRepository,
)
from app.persistence.repositories.liability_repository import LiabilityRepository
from app.persistence.repositories.recommendation_repository import RecommendationRepository
from app.persistence.repositories.transaction_repository import TransactionRepository
from app.persistence.repositories.transaction_repository import import_fingerprints
from app.services.recommendation_engine import RecommendationDraft


def _sql(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))


def _empty_result():
    return SimpleNamespace(
        scalars=lambda: SimpleNamespace(all=lambda: []),
        all=lambda: [],
    )


@pytest.mark.asyncio
async def test_provider_defaults_assign_categories_without_approving_transactions():
    user_id, dining_id, shopping_id = uuid4(), uuid4(), uuid4()
    rows = [
        SimpleNamespace(category="FOOD_AND_DRINK_RESTAURANT", budget_category_id=None, reviewed_at=None),
        SimpleNamespace(category="GENERAL_MERCHANDISE_SUPERSTORES", budget_category_id=None, reviewed_at=None),
    ]
    session = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: rows))),
        flush=AsyncMock(),
    )
    repo = BudgetRepository(session)
    repo.apply_merchant_rules_for_user = AsyncMock(return_value=0)
    repo.list_categories = AsyncMock(return_value=[
        SimpleNamespace(id=dining_id, name="Drinks & Dining", active=True),
        SimpleNamespace(id=shopping_id, name="Shopping", active=True),
        SimpleNamespace(id=uuid4(), name="Restaurants", active=False),
    ])

    assert await repo.apply_category_defaults_for_user(user_id) == 2
    assert [row.budget_category_id for row in rows] == [dining_id, shopping_id]
    assert all(row.reviewed_at is None for row in rows)
    repo.apply_merchant_rules_for_user.assert_awaited_once_with(user_id)

    # Repair only this user's active, unassigned, unreviewed expenses. Existing
    # choices, approvals, ignored transactions, and other users stay untouched.
    statement = session.execute.await_args.args[0]
    sql = _sql(statement)
    for condition in [
        "accounts.user_id", "accounts.archived_at IS NULL", "transactions.deleted_at IS NULL",
        "transactions.budget_category_id IS NULL", "transactions.reviewed_at IS NULL",
        "transactions.ignored_from_budget IS false", "transactions.type =",
    ]:
        assert condition in sql
    assert user_id in statement.compile().params.values()
    assert "expense" in statement.compile().params.values()

    assert await repo.unreviewed_transactions(user_id) == rows
    review_sql = _sql(session.execute.await_args.args[0])
    assert "transactions.reviewed_at IS NULL" in review_sql
    assert "transactions.budget_category_id IS NULL" not in review_sql


@pytest.mark.asyncio
async def test_filtered_totals_share_scope_and_are_not_paginated():
    session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(one=lambda: (Decimal("25"), Decimal("100")))))
    totals = await TransactionRepository(session).totals_for_user(
        uuid4(), account_id=uuid4(), budget_category_id=uuid4(), since=date(2026, 9, 1),
        until=date(2026, 9, 30), transaction_type="expense", cash_flow_only=False)
    assert totals == {"income": Decimal("25"), "spending": Decimal("100"), "net_cash_flow": Decimal("-75")}
    sql = _sql(session.execute.await_args.args[0])
    for required in ["accounts.user_id", "accounts.archived_at IS NULL", "transactions.deleted_at IS NULL", "transactions.budget_category_id", "transactions.type", "transactions.posted_at >=", "transactions.posted_at <="]:
        assert required in sql
    assert "LIMIT" not in sql and "OFFSET" not in sql
    params = session.execute.await_args.args[0].compile().params
    assert ["income", "expense"] in params.values()
    assert "LOAN_PAYMENTS_CREDIT_CARD_PAYMENT" in params.values()


@pytest.mark.asyncio
@pytest.mark.parametrize("amount", ["-500", "100"])
async def test_categorized_transfers_preserve_type_and_exclusion(monkeypatch, amount):
    category_id = uuid4()
    row = SimpleNamespace(type="transfer", amount=Decimal(amount), category="Transfer", merchant="Travel", ignored_from_budget=False)
    session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: row)), flush=AsyncMock())
    monkeypatch.setattr("app.persistence.repositories.transaction_repository._to_domain", lambda value: value)
    result = await TransactionRepository(session).update_budget_category(uuid4(), uuid4(), category_id)
    assert result.budget_category_id == category_id
    assert result.type == "transfer"
    assert result.ignored_from_budget is False


@pytest.mark.asyncio
async def test_income_cannot_silently_become_budget_spending():
    from app.core.exceptions import ValidationError
    row = SimpleNamespace(type="income", amount=Decimal("100"), category="Income", merchant="Salary")
    session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: row)))
    with pytest.raises(ValidationError, match="Budget categories apply"):
        await TransactionRepository(session).update_budget_category(uuid4(), uuid4(), uuid4())


@pytest.mark.asyncio
async def test_category_merchant_rule_classifies_incompatible_transactions_as_expenses():
    category_id = uuid4()
    session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(rowcount=1)), flush=AsyncMock())
    repo = BudgetRepository(session)
    repo.list_rules = AsyncMock(return_value=[(
        SimpleNamespace(merchant_pattern="Cafe", budget_category_id=category_id),
        SimpleNamespace(active=True),
    )])

    assert await repo.apply_merchant_rules_for_user(uuid4()) == 1
    sql = _sql(session.execute.await_args.args[0])
    assert "CASE WHEN" in sql
    assert "transactions.type IN" in sql
    assert "user_type_override" in sql
    assert "budget_category_id" in sql
    assert "expense" in session.execute.await_args.args[0].compile().params.values()


@pytest.mark.asyncio
@pytest.mark.parametrize("repository_type", [HoldingRepository, LiabilityRepository])
async def test_active_child_queries_exclude_archived_accounts(repository_type):
    session = SimpleNamespace(execute=AsyncMock(return_value=_empty_result()))

    assert await repository_type(session).list_for_user(uuid4()) == []

    statement = session.execute.await_args.args[0]
    assert "accounts.archived_at IS NULL" in _sql(statement)


@pytest.mark.asyncio
async def test_unlink_detaches_already_archived_accounts_too():
    session = SimpleNamespace(execute=AsyncMock(), flush=AsyncMock())

    await AccountRepository(session).archive_and_detach_institution(uuid4(), uuid4())

    statement = session.execute.await_args.args[0]
    sql = _sql(statement)
    assert "accounts.archived_at IS NULL" not in sql.split("WHERE", 1)[1]
    assert {column.key for column in statement._values} == {"archived_at", "institution_id"}


@pytest.mark.asyncio
async def test_linked_account_rename_sets_local_name_only():
    provider_name = "Investment Account"
    row = SimpleNamespace(
        id=uuid4(), user_id=uuid4(), institution_id=uuid4(),
        name=provider_name, custom_name=None, type=AccountType.INVESTMENT.value,
        balance=Decimal("100"), currency="USD", mask="1234", apy=None,
        status="connected", updated_at=None, external_account_id="plaid-account",
        archived_at=None,
    )
    session = SimpleNamespace(flush=AsyncMock())
    repository = AccountRepository(session)
    repository._row_for_user = AsyncMock(return_value=row)

    renamed = await repository.rename_for_user(row.user_id, row.id, "Roth IRA")

    assert row.name == provider_name
    assert row.custom_name == "Roth IRA"
    assert renamed.name == "Roth IRA"


@pytest.mark.asyncio
async def test_recommendation_refresh_reuses_stable_row_and_updates_estimate():
    user_id, recommendation_id = uuid4(), uuid4()
    row = SimpleNamespace(
        id=recommendation_id,
        user_id=user_id,
        title="Move excess cash",
        body="Old estimate",
        category="Cash Management",
        impact_value=Decimal("10"),
        effort=RecommendationEffort.LOW.value,
        confidence=Decimal("0.7"),
        status=RecommendationStatus.NEW.value,
        generated_at=datetime.now(UTC),
    )
    session = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [row]))),
        add=Mock(),
        flush=AsyncMock(),
    )
    draft = RecommendationDraft(
        title="Move excess cash",
        body="Updated estimate",
        category="Cash Management",
        impact_value=Decimal("25"),
        effort=RecommendationEffort.MEDIUM,
        confidence=0.9,
    )

    refreshed = await RecommendationRepository(session).save_drafts(user_id, [draft])

    assert [item.id for item in refreshed] == [recommendation_id]
    assert row.body == "Updated estimate"
    assert row.impact_value == Decimal("25")
    assert row.effort == RecommendationEffort.MEDIUM.value
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_recommendation_refresh_does_not_resurrect_dismissed_rule():
    user_id = uuid4()
    row = SimpleNamespace(
        id=uuid4(),
        user_id=user_id,
        title="Move excess cash",
        body="Already considered",
        category="Cash Management",
        impact_value=Decimal("10"),
        effort=RecommendationEffort.LOW.value,
        confidence=Decimal("0.8"),
        status=RecommendationStatus.DISMISSED.value,
        generated_at=datetime.now(UTC),
    )
    session = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [row]))),
        add=Mock(),
        flush=AsyncMock(),
    )
    draft = RecommendationDraft(
        title=" move excess cash ",
        body="New wording",
        category="cash management",
        impact_value=Decimal("40"),
        effort=RecommendationEffort.LOW,
        confidence=0.9,
    )

    assert await RecommendationRepository(session).save_drafts(user_id, [draft]) == []
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_complete_history_query_has_no_hidden_limit():
    session = SimpleNamespace(execute=AsyncMock(return_value=_empty_result()))

    assert await TransactionRepository(session).list_since_for_income_expense(
        uuid4(), date(2025, 1, 1)
    ) == []

    statement = session.execute.await_args.args[0]
    assert "LIMIT" not in _sql(statement).upper()


@pytest.mark.asyncio
async def test_monthly_budget_excludes_transactions_from_archived_accounts():
    session = SimpleNamespace(execute=AsyncMock(return_value=_empty_result()))

    assert await BudgetRepository(session).expense_transactions_for_month(
        uuid4(), date(2026, 8, 1), date(2026, 8, 31)
    ) == []

    statement = session.execute.await_args.args[0]
    assert "accounts.archived_at IS NULL" in _sql(statement)


@pytest.mark.asyncio
async def test_paginated_transaction_order_has_stable_id_tiebreaker():
    count_result = SimpleNamespace(scalar_one=lambda: 0)
    rows_result = _empty_result()
    session = SimpleNamespace(
        execute=AsyncMock(side_effect=[count_result, rows_result])
    )

    rows, total = await TransactionRepository(session).list_for_user(uuid4())

    assert rows == []
    assert total == 0
    sql = _sql(session.execute.await_args_list[1].args[0])
    assert "transactions.posted_at DESC, transactions.id DESC" in sql


@pytest.mark.asyncio
async def test_transaction_filters_support_budget_category_and_merchant():
    count_result = SimpleNamespace(scalar_one=lambda: 0)
    session = SimpleNamespace(execute=AsyncMock(side_effect=[count_result, _empty_result()]))
    category_id = uuid4()

    await TransactionRepository(session).list_for_user(
        uuid4(), budget_category_id=category_id, merchant="Corner Market"
    )

    sql = _sql(session.execute.await_args_list[1].args[0])
    assert "transactions.budget_category_id" in sql
    assert "lower(transactions.merchant)" in sql


@pytest.mark.asyncio
async def test_transaction_totals_are_aggregated_in_sql():
    result = SimpleNamespace(all=lambda: [("income", Decimal("25.00"))])
    session = SimpleNamespace(execute=AsyncMock(return_value=result))

    totals = await TransactionRepository(session).totals_by_type_since(
        uuid4(), date(2025, 1, 1), absolute=True
    )

    assert totals == {TransactionType.INCOME: Decimal("25.00")}
    assert "sum(abs(transactions.amount))" in _sql(session.execute.await_args.args[0])


@pytest.mark.asyncio
async def test_plaid_update_prefetches_existing_and_import_candidates_once():
    existing = SimpleNamespace(
        external_transaction_id="existing",
        account_id=uuid4(),
        posted_at=date(2025, 1, 1),
        merchant="Old",
        category="Old",
        amount=Decimal("1"),
        type=TransactionType.EXPENSE.value,
        status=TransactionStatus.CLEARED.value,
    )
    result = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [existing]))
    session = SimpleNamespace(execute=AsyncMock(return_value=result), add=Mock(), flush=AsyncMock())
    account_id = uuid4()
    transactions = [
        Transaction(
            id=uuid4(),
            account_id=account_id,
            posted_at=date(2025, 2, index),
            merchant=f"Merchant {index}",
            category="Category",
            amount=Decimal("-1"),
            type=TransactionType.EXPENSE,
            status=TransactionStatus.CLEARED,
            external_transaction_id=external_id,
        )
        for index, external_id in [(1, "existing"), (2, "new")]
    ]

    counts = await TransactionRepository(session).apply_plaid_updates(transactions, [])

    assert counts == (1, 1, 0)
    assert session.execute.await_count == 2


@pytest.mark.asyncio
async def test_plaid_update_reconciles_a_nearby_csv_import():
    account_id = uuid4()
    imported = SimpleNamespace(
        external_transaction_id=None,
        import_fingerprint="fingerprint",
        deleted_at=None,
        account_id=account_id,
        posted_at=date(2026, 8, 1),
        merchant="US Dept Education",
        category="uncategorized",
        amount=Decimal("-200.00"),
        type=TransactionType.EXPENSE.value,
        status=TransactionStatus.CLEARED.value,
    )
    empty = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))
    candidates = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [imported]))
    session = SimpleNamespace(
        execute=AsyncMock(side_effect=[empty, candidates]), add=Mock(), flush=AsyncMock()
    )
    synced = Transaction(
        id=uuid4(), account_id=account_id, posted_at=date(2026, 8, 3),
        merchant="Dept Education - Loan", category="loan_payments",
        amount=Decimal("-200.00"), type=TransactionType.EXPENSE,
        status=TransactionStatus.CLEARED, external_transaction_id="plaid-123",
    )

    assert await TransactionRepository(session).apply_plaid_updates([synced], []) == (0, 1, 0)
    assert imported.external_transaction_id == "plaid-123"


@pytest.mark.asyncio
async def test_plaid_attach_preserves_explicit_csv_category_override():
    account_id = uuid4()
    imported = SimpleNamespace(
        external_transaction_id=None, import_fingerprint="fingerprint", deleted_at=None,
        account_id=account_id, posted_at=date(2026, 8, 1), merchant="Acme Loan",
        category="My loan payment", amount=Decimal("-200"), type="expense", status="cleared",
        reviewed_at=None, user_category_override="My loan payment", user_type_override=None,
    )
    empty = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))
    candidates = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [imported]))
    session = SimpleNamespace(execute=AsyncMock(side_effect=[empty, candidates]), add=Mock(), flush=AsyncMock())
    synced = Transaction(
        id=uuid4(), account_id=account_id, posted_at=date(2026, 8, 1), merchant="Acme Loan",
        category="provider loans", amount=Decimal("-200"), type=TransactionType.EXPENSE,
        status=TransactionStatus.CLEARED, external_transaction_id="plaid-category",
    )
    await TransactionRepository(session).apply_plaid_updates([synced], [])
    assert imported.provider_category == "provider loans"
    assert imported.category == "My loan payment"


def test_csv_import_identity_preserves_identical_occurrences_and_replays_stably():
    account_id = uuid4()
    transaction = Transaction(
        id=uuid4(), account_id=account_id, posted_at=date(2026, 9, 14), merchant="Coffee Shop",
        category="Dining", amount=Decimal("-5"), type=TransactionType.EXPENSE,
        status=TransactionStatus.CLEARED,
    )
    identities = import_fingerprints([transaction, transaction])
    assert identities[0] != identities[1]
    assert identities == import_fingerprints([transaction, transaction])


@pytest.mark.asyncio
async def test_csv_replay_can_fill_an_identical_occurrence_previously_excluded():
    account_id = uuid4()
    transaction = Transaction(
        id=uuid4(), account_id=account_id, posted_at=date(2026, 9, 14), merchant="Coffee Shop",
        category="Dining", amount=Decimal("-5"), type=TransactionType.EXPENSE,
        status=TransactionStatus.CLEARED,
    )
    second_identity = import_fingerprints([transaction], [3])[0]
    existing = SimpleNamespace(
        account_id=account_id, posted_at=transaction.posted_at, merchant=transaction.merchant,
        amount=transaction.amount, import_fingerprint=second_identity,
    )
    result = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [existing]))
    session = SimpleNamespace(execute=AsyncMock(return_value=result))

    flags = await TransactionRepository(session).import_duplicate_flags(
        [transaction, transaction], [2, 3]
    )

    assert flags == [False, True]


@pytest.mark.asyncio
async def test_csv_known_identity_does_not_disable_fuzzy_warning_for_another_date():
    account_id = uuid4()
    first = Transaction(
        id=uuid4(), account_id=account_id, posted_at=date(2026, 9, 14), merchant="Coffee Shop",
        category="Dining", amount=Decimal("-5"), type=TransactionType.EXPENSE,
        status=TransactionStatus.CLEARED,
    )
    next_day = Transaction(
        id=uuid4(), account_id=account_id, posted_at=date(2026, 9, 15), merchant="Coffee Shop",
        category="Dining", amount=Decimal("-5"), type=TransactionType.EXPENSE,
        status=TransactionStatus.CLEARED,
    )
    existing = SimpleNamespace(
        account_id=account_id, posted_at=first.posted_at, merchant=first.merchant,
        amount=first.amount, import_fingerprint=import_fingerprints([first], [2])[0],
    )
    result = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [existing]))
    session = SimpleNamespace(execute=AsyncMock(return_value=result))
    assert await TransactionRepository(session).import_duplicate_flags([first, next_day], [2, 3]) == [True, True]


@pytest.mark.asyncio
async def test_csv_replay_recognizes_legacy_physical_line_fingerprints_after_shift():
    account_id = uuid4()
    transaction = Transaction(
        id=uuid4(), account_id=account_id, posted_at=date(2026, 9, 14), merchant="Coffee Shop",
        category="Dining", amount=Decimal("-5"), type=TransactionType.EXPENSE,
        status=TransactionStatus.CLEARED,
    )
    base_identity = import_fingerprints([transaction])[0].split(":", 1)[0]
    legacy_row = SimpleNamespace(
        account_id=account_id, posted_at=transaction.posted_at, merchant=transaction.merchant,
        amount=transaction.amount, import_fingerprint=f"{base_identity}:2", deleted_at=None,
    )
    result = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [legacy_row]))

    preview_session = SimpleNamespace(execute=AsyncMock(return_value=result))
    assert await TransactionRepository(preview_session).import_duplicate_flags([transaction], [1]) == [True]

    import_session = SimpleNamespace(execute=AsyncMock(return_value=result), flush=AsyncMock())
    created, skipped = await TransactionRepository(import_session).bulk_create_deduplicated(
        [transaction], force_import=[False], identity_numbers=[1]
    )
    assert created == []
    assert skipped == 1


@pytest.mark.asyncio
async def test_forced_identical_csv_occurrence_allocates_next_stable_identity():
    account_id = uuid4()
    transaction = Transaction(
        id=uuid4(), account_id=account_id, posted_at=date(2026, 9, 14), merchant="Coffee Shop",
        category="Dining", amount=Decimal("-5"), type=TransactionType.EXPENSE,
        status=TransactionStatus.CLEARED,
    )
    existing = SimpleNamespace(
        account_id=account_id, posted_at=transaction.posted_at, merchant=transaction.merchant,
        amount=transaction.amount, import_fingerprint=import_fingerprints([transaction])[0], deleted_at=None,
    )
    existing_result = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [existing]))
    insert_result = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))
    session = SimpleNamespace(
        execute=AsyncMock(side_effect=[existing_result, insert_result]), flush=AsyncMock()
    )

    await TransactionRepository(session).bulk_create_deduplicated(
        [transaction], force_import=[True], identity_numbers=[1]
    )

    insert_statement = session.execute.await_args_list[1].args[0]
    params = insert_statement.compile(dialect=postgresql.dialect()).params
    assert any(isinstance(value, str) and value.endswith(":occurrence:2") for value in params.values())


@pytest.mark.asyncio
async def test_plaid_sync_preserves_reviewed_user_classification():
    account_id = uuid4()
    row = SimpleNamespace(
        external_transaction_id="plaid-1", account_id=account_id, posted_at=date(2026, 9, 1),
        merchant="Bank payment", category="custom", amount=Decimal("-50"), type="transfer",
        status="cleared", user_category_override="custom", user_type_override="transfer",
    )
    existing = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [row]))
    no_candidates = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))
    session = SimpleNamespace(execute=AsyncMock(side_effect=[existing, no_candidates]), add=Mock(), flush=AsyncMock())
    incoming = Transaction(
        id=uuid4(), account_id=account_id, posted_at=date(2026, 9, 2), merchant="Bank payment",
        category="provider expense", amount=Decimal("-50"), type=TransactionType.EXPENSE,
        status=TransactionStatus.CLEARED, external_transaction_id="plaid-1",
    )
    await TransactionRepository(session).apply_plaid_updates([incoming], [])
    assert row.provider_category == "provider expense"
    assert row.category == "custom"
    assert row.type == "transfer"
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_daily_snapshots_prefetch_existing_rows_once():
    session = SimpleNamespace(execute=AsyncMock(return_value=_empty_result()), add=Mock(), flush=AsyncMock())
    accounts = [
        Account(
            id=uuid4(),
            user_id=uuid4(),
            name=f"Investment {index}",
            type=AccountType.INVESTMENT,
            balance=Decimal("100"),
        )
        for index in range(3)
    ]

    await InvestmentValueSnapshotRepository(session).record_for_accounts(accounts)

    assert session.execute.await_count == 1
    assert session.add.call_count == 3


@pytest.mark.asyncio
async def test_investment_history_carries_manual_balances_across_plaid_sync_dates():
    plaid_id, manual_401k_id, manual_hsa_id = uuid4(), uuid4(), uuid4()
    rows = [
        (plaid_id, date(2026, 9, 1), Decimal("10000")),
        (plaid_id, date(2026, 9, 2), Decimal("10100")),
        (manual_401k_id, date(2026, 9, 2), Decimal("50000")),
        (manual_hsa_id, date(2026, 9, 2), Decimal("3000")),
        (plaid_id, date(2026, 9, 3), Decimal("10200")),
        (manual_hsa_id, date(2026, 9, 4), Decimal("3100")),
        (plaid_id, date(2026, 9, 5), Decimal("10300")),
    ]
    result = SimpleNamespace(all=lambda: rows)
    session = SimpleNamespace(execute=AsyncMock(return_value=result))

    totals = await InvestmentValueSnapshotRepository(session).daily_totals_for_user(uuid4())

    assert totals == [
        (date(2026, 9, 1), Decimal("10000")),
        (date(2026, 9, 2), Decimal("63100")),
        (date(2026, 9, 3), Decimal("63200")),
        (date(2026, 9, 4), Decimal("63300")),
        (date(2026, 9, 5), Decimal("63400")),
    ]
