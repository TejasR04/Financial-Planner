"""Small value objects used throughout the domain and simulation layers.

Money is always represented as Decimal, never float, to avoid compounding
rounding errors across multi-decade projections. Rates are stored as
decimals (0.065 for 6.5%), never whole-number percentages.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

TWO_PLACES = Decimal("0.01")


def to_money(value: float | int | str | Decimal) -> Decimal:
    """Coerce any numeric input into a Decimal rounded to cents."""
    return Decimal(str(value)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def to_rate(value: float | int | str | Decimal) -> Decimal:
    """Coerce any numeric input into a Decimal rate (e.g. 6.5 -> 0.065 is NOT
    done here — callers must pass already-normalized decimals; this only
    ensures Decimal precision, avoiding float drift in exponentiation)."""
    return Decimal(str(value))


@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: str = "USD"

    def __post_init__(self):
        object.__setattr__(self, "amount", to_money(self.amount))

    def __add__(self, other: "Money") -> "Money":
        self._assert_same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: "Money") -> "Money":
        self._assert_same_currency(other)
        return Money(self.amount - other.amount, self.currency)

    def __neg__(self) -> "Money":
        return Money(-self.amount, self.currency)

    def __lt__(self, other: "Money") -> bool:
        self._assert_same_currency(other)
        return self.amount < other.amount

    def _assert_same_currency(self, other: "Money") -> None:
        if self.currency != other.currency:
            raise ValueError(
                f"Currency mismatch: {self.currency} vs {other.currency}"
            )

    def as_float(self) -> float:
        return float(self.amount)
