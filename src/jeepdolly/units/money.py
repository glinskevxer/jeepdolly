"""Money, held as whole cents.

Permit fees are small and exact. A fee is never a float, it is a count of
cents, and every rate multiplication rounds once at the end rather than at each
step. Two rates applied to the same distance and then added is not the same
number as their sum applied once, and the office bills the first one, so the
rounding rule is stated here and not left to whoever writes the tariff.

Half a cent rounds up, away from zero. Bankers rounding is defensible and it is
not what the cashier does.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal
from typing import NewType

from jeepdolly.errors import BadValueError

__all__ = [
    "ZERO",
    "Money",
    "add",
    "at_rate",
    "cents",
    "dollars",
    "format_money",
    "parse_money",
    "total",
]

Money = NewType("Money", int)

_PATTERN = re.compile(r"^\s*(?P<sign>-)?\$?\s*(?P<whole>\d[\d,]*)(?:\.(?P<frac>\d{1,2}))?\s*$")


def cents(value: int) -> Money:
    """Take a whole number of cents."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise BadValueError("money", value, "want a whole number of cents")
    return Money(value)


#: The zero amount, so callers do not write ``cents(0)`` in twenty places.
ZERO = cents(0)


def dollars(value: int | float | str | Decimal) -> Money:
    """A dollar figure as cents, rounded half up at the last step."""
    if isinstance(value, bool):
        raise BadValueError("money", value, "want a dollar amount")
    try:
        amount = Decimal(str(value))
    except Exception as exc:
        raise BadValueError("money", value, "not a dollar amount") from exc
    if not amount.is_finite():
        raise BadValueError("money", value, "not finite")
    quantised = (amount * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    return cents(int(quantised))


def parse_money(text: str) -> Money:
    """Read a dollar figure off a form.

    Accepts ``$125.00``, ``125.00``, ``1,250``, ``-40.00``. More than two
    decimal places is refused rather than rounded, because on a form it means
    somebody typed the wrong thing.
    """
    if not isinstance(text, str):
        raise BadValueError("money", text, "want text")
    hit = _PATTERN.match(text)
    if hit is None:
        raise BadValueError("money", text, "not a dollar amount")
    whole = int(hit.group("whole").replace(",", ""))
    frac = hit.group("frac") or "0"
    frac_value = int(frac.ljust(2, "0"))
    value = whole * 100 + frac_value
    return cents(-value if hit.group("sign") else value)


def format_money(value: Money) -> str:
    """Write an amount the way the invoice prints it."""
    amount = int(value)
    sign = "-" if amount < 0 else ""
    whole, frac = divmod(abs(amount), 100)
    return f"{sign}${whole:,}.{frac:02d}"


def add(*amounts: Money) -> Money:
    """Sum a handful of amounts."""
    return cents(sum(int(a) for a in amounts))


def total(amounts: Iterable[Money]) -> Money:
    """Sum an iterable of amounts."""
    return cents(sum(int(a) for a in amounts))


def at_rate(rate: Money, quantity: int | Decimal) -> Money:
    """Apply a per unit rate to a quantity, rounding once at the end.

    The quantity is exact. A rate of 6 cents a mile over 37 miles is 222 cents
    and not 220, and a rate applied to a half mile lands on the half cent and
    rounds up.
    """
    if isinstance(quantity, bool) or not isinstance(quantity, int | Decimal):
        raise BadValueError("quantity", quantity, "want a whole number or a Decimal")
    product = Decimal(int(rate)) * Decimal(quantity)
    return cents(int(product.quantize(Decimal(1), rounding=ROUND_HALF_UP)))
