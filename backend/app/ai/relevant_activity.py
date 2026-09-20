"""Select transaction and budget facts explicitly requested in an AI question."""
from __future__ import annotations

import re
from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.merchant_rules import normalize_merchant_rule
from app.domain.category_mapping import ALIASES, normalized as normalize_category
from app.persistence.repositories.budget_repository import BudgetRepository
from app.persistence.repositories.transaction_repository import TransactionRepository
from app.services.activity_history import shift_month

_MONTHS = {
    name: number for number, name in enumerate(
        ("january", "february", "march", "april", "may", "june",
         "july", "august", "september", "october", "november", "december"),
        1,
    )
}
_DETAIL_WORDS = re.compile(r"\b(transaction|transactions|purchase|purchases|charge|charges|deposit|deposits|show|list|which)\b")
_BROAD_DETAIL_REQUEST = re.compile(
    r"(?:\b(?:my|show|list|recent|latest|all)\b.{0,30}\b(?:transactions?|purchases?|charges?|deposits?)\b)"
    r"|(?:\b(?:transactions?|purchases?|charges?|deposits?)\b.{0,20}\b(?:recent|latest|last|this)\b)"
)
_BUDGET_WORDS = re.compile(r"\b(budget|category|categories|spent|spend|spending)\b")
_GENERIC_MERCHANT_WORDS = {
    "payment", "purchase", "online", "transfer", "transaction", "debit", "credit",
    "card", "store", "market", "shop", "pending", "deposit", "withdrawal",
    "from", "with", "into", "the", "and", "for", "your", "inc", "llc", "corp",
    "company",
}


@dataclass
class _CategoryTotals:
    spent: Decimal = Decimal("0")
    pending: Decimal = Decimal("0")
    transactions: int = 0


def _money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))


def _month_end(value: date) -> date:
    return value.replace(day=monthrange(value.year, value.month)[1])


def _requested_period(message: str, reference: date) -> tuple[date, date, str] | None:
    lowered = message.lower()
    current = reference.replace(day=1)
    if "last month" in lowered:
        start = shift_month(current, -1)
        return start, _month_end(start), "last month"
    if "this month" in lowered or "month to date" in lowered or "mtd" in lowered:
        return current, reference, "this month to date"
    if "last year" in lowered:
        return date(reference.year - 1, 1, 1), date(reference.year - 1, 12, 31), "last year"
    if "this year" in lowered or "year to date" in lowered or "ytd" in lowered:
        return date(reference.year, 1, 1), reference, "this year to date"

    match = re.search(r"\blast\s+(\d{1,2})\s+months?\b", lowered)
    if match:
        count = min(24, max(1, int(match.group(1))))
        start = shift_month(current, -(count - 1))
        return start, reference, f"last {count} months"

    match = re.search(r"\b(20\d{2})-(0[1-9]|1[0-2])\b", lowered)
    if match:
        start = date(int(match.group(1)), int(match.group(2)), 1)
        return start, _month_end(start), match.group(0)

    for name, number in _MONTHS.items():
        if not re.search(rf"\b{name}\b", lowered):
            continue
        year_match = re.search(rf"\b{name}\s+(20\d{{2}})\b", lowered)
        year = int(year_match.group(1)) if year_match else reference.year
        if not year_match and number > reference.month:
            year -= 1
        start = date(year, number, 1)
        return start, _month_end(start), f"{name.title()} {year}"
    return None


def _mentioned_amounts(message: str) -> set[Decimal]:
    values: set[Decimal] = set()
    amount_pattern = re.compile(
        r"(?:\$\s*\d{1,7}(?:,\d{3})*(?:\.\d{1,2})?)"
        r"|(?:\b\d{1,7}(?:,\d{3})*\.\d{1,2}\b)"
        r"|(?:\b\d{1,7}(?:,\d{3})*(?:\.\d{1,2})?\s+(?:dollars?|bucks?)\b)",
        re.IGNORECASE,
    )
    for matched in amount_pattern.findall(message):
        raw = re.sub(r"(?:dollars?|bucks?)", "", matched, flags=re.IGNORECASE).strip()
        try:
            values.add(abs(Decimal(raw.replace("$", "").replace(",", ""))).quantize(Decimal("0.01")))
        except InvalidOperation:
            continue
    return values


def _merchant_is_mentioned(merchant: str, message: str) -> bool:
    # Do not run the whole question through merchant-rule normalization: that
    # intentionally strips text following words such as "transaction number",
    # which would also erase a merchant named later in a natural question.
    question = " ".join(re.findall(r"[a-z0-9]+", message.lower().replace("_", " ")))
    candidate = normalize_merchant_rule(merchant, collapse_transfers=False)
    if not candidate or not question:
        return False
    if candidate in question:
        return True
    question_words = set(re.findall(r"[a-z0-9]+", question))
    distinctive = {
        word for word in re.findall(r"[a-z0-9]+", candidate)
        if len(word) >= 4 and not word.isdigit() and word not in _GENERIC_MERCHANT_WORDS
    }
    return bool(distinctive) and distinctive.issubset(question_words)


