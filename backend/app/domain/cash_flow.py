"""Shared cash-flow treatment for reporting and budget reconciliation."""
from decimal import Decimal


def is_card_payment(transaction_type: str, category: str, merchant: str) -> bool:
    category, merchant = category.upper(), merchant.upper()
    return (
        transaction_type == "credit_card_payment"
        or category == "LOAN_PAYMENTS_CREDIT_CARD_PAYMENT"
        or "PAYMENT - BILT" in merchant
        or (category == "LOAN_PAYMENTS" and any(marker in merchant for marker in (
            "CREDIT CRD", "CREDIT CARD", "AUTOPAY PAYMENT", "AUTOMATIC PAYMENT", "PAYMENT - THANK",
        )))
    )


def cash_flow_amounts(transaction_type: str, amount: Decimal, category: str = "", merchant: str = "") -> tuple[Decimal, Decimal]:
    if is_card_payment(transaction_type, category, merchant):
        return Decimal(0), Decimal(0)
    return (amount if transaction_type == "income" else Decimal(0),
            -amount if transaction_type == "expense" else Decimal(0))
