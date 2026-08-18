"""What an overage costs the carrier, once the ticket has been written.

The penalty is banded on the overage in pounds, and the bands are progressive
the same way the permit fee is. That is not a coincidence: a cliff at a band edge
is worth arguing about, and a penalty worth arguing about gets argued about in
front of a magistrate who then reads the whole schedule out loud.

Two things sit on top of the bands and they interact, which is the part worth
reading.

A repeat inside the look back window is charged at a multiple. The multiple is
worked out from how many previous violations the carrier has, not from how bad
this one is, so a small third overage costs more than a large first one. That is
the office deciding that the pattern is the problem.

And a violation on a permit that had already been amended is charged at the
first offence rate whatever the history, because the office has learned that
most of those are a clerk's amendment not reaching the driver in time. That rule
reads the amendment chain to decide what the violation history means, which is
why it lives here and not in the band table.
"""

from __future__ import annotations

from dataclasses import dataclass

from jeepdolly.billing.tariff import Band, band_charge, check_bands
from jeepdolly.enforce.ticket import Discrepancy, Overage
from jeepdolly.errors import BadValueError
from jeepdolly.ids.reference import Serial, serial
from jeepdolly.units.clock import Day, format_day, only_a_day
from jeepdolly.units.mass import Pounds, format_weight, pounds
from jeepdolly.units.money import Money, cents, format_money, total

__all__ = [
    "CHARGEABLE",
    "LOOK_BACK_DAYS",
    "PENALTY_BANDS",
    "REPEAT_MULTIPLES",
    "Violation",
    "multiple_for",
    "owed",
    "penalty_for",
    "repeats_within",
    "violations_from",
]

#: How far back the office looks when deciding whether this is a repeat.
LOOK_BACK_DAYS = 365

#: Charged per whole ton over, progressively. The last band runs to the end.
PENALTY_BANDS: tuple[Band, ...] = (
    Band(upper=5, rate=cents(2500)),
    Band(upper=15, rate=cents(5000)),
    Band(upper=None, rate=cents(9000)),
)

#: What a second, third and any later violation are charged as a multiple of the
#: first. Anything past the end of the table is charged at the last figure.
REPEAT_MULTIPLES: tuple[int, ...] = (1, 2, 3)

#: The discrepancies that carry a penalty. A rig lighter than its permit is worth
#: knowing about and is not an offence.
CHARGEABLE = frozenset({Discrepancy.GROSS, Discrepancy.AXLE})


def multiple_for(previous: int) -> int:
    """What this violation is charged as a multiple of the first offence rate."""
    if isinstance(previous, bool) or not isinstance(previous, int):
        raise BadValueError("previous", previous, "want a whole number")
    if previous < 0:
        raise BadValueError("previous", previous, "negative")
    if previous >= len(REPEAT_MULTIPLES):
        return REPEAT_MULTIPLES[-1]
    return REPEAT_MULTIPLES[previous]


def penalty_for(over: Pounds, previous: int = 0, forgiven: bool = False) -> Money:
    """What one overage costs, given how many the carrier already has.

    ``forgiven`` is the amended permit case. It drops the repeat multiple and
    leaves the band charge, so the carrier still pays for the pounds and does
    not pay for a pattern the office is not sure is theirs.
    """
    if not isinstance(forgiven, bool):
        raise BadValueError("forgiven", forgiven, "want true or false")
    weight = pounds(int(over))
    if int(weight) <= 0:
        return cents(0)
    check_bands(PENALTY_BANDS)
    tons = -(-int(weight) // 2000)
    base = band_charge(tons, PENALTY_BANDS)
    times = 1 if forgiven else multiple_for(previous)
    return cents(int(base) * times)


@dataclass(frozen=True, slots=True, order=True)
class Violation:
    """One chargeable overage off one ticket, priced."""

    on: Day
    ticket: Serial
    permit: Serial
    carrier: str
    kind: Discrepancy
    over: Pounds
    penalty: Money

    def __post_init__(self) -> None:
        only_a_day(self.on, "day")
        for name in ("ticket", "permit"):
            object.__setattr__(self, name, serial(str(getattr(self, name))))
        object.__setattr__(self, "kind", Discrepancy(self.kind))
        object.__setattr__(self, "over", pounds(int(self.over)))
        object.__setattr__(self, "penalty", cents(int(self.penalty)))
        if not isinstance(self.carrier, str) or not self.carrier.strip():
            raise BadValueError("carrier", self.carrier, "want some text")
        object.__setattr__(self, "carrier", self.carrier.strip().upper())
        if self.kind not in CHARGEABLE:
            raise BadValueError("kind", self.kind, "not something the office charges for")
        if int(self.over) <= 0:
            raise BadValueError("over", int(self.over), "a violation is over by something")
        if int(self.penalty) < 0:
            raise BadValueError("penalty", int(self.penalty), "negative")

    def within(self, day: Day, days: int = LOOK_BACK_DAYS) -> bool:
        """Is this violation inside the look back window as at a day."""
        if isinstance(days, bool) or not isinstance(days, int) or days < 0:
            raise BadValueError("days", days, "want a whole number of days")
        return 0 <= (day - self.on).days <= days

    def __str__(self) -> str:
        return (
            f"{format_day(self.on)} {self.carrier} {self.kind}"
            f" by {format_weight(self.over)}, {format_money(self.penalty)}"
        )


def repeats_within(history: list[Violation], day: Day, days: int = LOOK_BACK_DAYS) -> int:
    """How many violations a carrier already has inside the look back window."""
    only_a_day(day, "day")
    return sum(1 for one in history if one.within(day, days))


def violations_from(
    overages: list[Overage],
    ticket: Serial,
    permit: Serial,
    carrier: str,
    on: Day,
    history: list[Violation] | None = None,
    forgiven: bool = False,
) -> list[Violation]:
    """Price every chargeable overage off one ticket.

    Each overage on the ticket is charged against the same violation count. A
    rig over on the gross and over on an axle is one incident, so charging the
    axle as a repeat of the gross would double the multiple on what the officer
    saw as one stop.
    """
    previous = repeats_within(history or [], on)
    return [
        Violation(
            on=on,
            ticket=ticket,
            permit=permit,
            carrier=carrier,
            kind=one.kind,
            over=one.over,
            penalty=penalty_for(one.over, previous, forgiven),
        )
        for one in overages
        if one.kind in CHARGEABLE and int(one.over) > 0
    ]


def owed(violations: list[Violation]) -> Money:
    """What a batch of violations comes to."""
    return total(one.penalty for one in violations)
