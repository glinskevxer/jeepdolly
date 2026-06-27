"""What a carrier has lodged with the office before it may be issued anything.

Two different things wear the same word at the counter. A surety bond is money
the state can call on when a carrier breaks a bridge and walks away. A liability
policy is the carrier's own insurer promising to pay somebody else. The office
files them together because the clerk asks for both in the same breath, and it
keeps them apart in here because they lapse on different days and only one of
them can be called.

A certificate is a record of a piece of paper, not the paper. The office does not
hold the policy and cannot tell you what it excludes. What it can tell you is who
wrote it, for how much, and until when, which is the whole of what the issuing
decision needs.

The amount is the face amount, not what is left of it. A bond that has been
drawn against still reads at its face amount here, because the office finds out
about a draw months later from the surety and never from the carrier.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from enum import StrEnum

from jeepdolly.errors import BadValueError
from jeepdolly.ids.reference import Code, code
from jeepdolly.units.clock import Day, DaySpan, format_day
from jeepdolly.units.money import Money, cents, format_money

__all__ = [
    "CALLABLE",
    "MAX_INSURER",
    "MAX_POLICY",
    "Certificate",
    "Cover",
    "in_force",
    "lapsing",
]

#: Longer than any insurer's trading name the office has had to file.
MAX_INSURER = 60

#: Policy numbers are the insurer's own format and get no validation past this.
MAX_POLICY = 40


class Cover(StrEnum):
    """What a lodged certificate covers.

    ``BOND`` is the only one the state can call on directly. The other three are
    promises to third parties, and the office files them because the statute
    says to rather than because it will ever collect on one.
    """

    BOND = "surety bond"
    LIABILITY = "public liability"
    CARGO = "cargo"
    ESCORT = "escort service"


#: The one the office can call on when a carrier walks away from the damage.
CALLABLE = frozenset({Cover.BOND})


@dataclass(frozen=True, slots=True, order=True)
class Certificate:
    """One piece of paper a carrier has lodged."""

    carrier: Code
    cover: Cover
    insurer: str
    policy: str
    amount: Money
    span: DaySpan

    def __post_init__(self) -> None:
        object.__setattr__(self, "carrier", code(str(self.carrier)))
        object.__setattr__(self, "cover", Cover(self.cover))
        for name, cap in (("insurer", MAX_INSURER), ("policy", MAX_POLICY)):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise BadValueError(name, value, "want some text")
            tidy = " ".join(value.split())
            if len(tidy) > cap:
                raise BadValueError(name, value, f"over {cap} characters")
            object.__setattr__(self, name, tidy)
        object.__setattr__(self, "amount", cents(int(self.amount)))
        if int(self.amount) <= 0:
            raise BadValueError("amount", int(self.amount), "a certificate is for some money")
        if not isinstance(self.span, DaySpan):
            raise BadValueError("span", self.span, "want a span of days")

    @property
    def callable_on_default(self) -> bool:
        """May the state collect against this one itself."""
        return self.cover in CALLABLE

    def in_force(self, on: Day) -> bool:
        """Was this certificate good on a given day."""
        if not isinstance(on, dt.date) or isinstance(on, dt.datetime):
            raise BadValueError("day", on, "want a date")
        return self.span.covers(on)

    def days_left(self, on: Day) -> int:
        """How many days it has to run, counting the day itself.

        Negative once it has lapsed, which reads better in a report than zero
        does. A clerk chasing a renewal wants to know it went four days ago.
        """
        if not isinstance(on, dt.date) or isinstance(on, dt.datetime):
            raise BadValueError("day", on, "want a date")
        return (self.span.last - on).days + 1

    def covers_at_least(self, amount: Money) -> bool:
        """Is the face amount at or above what something requires."""
        return int(self.amount) >= int(cents(int(amount)))

    def shortfall(self, amount: Money) -> Money:
        """How far short of a required amount this certificate falls."""
        gap = int(cents(int(amount))) - int(self.amount)
        return cents(max(gap, 0))

    def renewed(self, span: DaySpan, policy: str | None = None) -> Certificate:
        """The same cover on a fresh span, and usually a fresh policy number."""
        return Certificate(
            carrier=self.carrier,
            cover=self.cover,
            insurer=self.insurer,
            policy=self.policy if policy is None else policy,
            amount=self.amount,
            span=span,
        )

    def __str__(self) -> str:
        return (
            f"{self.cover} {self.policy} with {self.insurer}"
            f" for {format_money(self.amount)} to {format_day(self.span.last)}"
        )


def in_force(held: list[Certificate], on: Day) -> list[Certificate]:
    """Whichever of a carrier's certificates were good on a day."""
    return [one for one in held if one.in_force(on)]


def lapsing(held: list[Certificate], on: Day, within: int) -> list[Certificate]:
    """The ones good today that run out inside a number of days.

    Ones that have already lapsed are left out. They are not lapsing, they are
    gone, and mixing the two produced a chase list where the eight year old
    expired bond sat above the one that goes on Friday.
    """
    if isinstance(within, bool) or not isinstance(within, int):
        raise BadValueError("within", within, "want a whole number of days")
    if within < 0:
        raise BadValueError("within", within, "want nothing negative")
    soon = [one for one in in_force(held, on) if one.days_left(on) <= within]
    return sorted(soon, key=lambda one: (one.span.last, str(one.cover)))
