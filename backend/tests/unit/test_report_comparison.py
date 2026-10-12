from app.domain.report_comparison import compare_collection, compare_report_states


def test_collection_comparison_reports_add_remove_and_financial_delta() -> None:
    changes = compare_collection(
        [{"id": "a", "balance": "100.00"}, {"id": "b", "balance": "5.00"}],
        [{"id": "a", "balance": "125.00"}, {"id": "c", "balance": "1.00"}],
        key="id",
        fields=("balance",),
    )
    assert changes == [
        {"operation": "updated", "id": "a", "fields": {"balance": {"before": "100.00", "after": "125.00"}}},
        {"operation": "removed", "id": "b", "before": {"id": "b", "balance": "5.00"}},
        {"operation": "added", "id": "c", "after": {"id": "c", "balance": "1.00"}},
    ]


def test_report_comparison_detects_budget_threshold_crossing_and_value_changes() -> None:
    previous = {
        "summary": {"assets": "1000.00", "liabilities": "200.00", "net_worth": "800.00"},
        "accounts": [{"id": "cash", "balance": "800.00"}],
        "investments": {
            "account_value": "500.00", "holdings_value": "400.00",
            "holdings": [{"id": "holding", "quantity": "5", "market_value": "400.00"}],
        },
        "budgets": {"month": "2026-10-01", "categories": [{
            "id": "food", "name": "Food", "monthly_limit": "100.00", "spent": "70.00", "pending": "0.00",
        }]},
    }
    current = {
        "summary": {"assets": "1100.00", "liabilities": "250.00", "net_worth": "850.00"},
        "accounts": [{"id": "cash", "balance": "850.00"}],
        "investments": {
            "account_value": "550.00", "holdings_value": "500.00",
            "holdings": [{"id": "holding", "quantity": "6", "market_value": "500.00"}],
        },
        "budgets": {"month": "2026-10-01", "categories": [{
            "id": "food", "name": "Food", "monthly_limit": "100.00", "spent": "82.00", "pending": "20.00",
        }]},
    }
    changes = compare_report_states(previous, current, [{"id": "event-1", "entity_type": "transactions"}])
    assert changes["accounts"][0]["fields"]["balance"]["change"] == "50.00"
    assert changes["summary_totals"]["assets"]["change"] == "100.00"
    assert changes["summary_totals"]["liabilities"]["change"] == "50.00"
    assert changes["summary_totals"]["net_worth"]["change"] == "50.00"
    assert changes["investments"][0]["fields"]["quantity"]["change"] == "1"
    assert changes["investments"][0]["fields"]["market_value"]["change"] == "100.00"
    assert changes["investment_totals"]["account_value"]["change"] == "50.00"
    assert changes["investment_totals"]["holdings_value"]["change"] == "100.00"
    assert changes["budget_thresholds_crossed"] == [{
        "category_id": "food", "category_name": "Food", "threshold": "80%", "utilization": "102.00",
    }, {
        "category_id": "food", "category_name": "Food", "threshold": "100%", "utilization": "102.00",
    }]
    assert changes["transactions"] == [{"id": "event-1", "entity_type": "transactions"}]


def test_first_report_is_an_explicit_baseline() -> None:
    result = compare_report_states(None, {"accounts": [], "investments": {}, "budgets": {"categories": []}})
    assert result == {
        "baseline": True, "accounts": [], "investments": [], "summary_totals": {},
        "investment_totals": {}, "budgets": [],
        "liabilities": [], "income_sources": [], "transactions": [],
    }


def test_budget_spend_does_not_compare_across_month_boundaries() -> None:
    previous = {
        "budgets": {"month": "2026-09-01", "categories": [{
            "id": "food", "name": "Food", "group_name": "Needs", "monthly_limit": "100.00",
            "spent": "95.00", "pending": "10.00", "remaining": "0.00", "active": True,
        }]},
    }
    current = {
        "budgets": {"month": "2026-10-01", "categories": [{
            "id": "food", "name": "Food", "group_name": "Needs", "monthly_limit": "100.00",
            "spent": "2.00", "pending": "0.00", "remaining": "98.00", "active": True,
        }]},
    }
    changes = compare_report_states(previous, current)
    assert changes["budget_period_changed"] is True
    assert changes["budgets"] == []
    assert changes["budget_thresholds_crossed"] == []
