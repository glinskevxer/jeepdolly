"""Codes and serial numbers.

Two shapes turn up everywhere. A *code* is a short human chosen key, like the
carrier abbreviation a clerk types twenty times a day. A *serial* is issued by
the office in order and never reused, like a permit number.

Codes are normalised, hard, on the way in. Case and stray spaces are the single
largest source of duplicate carrier records, so ``vance``, ``Vance`` and
``VANCE `` are all the same code and there is no way to store the other two.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import NewType

from jeepdolly.errors import BadValueError

__all__ = [
    "KINDS",
    "PERMIT",
    "REVIEW",
    "RIG",
    "STRUCTURE",
    "Code",
    "Serial",
    "SerialKind",
    "code",
    "is_code",
    "serial",
]

Code = NewType("Code", str)

_CODE = re.compile(r"^[A-Z0-9][A-Z0-9-]{1,15}$")
_TIDY = re.compile(r"[\s_]+")


def code(text: str) -> Code:
    """Normalise and check a human chosen key.

    Upper cased, inner runs of whitespace and underscores collapsed to a single
    dash, ends trimmed. Two to sixteen characters of letters, digits and dashes,
    starting on a letter or a digit.
    """
    if not isinstance(text, str):
        raise BadValueError("code", text, "want text")
    tidied = _TIDY.sub("-", text.strip()).upper().strip("-")
    if not _CODE.match(tidied):
        raise BadValueError("code", text, "want 2 to 16 of A-Z, 0-9 and dashes")
    if "--" in tidied:
        raise BadValueError("code", text, "doubled dash")
    return Code(tidied)


def is_code(text: object) -> bool:
    """Would ``code`` accept this without raising."""
    if not isinstance(text, str):
        return False
    try:
        code(text)
    except BadValueError:
        return False
    return True


@dataclass(frozen=True, slots=True, order=True)
class SerialKind:
    """A family of office issued numbers.

    The prefix is what a clerk reads off the paper, and the width is how many
    digits the counter is padded to. Widths are generous on purpose. A counter
    that rolls over does not wrap, it just gets wider, and the sort order of the
    printed form stops matching the issue order at that point, so the width is
    picked to outlast the office.
    """

    prefix: str
    width: int

    def __post_init__(self) -> None:
        if not re.match(r"^[A-Z]{1,4}$", self.prefix):
            raise BadValueError("prefix", self.prefix, "want 1 to 4 capitals")
        if not 3 <= self.width <= 9:
            raise BadValueError("width", self.width, "want 3 to 9 digits")

    def format(self, number: int) -> Serial:
        """Render a counter value as the printed reference."""
        if isinstance(number, bool) or not isinstance(number, int):
            raise BadValueError("serial", number, "want a whole number")
        if number < 1:
            raise BadValueError("serial", number, "counters start at 1")
        return Serial(f"{self.prefix}-{number:0{self.width}d}")

    def number(self, text: str) -> int:
        """Read the counter value back out of a printed reference."""
        parsed = serial(text)
        head, _, tail = parsed.partition("-")
        if head != self.prefix:
            raise BadValueError("serial", text, f"not a {self.prefix} reference")
        return int(tail)


Serial = NewType("Serial", str)

_SERIAL = re.compile(r"^(?P<prefix>[A-Z]{1,4})-(?P<digits>\d{3,9})$")


def serial(text: str) -> Serial:
    """Normalise and check a printed office reference."""
    if not isinstance(text, str):
        raise BadValueError("serial", text, "want text")
    tidied = text.strip().upper()
    hit = _SERIAL.match(tidied)
    if hit is None:
        raise BadValueError("serial", text, "want a prefix, a dash and digits")
    if int(hit.group("digits")) < 1:
        raise BadValueError("serial", text, "counters start at 1")
    return Serial(tidied)


#: Permit numbers. Six digits carries about forty years at current volume.
PERMIT = SerialKind("P", 6)

#: Rig configurations as the office recorded them, not as the carrier owns them.
RIG = SerialKind("R", 5)

#: Bridges, culverts and overhead structures.
STRUCTURE = SerialKind("STR", 5)

#: Engineering reviews of a superload or an over dimension application.
REVIEW = SerialKind("E", 5)

KINDS: dict[str, SerialKind] = {
    "permit": PERMIT,
    "rig": RIG,
    "structure": STRUCTURE,
    "review": REVIEW,
}
