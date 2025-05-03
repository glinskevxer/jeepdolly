"""Road distance, held as hundredths of a mile.

Mileposts are published to two decimal places and the fee schedule bills by the
mile, so the stored unit is the hundredth and nothing rounds until the money is
worked out. Inches would be exact too and would overflow into numbers nobody can
read; a two hundred mile trip is twelve million inches and twenty thousand
hundredths.

Rounding up to whole miles is a separate call and is deliberately not automatic,
because the office bills a part mile as a whole mile and reports it as the part
mile it is.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from decimal import Decimal
from typing import NewType

from jeepdolly.errors import BadValueError

__all__ = [
    "MAX_HUNDREDTHS",
    "NO_DISTANCE",
    "Miles",
    "add_distance",
    "format_distance",
    "hundredths",
    "miles",
    "parse_distance",
    "to_miles",
    "total_distance",
    "whole_miles",
]

Miles = NewType("Miles", int)

#: Ten thousand miles. A permit route inside one state does not approach this,
#: so anything above it is a units mistake rather than a long trip.
MAX_HUNDREDTHS = 1_000_000

_PATTERN = re.compile(r"^\s*(?P<whole>\d+)(?:\.(?P<frac>\d{1,2}))?\s*(?:mi|miles?)?\s*$", re.I)


def hundredths(value: int) -> Miles:
    """Take a whole number of hundredths of a mile."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise BadValueError("distance", value, "want a whole number of hundredths")
    if value < 0:
        raise BadValueError("distance", value, "negative")
    if value > MAX_HUNDREDTHS:
        raise BadValueError("distance", value, f"over {MAX_HUNDREDTHS} hundredths")
    return Miles(value)


#: Zero distance, named so a dataclass default can point at it.
NO_DISTANCE = Miles(0)


def miles(value: int | float | str | Decimal) -> Miles:
    """A mile figure as hundredths, refusing anything finer than a hundredth."""
    if isinstance(value, bool):
        raise BadValueError("distance", value, "want a number of miles")
    try:
        amount = Decimal(str(value))
    except Exception as exc:
        raise BadValueError("distance", value, "not a number of miles") from exc
    if not amount.is_finite():
        raise BadValueError("distance", value, "not finite")
    scaled = amount * 100
    if scaled != scaled.to_integral_value():
        raise BadValueError("distance", value, "finer than a hundredth of a mile")
    return hundredths(int(scaled))


def parse_distance(text: str) -> Miles:
    """Read a distance off a route sheet."""
    if not isinstance(text, str):
        raise BadValueError("distance", text, "want text")
    hit = _PATTERN.match(text)
    if hit is None:
        raise BadValueError("distance", text, "not a distance")
    whole = int(hit.group("whole"))
    frac = (hit.group("frac") or "0").ljust(2, "0")
    return hundredths(whole * 100 + int(frac))


def format_distance(value: Miles) -> str:
    """Write a distance the way the route sheet prints it."""
    whole, frac = divmod(int(value), 100)
    return f"{whole}.{frac:02d} mi"


def to_miles(value: Miles) -> Decimal:
    """The distance as an exact decimal number of miles."""
    return Decimal(int(value)) / 100


def whole_miles(value: Miles) -> int:
    """Whole miles, rounded up, which is what the fee schedule bills."""
    return -(-int(value) // 100)


def add_distance(*values: Miles) -> Miles:
    """Sum a handful of distances."""
    return hundredths(sum(int(v) for v in values))


def total_distance(values: Iterable[Miles]) -> Miles:
    """Sum an iterable of distances."""
    return hundredths(sum(int(v) for v in values))
