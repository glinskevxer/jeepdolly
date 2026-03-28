"""How much work came through the counter, and how long it took.

Two numbers the office is asked for every quarter: how many permits were issued
in a month, and how long an application waited. The first is a count off the
permits. The second can only come from the journal, because an application that
was filed on Monday and issued on Thursday leaves no trace of the Monday
anywhere else.

Turnaround is measured filed to issued, in whole days, and a permit issued the
day it was filed counts as nought rather than one. That is the office's own
convention and it is stated because the other reading is just as defensible and
the two differ by about a day and a half across a year.

An application that was never issued is not in the turnaround figures at all. It
is in the counts, where it belongs, and averaging it in as a very slow permit
would say the office is slow when what it actually did was refuse something.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from jeepdolly.report.layout import LEFT, RIGHT, banner, pairs, table
from jeepdolly.report.revenue import month_of
from jeepdolly.store.history import Event, EventKind

__all__ = ["Month", "average_days", "by_month", "turnarounds", "workload_sheet"]


@dataclass(frozen=True, slots=True, order=True)
class Month:
    """One month of work at the counter."""

    key: str
    filed: int = 0
    issued: int = 0
    voided: int = 0
    referred: int = 0

    @property
    def taken(self) -> int:
        """Everything that came in."""
        return self.filed

    @property
    def done(self) -> int:
        """Everything that went out with a permit."""
        return self.issued

    def __str__(self) -> str:
        return f"{self.key}: {self.filed} filed, {self.issued} issued, {self.voided} voided"


_COUNTED = {
    EventKind.FILED: "filed",
    EventKind.ISSUED: "issued",
    EventKind.VOIDED: "voided",
    EventKind.REFERRED: "referred",
}


def by_month(journal: list[Event]) -> list[Month]:
    """The counter's work, a row per month, earliest first."""
    tally: dict[str, dict[str, int]] = defaultdict(lambda: dict.fromkeys(_COUNTED.values(), 0))
    for event in journal:
        field = _COUNTED.get(event.kind)
        if field is None:
            continue
        tally[month_of(event.day)][field] += 1
    return [Month(key=key, **tally[key]) for key in sorted(tally)]


def turnarounds(journal: list[Event]) -> dict[str, int]:
    """How many days each issued permit waited, by permit number.

    The application's filing day is found by following the journal: the issue
    line names the application it came from, and the filing line names the same
    application as its subject.
    """
    filed_on = {event.subject: event.day for event in journal if event.kind is EventKind.FILED}
    out: dict[str, int] = {}
    for event in journal:
        if event.kind is not EventKind.ISSUED:
            continue
        for word in event.detail.split():
            key = f"application {word}" if word.isdigit() else ""
            if key and key in filed_on:
                out[event.subject] = (event.day - filed_on[key]).days
                break
    return out


def average_days(waits: dict[str, int]) -> float:
    """The mean wait, or zero when nothing was issued."""
    if not waits:
        return 0.0
    return round(sum(waits.values()) / len(waits), 2)


def workload_sheet(journal: list[Event]) -> list[str]:
    """The whole workload return, ready to print."""
    months = by_month(journal)
    lines = banner("counter workload")
    if not months:
        lines.append("nothing has come through the counter")
        return lines
    lines.extend(
        table(
            ["month", "filed", "issued", "referred", "voided"],
            [
                [one.key, str(one.filed), str(one.issued), str(one.referred), str(one.voided)]
                for one in months
            ],
            aligns=[LEFT, RIGHT, RIGHT, RIGHT, RIGHT],
        )
    )
    waits = turnarounds(journal)
    lines.append("")
    lines.extend(
        pairs(
            [
                ("months", str(len(months))),
                ("filed", str(sum(one.filed for one in months))),
                ("issued", str(sum(one.issued for one in months))),
                ("measured", str(len(waits))),
                ("average days", f"{average_days(waits):.2f}"),
                ("slowest", str(max(waits.values())) if waits else "0"),
            ]
        )
    )
    return lines
