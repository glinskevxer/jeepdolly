"""Lengths, held as whole inches.

Permit paperwork is written in feet and inches and read out loud the same way,
so the parser and the formatter both speak that. Everything between them is a
plain int, because a load that is thirteen feet six inches tall is 162 inches
and nothing about it wants a float.

The unit is a ``NewType`` rather than a class. It costs nothing at runtime and
it still stops a weight being handed to a function that wants a height.
"""

from __future__ import annotations

import re
from typing import NewType

from jeepdolly.errors import BadValueError

__all__ = [
    "MAX_INCHES",
    "Inches",
    "feet",
    "feet_inches",
    "format_length",
    "inches",
    "parse_length",
    "to_feet",
]

Inches = NewType("Inches", int)

#: A hundred and fifty feet. Nothing the office permits is longer than this in a
#: single dimension, and a number above it is a typo rather than a load.
MAX_INCHES = 1800

#: Zero inches, named so a dataclass default can point at it instead of
#: calling the constructor, which the linter reads as a shared mutable.
NO_LENGTH = Inches(0)

_PATTERN = re.compile(
    r"""^\s*
    (?:(?P<feet>\d+)\s*(?:'|ft|feet|f)\s*)?
    (?:(?P<inches>\d+)\s*(?:"|in|inches|i)?\s*)?
    $""",
    re.VERBOSE | re.IGNORECASE,
)


def inches(value: int) -> Inches:
    """Take a whole number of inches, checking it is one we can carry."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise BadValueError("length", value, "want a whole number of inches")
    if value < 0:
        raise BadValueError("length", value, "negative")
    if value > MAX_INCHES:
        raise BadValueError("length", value, f"over {MAX_INCHES} inches")
    return Inches(value)


def feet(value: int) -> Inches:
    """Whole feet, as inches."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise BadValueError("length", value, "want a whole number of feet")
    return inches(value * 12)


def feet_inches(ft: int, inch: int) -> Inches:
    """Feet and inches together, the way a form is filled in."""
    if isinstance(inch, bool) or not isinstance(inch, int) or not 0 <= inch < 12:
        raise BadValueError("length", inch, "the inches part runs 0 to 11")
    return inches(ft * 12 + inch)


def parse_length(text: str) -> Inches:
    """Read a length off a form.

    Accepts ``13'6"``, ``13' 6``, ``13 ft 6 in``, ``162``, ``13'``. A bare
    number is inches, which is the convention on the office's own forms even
    though a driver reading it aloud would say feet.
    """
    if not isinstance(text, str):
        raise BadValueError("length", text, "want text")
    hit = _PATTERN.match(text)
    if hit is None or (hit.group("feet") is None and hit.group("inches") is None):
        raise BadValueError("length", text, "not a length")
    ft_part = hit.group("feet")
    in_part = hit.group("inches")
    if ft_part is None:
        return inches(int(in_part or 0))
    total = int(ft_part) * 12 + int(in_part or 0)
    if in_part is not None and int(in_part) >= 12:
        raise BadValueError("length", text, "the inches part runs 0 to 11")
    return inches(total)


def format_length(value: Inches) -> str:
    """Write a length the way the permit prints it."""
    ft, inch = divmod(int(value), 12)
    if inch == 0:
        return f"{ft}'"
    return f"{ft}'{inch}\""


def to_feet(value: Inches) -> float:
    """Feet as a float, for the one place that reports decimals."""
    return int(value) / 12.0
