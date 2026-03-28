"""What is about to run out, and what has already.

The office rings carriers about two things: an annual permit coming up for
renewal, and a single trip permit whose load has not moved yet with two days
left on it. Both are the same question asked of the calendar, so both are here.

Expiry is worked out against a day the caller passes in rather than against
today. Every report in this package takes its day as an argument, which is what
lets the whole suite run without a clock and what lets a clerk ask what next
Monday's list will look like.

A void permit is never on the list. It has not expired, it has been cancelled,
and ringing a carrier about it makes the office look like it does not read its
own records.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from jeepdolly.errors import BadValueError
from jeepdolly.permit.permit import Permit, State
from jeepdolly.report.layout import LEFT, RIGHT, banner, pairs, table
from jeepdolly.units.clock import Day, format_day
from jeepdolly.units.money import format_money, total

__all__ = ["SOON", "Expiry", "expired", "expiring", "expiry_sheet"]

#: How many days ahead the office calls "soon".
SOON = 14


@dataclass(frozen=True, slots=True, order=True)
class Expiry:
    """One permit and how long it has left."""

    days_left: int
    number: str
    carrier: str
    last_day: Day
    state: str

    @property
    def gone(self) -> bool:
        """Has it already run out."""
        return self.days_left < 0

    @property
    def today(self) -> bool:
        """Does it run out today."""
        return self.days_left == 0

    def __str__(self) -> str:
        if self.gone:
            return f"{self.number} {self.carrier} ran out {-self.days_left} days ago"
        if self.today:
            return f"{self.number} {self.carrier} runs out today"
        return f"{self.number} {self.carrier} has {self.days_left} days left"


def _expiry(permit: Permit, on: Day) -> Expiry:
    """One permit's expiry as at a day."""
    return Expiry(
        days_left=(permit.span.last - on).days,
        number=str(permit.number),
        carrier=permit.carrier,
        last_day=permit.span.last,
        state=str(permit.state),
    )


def _live(permits: list[Permit]) -> list[Permit]:
    """The permits the office would still ring somebody about."""
    return [one for one in permits if one.state is State.ACTIVE]


def expiring(permits: list[Permit], on: Day, within: int = SOON) -> list[Expiry]:
    """Every live permit running out inside the next few days, soonest first."""
    if isinstance(within, bool) or not isinstance(within, int):
        raise BadValueError("within", within, "want a whole number of days")
    if within < 0:
        raise BadValueError("within", within, "negative")
    if not isinstance(on, dt.date) or isinstance(on, dt.datetime):
        raise BadValueError("day", on, "want a date")
    found = [_expiry(one, on) for one in _live(permits)]
    return sorted(one for one in found if 0 <= one.days_left <= within)


def expired(permits: list[Permit], on: Day) -> list[Expiry]:
    """Every live permit that has already run out, longest gone first."""
    found = [_expiry(one, on) for one in _live(permits)]
    return sorted(one for one in found if one.days_left < 0)


def expiry_sheet(
    permits: list[Permit], on: Day, within: int = SOON, fee_column: bool = True
) -> list[str]:
    """The whole expiry list, ready to print."""
    soon = expiring(permits, on, within)
    gone = expired(permits, on)
    lines = banner(f"expiry list as at {format_day(on)}")
    if not soon and not gone:
        lines.append(f"nothing runs out in the next {within} days")
        return lines
    by_number = {str(one.number): one for one in permits}
    for title, batch in (("running out", soon), ("already run out", gone)):
        if not batch:
            continue
        lines.append("")
        lines.extend(banner(title))
        headings = ["permit", "carrier", "last day", "days"]
        aligns = [LEFT, LEFT, LEFT, RIGHT]
        if fee_column:
            headings.append("fee")
            aligns.append(RIGHT)
        body: list[list[str]] = []
        for one in batch:
            row = [one.number, one.carrier, format_day(one.last_day), str(one.days_left)]
            if fee_column:
                row.append(format_money(by_number[one.number].fee))
            body.append(row)
        lines.extend(table(headings, body, aligns=aligns))
    lines.append("")
    lines.extend(
        pairs(
            [
                ("running out", str(len(soon))),
                ("already gone", str(len(gone))),
                ("fees at risk", format_money(total(by_number[o.number].fee for o in soon))),
            ]
        )
    )
    return lines
