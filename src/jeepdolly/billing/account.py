"""The carrier's account with the office.

Most permits are bought on account rather than paid for at the counter, so the
office keeps a running balance per carrier. The balance is not stored. It is the
sum of the entries, worked out every time it is asked for, because a stored
balance and a list of entries disagree eventually and there is no way to tell
which one is right.

Every entry is signed from the carrier's point of view. A deposit is positive, a
charge is negative, a refund is positive, an adjustment is whichever the clerk
says. That means the balance is a plain sum with no special cases, and a
negative balance means the carrier owes the office.

The floor is how far into the red a carrier may go. It is per carrier, because a
carrier who has been on account for fifteen years is not the same risk as one
who opened last week.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from jeepdolly.errors import BadValueError, NotAllowedError
from jeepdolly.ids.reference import Code, code
from jeepdolly.units.clock import Day, DaySpan
from jeepdolly.units.money import ZERO, Money, cents, format_money, total

__all__ = ["DEFAULT_FLOOR", "SIGNS", "Account", "Entry", "EntryKind", "running"]

#: How far below zero an ordinary account may run.
DEFAULT_FLOOR = cents(-500_00)


class EntryKind(StrEnum):
    """What sort of movement this is."""

    DEPOSIT = "deposit"
    CHARGE = "charge"
    REFUND = "refund"
    ADJUSTMENT = "adjustment"


#: Which way each kind moves the balance. An adjustment carries its own sign.
SIGNS: dict[EntryKind, int] = {
    EntryKind.DEPOSIT: 1,
    EntryKind.CHARGE: -1,
    EntryKind.REFUND: 1,
    EntryKind.ADJUSTMENT: 0,
}


@dataclass(frozen=True, slots=True, order=True)
class Entry:
    """One movement on one carrier's account.

    ``amount`` is always given unsigned except on an adjustment, where the sign
    is the whole point. The kind decides the direction and ``signed`` is what
    the balance sums.
    """

    day: Day
    sequence: int
    carrier: Code
    kind: EntryKind
    amount: Money
    reference: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "carrier", code(str(self.carrier)))
        object.__setattr__(self, "kind", EntryKind(self.kind))
        object.__setattr__(self, "amount", cents(int(self.amount)))
        if not isinstance(self.day, dt.date) or isinstance(self.day, dt.datetime):
            raise BadValueError("day", self.day, "want a date")
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int):
            raise BadValueError("sequence", self.sequence, "want a whole number")
        if self.sequence < 1:
            raise BadValueError("sequence", self.sequence, "sequences start at 1")
        for field in ("reference", "note"):
            value = getattr(self, field)
            if not isinstance(value, str):
                raise BadValueError(field, value, "want text")
            object.__setattr__(self, field, " ".join(value.split()))
        self._check_kind()

    def _check_kind(self) -> None:
        """Each kind wants something the others do not."""
        if self.kind is EntryKind.ADJUSTMENT:
            if int(self.amount) == 0:
                raise BadValueError("amount", 0, "an adjustment moves something")
            if not self.note:
                raise BadValueError("note", self.note, "an adjustment needs a note")
        elif int(self.amount) <= 0:
            raise BadValueError("amount", int(self.amount), "want more than nothing")
        if self.kind is EntryKind.CHARGE and not self.reference:
            raise BadValueError("reference", self.reference, "a charge names its permit")

    @property
    def signed(self) -> Money:
        """The amount as the balance sees it."""
        sign = SIGNS[self.kind]
        if sign == 0:
            return self.amount
        return cents(sign * int(self.amount))

    def __str__(self) -> str:
        tail = f" {self.reference}" if self.reference else ""
        return f"{self.day} {self.kind}{tail} {format_money(self.signed)}"


@dataclass(frozen=True, slots=True)
class Account:
    """One carrier's entries and what they add up to."""

    carrier: Code
    entries: tuple[Entry, ...]
    floor: Money = DEFAULT_FLOOR

    def __post_init__(self) -> None:
        object.__setattr__(self, "carrier", code(str(self.carrier)))
        object.__setattr__(self, "entries", tuple(sorted(self.entries)))
        object.__setattr__(self, "floor", cents(int(self.floor)))
        if int(self.floor) > 0:
            raise BadValueError("floor", int(self.floor), "a credit floor is not positive")
        for entry in self.entries:
            if entry.carrier != self.carrier:
                raise BadValueError("entry", entry.carrier, "belongs to another carrier")
        seen = [e.sequence for e in self.entries]
        if len(set(seen)) != len(seen):
            raise BadValueError("entries", seen, "two entries share a sequence")

    @property
    def balance(self) -> Money:
        """What the carrier has with the office, negative if they owe."""
        return total(entry.signed for entry in self.entries)

    @property
    def in_credit(self) -> bool:
        """Is the balance at or above zero."""
        return int(self.balance) >= 0

    @property
    def headroom(self) -> Money:
        """How much more may be charged before the floor is hit."""
        return cents(int(self.balance) - int(self.floor))

    def allows(self, charge: Money) -> bool:
        """May a charge of this size be posted."""
        if int(charge) < 0:
            raise BadValueError("charge", int(charge), "negative")
        return int(self.balance) - int(charge) >= int(self.floor)

    def check(self, charge: Money) -> None:
        """Raise unless a charge of this size may be posted."""
        if not self.allows(charge):
            raise NotAllowedError(
                "account", f"at {format_money(self.balance)}", f"charge {format_money(charge)}"
            )

    def within(self, span: DaySpan) -> tuple[Entry, ...]:
        """The entries falling inside a span of days."""
        return tuple(e for e in self.entries if span.covers(e.day))

    def balance_on(self, day: Day) -> Money:
        """What the balance was at the end of one day."""
        return total(e.signed for e in self.entries if e.day <= day)

    def of_kind(self, kind: EntryKind) -> tuple[Entry, ...]:
        """The entries of one kind."""
        wanted = EntryKind(kind)
        return tuple(e for e in self.entries if e.kind is wanted)

    def __len__(self) -> int:
        return len(self.entries)

    def __str__(self) -> str:
        return f"{self.carrier} {format_money(self.balance)} over {len(self.entries)} entries"


def running(entries: Iterable[Entry]) -> list[tuple[Entry, Money]]:
    """Each entry with the balance after it, oldest first."""
    balance = ZERO
    out: list[tuple[Entry, Money]] = []
    for entry in sorted(entries):
        balance = cents(int(balance) + int(entry.signed))
        out.append((entry, balance))
    return out
