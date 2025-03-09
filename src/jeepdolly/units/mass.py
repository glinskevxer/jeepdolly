"""Weights, held as whole pounds.

Scale tickets are whole pounds and the statutes are written in whole pounds, so
there is no reason for anything smaller. Tons show up in conversation and on the
fee schedule, and a ton here is always the short ton of 2000 pounds.

The office rounds a ton figure up when it is buying, because a fee band that
starts at "over 10 tons" has to catch 10 tons and one pound.
"""

from __future__ import annotations

import re
from typing import NewType

from jeepdolly.errors import BadValueError

__all__ = [
    "MAX_POUNDS",
    "POUNDS_PER_TON",
    "Pounds",
    "format_weight",
    "parse_weight",
    "pounds",
    "to_tons",
    "tons",
    "tons_over",
]

Pounds = NewType("Pounds", int)

#: A short ton. Nothing in this package uses a metric tonne.
POUNDS_PER_TON = 2000

#: Two and a half million pounds. The heaviest thing the office has ever
#: permitted was a transformer at just under a million, so this is a typo guard
#: and not a policy limit.
MAX_POUNDS = 2_500_000

#: Zero pounds, named so a dataclass default can point at it instead of
#: calling the constructor, which the linter reads as a shared mutable.
NO_WEIGHT = Pounds(0)

_PATTERN = re.compile(
    r"""^\s*
    (?P<number>\d[\d,]*(?:\.\d+)?)
    \s*
    (?P<unit>lbs?|pounds?|t|tons?)?
    \s*$""",
    re.VERBOSE | re.IGNORECASE,
)


def pounds(value: int) -> Pounds:
    """Take a whole number of pounds, checking it is one we can carry."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise BadValueError("weight", value, "want a whole number of pounds")
    if value < 0:
        raise BadValueError("weight", value, "negative")
    if value > MAX_POUNDS:
        raise BadValueError("weight", value, f"over {MAX_POUNDS} pounds")
    return Pounds(value)


def tons(value: float) -> Pounds:
    """A ton figure as pounds, rounded to the nearest pound."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise BadValueError("weight", value, "want a number of tons")
    return pounds(round(value * POUNDS_PER_TON))


def parse_weight(text: str) -> Pounds:
    """Read a weight off a scale ticket or a form.

    A bare number is pounds. Commas are ignored because every scale ticket has
    them. A decimal is only accepted with a ton unit, since half a pound is not
    a thing the office weighs.
    """
    if not isinstance(text, str):
        raise BadValueError("weight", text, "want text")
    hit = _PATTERN.match(text)
    if hit is None:
        raise BadValueError("weight", text, "not a weight")
    raw = hit.group("number").replace(",", "")
    unit = (hit.group("unit") or "lb").lower()
    if unit.startswith("t"):
        return tons(float(raw))
    if "." in raw:
        raise BadValueError("weight", text, "pounds are whole")
    return pounds(int(raw))


def format_weight(value: Pounds) -> str:
    """Write a weight the way the permit prints it."""
    return f"{int(value):,} lb"


def to_tons(value: Pounds) -> float:
    """Tons as a float, for reports that show one decimal."""
    return int(value) / POUNDS_PER_TON


def tons_over(value: Pounds, limit: Pounds) -> int:
    """Whole tons above a limit, rounded up, never below zero.

    This is the fee schedule's idea of overweight. One pound over the limit is
    one ton over for money purposes, which looks harsh and is what the schedule
    says.
    """
    excess = int(value) - int(limit)
    if excess <= 0:
        return 0
    return -(-excess // POUNDS_PER_TON)