def _category_is_mentioned(name: str, normalized_question: str) -> bool:
    category_name = normalize_category(name)
    if re.search(rf"\b{re.escape(category_name)}\b", normalized_question):
        return True
    for aliases in ALIASES:
        if category_name not in aliases:
            continue
        return any(
            re.search(rf"\b{re.escape(alias)}\b", normalized_question)
            for alias in aliases
        )
    return False


async def build_relevant_activity_context(
    session: AsyncSession,
    user_id: UUID,
    message: str,
    reference: date | None = None,
) -> dict | None:
    """Return only ledger facts selected by the user's current question."""
    today = reference or date.today()
    lowered = " ".join(message.lower().split())
    explicit_period = _requested_period(lowered, today)
    categories = [row for row in await BudgetRepository(session).list_categories(user_id) if row.active]
    normalized_question = " ".join(re.findall(r"[a-z0-9]+", lowered.replace("&", " and ")))
    matched_categories = [
        row for row in categories
        if _category_is_mentioned(row.name, normalized_question)
    ]
    asks_about_spending = bool(re.search(r"\b(spent|spend|spending)\b", lowered))
    broad_budget_request = (
        bool(_BUDGET_WORDS.search(lowered))
        and ("budget" in lowered or "category" in lowered or "categories" in lowered)
    ) or (asks_about_spending and explicit_period is not None)
    amounts = _mentioned_amounts(message)
    mentions_detail = bool(_DETAIL_WORDS.search(lowered))

    # Merchant matching happens locally over a bounded ledger window. Names
    # that do not occur in the question never leave Meridian.
    lookup_start, lookup_end = (
        (explicit_period[0], explicit_period[1])
        if explicit_period else (shift_month(today.replace(day=1), -11), today)
    )
    ledger, ledger_total = await TransactionRepository(session).list_for_user(
        user_id, since=lookup_start, until=lookup_end, limit=2000
    )
    matched_merchants = sorted({row.merchant for row in ledger if _merchant_is_mentioned(row.merchant, message)})
    broad_detail_request = bool(_BROAD_DETAIL_REQUEST.search(lowered))
    detail_request = bool(
        matched_merchants or amounts or broad_detail_request
        or (matched_categories and mentions_detail)
    )

    relevant = bool(matched_categories or matched_merchants or amounts or detail_request or broad_budget_request)
    if not relevant:
        return None

    if explicit_period:
        start, end, label = explicit_period
    elif matched_merchants or (detail_request and not matched_categories):
        start, end, label = lookup_start, lookup_end, "trailing 12 months"
    else:
        start, end, label = today.replace(day=1), today, "this month to date"
    rows = [row for row in ledger if start <= row.posted_at <= end]

    selected_categories = matched_categories or (categories if broad_budget_request else [])
    category_ids = {row.id for row in selected_categories}
    category_totals: dict[UUID, _CategoryTotals] = defaultdict(_CategoryTotals)
    for row in rows:
        if row.budget_category_id not in category_ids or row.ignored_from_budget:
            continue
        if row.type.value not in {"expense", "transfer"}:
            continue
        spent = -row.amount
        totals = category_totals[row.budget_category_id]
        totals.spent += spent
        totals.transactions += 1
        if row.status.value == "pending":
            totals.pending += spent

    payload: dict = {
        "selection": "Only activity explicitly relevant to the user's question is included.",
        "period": {"label": label, "start": start.isoformat(), "end": end.isoformat()},
    }
    if selected_categories:
        payload["budget_categories"] = [
            {
                "name": category.name,
                "group": category.group_name,
                "monthly_budget": _money(category.monthly_limit),
                "net_spending_in_period": _money(category_totals[category.id].spent),
                "pending_in_period": _money(category_totals[category.id].pending),
                "transaction_count": category_totals[category.id].transactions,
            }
            for category in selected_categories
        ]

    include_details = bool(matched_merchants or amounts or detail_request)
    if include_details:
        matches = rows
        if matched_merchants:
            matches = [row for row in matches if row.merchant in matched_merchants]
        if amounts:
            matches = [row for row in matches if abs(row.amount).quantize(Decimal("0.01")) in amounts]
        if matched_categories:
            matches = [row for row in matches if row.budget_category_id in category_ids]
        matches = sorted(matches, key=lambda row: (row.posted_at, str(row.id)), reverse=True)
        payload["matching_transaction_count"] = len(matches)
        payload["transactions_truncated"] = len(matches) > 50 or ledger_total > 2000
        payload["transactions"] = [
            {
                "date": row.posted_at.isoformat(),
                "merchant": row.merchant,
                "amount": _money(row.amount),
                "type": row.type.value,
                "status": row.status.value,
                "provider_category": row.category,
                "budget_category": row.budget_category_name,
                "account_name": row.account_name,
            }
            for row in matches[:50]
        ]
    return payload
