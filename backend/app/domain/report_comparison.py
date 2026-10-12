"""Pure comparison helpers for immutable daily financial reports."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


def _amount(value: Any) -> Decimal:
    try:
        return Decimal(str(value or "0"))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _money(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")


def _amount_change(before: Any, after: Any) -> dict[str, str]:
    old_value = _amount(before)
    new_value = _amount(after)
    return {
        "before": str(before),
        "after": str(after),
        "change": _money(new_value - old_value),
    }


def compare_collection(
    previous: list[dict[str, Any]],
    current: list[dict[str, Any]],
    *,
    key: str,
    fields: tuple[str, ...],
) -> list[dict[str, Any]]:
    """Return additions, removals, and changed rows without mutating inputs."""
    old = {str(item[key]): item for item in previous if key in item}
    new = {str(item[key]): item for item in current if key in item}
    changes: list[dict[str, Any]] = []
    for item_id in sorted(old.keys() | new.keys()):
        before, after = old.get(item_id), new.get(item_id)
        if before is None:
            changes.append({"operation": "added", "id": item_id, "after": after})
            continue
        if after is None:
            changes.append({"operation": "removed", "id": item_id, "before": before})
            continue
        changed = {field: {"before": before.get(field), "after": after.get(field)}
                   for field in fields if before.get(field) != after.get(field)}
        if changed:
            changes.append({"operation": "updated", "id": item_id, "fields": changed})
    return changes


def compare_report_states(
    previous: dict[str, Any] | None,
    current: dict[str, Any],
    event_changes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compare current report data with its predecessor using stable IDs."""
    if previous is None:
        return {
            "baseline": True,
            "accounts": [],
            "investments": [],
            "summary_totals": {},
            "investment_totals": {},
            "budgets": [],
            "liabilities": [],
            "income_sources": [],
            "transactions": event_changes or [],
        }

    account_changes = compare_collection(
        previous.get("accounts", []), current.get("accounts", []), key="id",
        fields=("name", "type", "balance", "currency", "archived"),
    )
    for change in account_changes:
        fields = change.get("fields", {})
        if "balance" in fields:
            fields["balance"]["change"] = _money(
                _amount(fields["balance"]["after"]) - _amount(fields["balance"]["before"])
            )

    holding_changes = compare_collection(
        previous.get("investments", {}).get("holdings", []),
        current.get("investments", {}).get("holdings", []), key="id",
        fields=("account_id", "symbol", "quantity", "cost_basis", "market_value", "asset_class", "as_of"),
    )
    for change in holding_changes:
        fields = change.get("fields", {})
        if "market_value" in fields:
            fields["market_value"]["change"] = _money(
                _amount(fields["market_value"]["after"]) - _amount(fields["market_value"]["before"])
            )
        if "quantity" in fields:
            fields["quantity"]["change"] = format(
                _amount(fields["quantity"]["after"]) - _amount(fields["quantity"]["before"]), "f"
            )

    previous_budgets = previous.get("budgets", {})
    current_budgets = current.get("budgets", {})
    same_budget_month = previous_budgets.get("month") == current_budgets.get("month")
    budget_fields: tuple[str, ...] = ("name", "group_name", "monthly_limit", "active")
    if same_budget_month:
        budget_fields += ("spent", "pending", "remaining")
    budget_changes = compare_collection(
        previous_budgets.get("categories", []),
        current_budgets.get("categories", []), key="id",
        fields=budget_fields,
    )
    for change in budget_changes:
        fields = change.get("fields", {})
        limit = fields.get("monthly_limit")
        if limit:
            limit["change"] = _money(_amount(limit["after"]) - _amount(limit["before"]))

    liability_changes = compare_collection(
        previous.get("liability_details", []), current.get("liability_details", []), key="account_id",
        fields=("principal", "interest_rate", "term_months", "minimum_payment", "origination_date"),
    )
    income_changes = compare_collection(
        previous.get("income_sources", []), current.get("income_sources", []), key="id",
        fields=("name", "annual_amount", "growth_rate", "type", "active"),
    )

    thresholds = _budget_threshold_crossings(
        previous_budgets.get("categories", []), current_budgets.get("categories", [])
    ) if same_budget_month else []

    previous_summary = previous.get("summary", {})
    current_summary = current.get("summary", {})
    summary_totals = {
        key: _amount_change(previous_summary.get(key, "0.00"), current_summary.get(key, "0.00"))
        for key in ("assets", "liabilities", "net_worth")
    }
    previous_investments = previous.get("investments", {})
    current_investments = current.get("investments", {})
    investment_totals = {
        key: _amount_change(previous_investments.get(key, "0.00"), current_investments.get(key, "0.00"))
        for key in ("account_value", "holdings_value")
    }
    return {
        "baseline": False,
        "summary_totals": summary_totals,
        "accounts": account_changes,
        "investments": holding_changes,
        "investment_totals": investment_totals,
        "budgets": budget_changes,
        "budget_period_changed": not same_budget_month,
        "liabilities": liability_changes,
        "income_sources": income_changes,
        "budget_thresholds_crossed": thresholds,
        "transactions": event_changes or [],
    }


def _budget_threshold_crossings(previous: list[dict[str, Any]], current: list[dict[str, Any]]) -> list[dict[str, str]]:
    old = {str(item["id"]): item for item in previous}
    crossed: list[dict[str, str]] = []
    for category in current:
        before = old.get(str(category.get("id")))
        if before is None:
            continue
        limit = _amount(category.get("monthly_limit"))
        if limit <= 0:
            continue
        previous_limit = _amount(before.get("monthly_limit"))
        old_utilization = (
            (_amount(before.get("spent")) + _amount(before.get("pending"))) / previous_limit
            if previous_limit > 0 else Decimal("0")
        )
        new_utilization = (_amount(category.get("spent")) + _amount(category.get("pending"))) / limit
        for threshold in (Decimal("0.8"), Decimal("1")):
            if old_utilization < threshold <= new_utilization:
                crossed.append({
                    "category_id": str(category["id"]),
                    "category_name": str(category.get("name", "")),
                    "threshold": "80%" if threshold == Decimal("0.8") else "100%",
                    "utilization": format(new_utilization * 100, ".2f"),
                })
    return crossed

