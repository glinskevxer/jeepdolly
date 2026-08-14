"""The enforcement return: what the scales found and what it came to.

Two audiences and therefore two shapes on one sheet.

The office wants the money: how many stops, how many came back over, and what
was charged. That is the summary and it is the only part anybody reads most
months.

The enforcement side wants the carriers: who keeps coming back, and how the
office is treating them. That is the repeat table, and it is sorted on the count
rather than on the money, because the carrier three thousand pounds over four
times is the problem and the carrier thirty thousand over once is a bad day.

Both are worked out from the violations rather than from the tickets. A ticket
that found nothing is a stop and not a violation, so the stop count is passed in
separately rather than derived, which is the one place this sheet takes a figure
on trust.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from jeepdolly.enforce.ticket import Discrepancy
from jeepdolly.enforce.violation import Violation, owed
from jeepdolly.errors import BadValueError
from jeepdolly.report.layout import LEFT, RIGHT
from jeepdolly.report.sheet import Sheet
from jeepdolly.units.clock import Day, DaySpan, format_day
from jeepdolly.units.mass import Pounds, format_weight, pounds
from jeepdolly.units.money import Money, format_money

__all__ = ["Repeat", "by_kind", "enforcement_sheet", "repeats", "within"]


@dataclass(frozen=True, slots=True, order=True)
class Repeat:
    """One carrier's record over a period, ready to sort on."""

    count: int
    carrier: str
    penalties: Money
    worst: Pounds

    def __str__(self) -> str:
        word = "violation" if self.count == 1 else "violations"
        return f"{self.carrier} {self.count} {word}, {format_money(self.penalties)}"


def within(violations: list[Violation], span: DaySpan) -> list[Violation]:
    """Every violation found inside a run of days, oldest first."""
    if not isinstance(span, DaySpan):
        raise BadValueError("span", span, "want a span of days")
    return sorted(one for one in violations if span.covers(one.on))


def by_kind(violations: list[Violation]) -> dict[Discrepancy, int]:
    """How many of each sort of overage, over whatever was handed in."""
    counted: dict[Discrepancy, int] = {}
    for one in violations:
        counted[one.kind] = counted.get(one.kind, 0) + 1
    return counted


def repeats(violations: list[Violation], least: int = 2) -> list[Repeat]:
    """Every carrier with at least so many violations, worst offender first."""
    if isinstance(least, bool) or not isinstance(least, int) or least < 1:
        raise BadValueError("least", least, "want a whole number of violations")
    held: dict[str, list[Violation]] = {}
    for one in violations:
        held.setdefault(one.carrier, []).append(one)
    found = [
        Repeat(
            count=len(batch),
            carrier=carrier,
            penalties=owed(batch),
            worst=pounds(max(int(one.over) for one in batch)),
        )
        for carrier, batch in held.items()
        if len(batch) >= least
    ]
    return sorted(found, reverse=True)


def enforcement_sheet(
    violations: list[Violation], span: DaySpan, stops: int = 0, on: Day | None = None
) -> list[str]:
    """The whole enforcement return, ready to print."""
    if on is not None and (not isinstance(on, dt.date) or isinstance(on, dt.datetime)):
        raise BadValueError("day", on, "want a date")
    found = within(violations, span)
    sheet = Sheet().title(f"enforcement return {span}")
    if not found:
        head = f"{stops} stops and nothing over" if stops else "nothing weighed"
        return sheet.note(head).done()
    sheet.section("what was found").rows(
        ["day", "carrier", "permit", "kind", "over", "penalty"],
        [
            [
                format_day(one.on),
                one.carrier,
                str(one.permit),
                str(one.kind),
                format_weight(one.over),
                format_money(one.penalty),
            ]
            for one in found
        ],
        aligns=[LEFT, LEFT, LEFT, LEFT, RIGHT, RIGHT],
    )
    again = repeats(found)
    if again:
        sheet.section("carriers back more than once").rows(
            ["carrier", "times", "worst", "penalties"],
            [
                [
                    one.carrier,
                    str(one.count),
                    format_weight(one.worst),
                    format_money(one.penalties),
                ]
                for one in again
            ],
            aligns=[LEFT, RIGHT, RIGHT, RIGHT],
        )
    counted = by_kind(found)
    summary = [
        ("stops", str(stops)) if stops else ("violations", str(len(found))),
        ("carriers", str(len({one.carrier for one in found}))),
        ("penalties", format_money(owed(found))),
    ]
    summary.extend((str(kind), str(count)) for kind, count in sorted(counted.items()))
    return sheet.summary(summary).done()
