"""The call sheet: who to ring before a permit's load goes anywhere.

This is a working document rather than a record. A clerk prints it, works down
it, and rings the four owners on it. So the deadline column is the only thing
sorted on, and anything already past its deadline is called out at the top rather
than left in date order where it reads like just another row.

The sheet takes the day it is being worked as an argument, like every other
report here. A call sheet printed on the Friday and worked on the Monday is a
different sheet, and the office would rather reprint it than have somebody read
the Friday one and think there is still time.
"""

from __future__ import annotations

import datetime as dt

from jeepdolly.errors import BadValueError
from jeepdolly.report.layout import LEFT, RIGHT
from jeepdolly.report.sheet import Sheet
from jeepdolly.route.notice import Notice
from jeepdolly.units.clock import Day, format_day

__all__ = ["late", "notice_sheet", "still_time"]


def _day(on: Day) -> Day:
    """Refuse anything that is not a plain date."""
    if not isinstance(on, dt.date) or isinstance(on, dt.datetime):
        raise BadValueError("day", on, "want a date")
    return on


def late(notices: list[Notice], on: Day) -> list[Notice]:
    """The calls whose deadline has already gone, longest gone first."""
    return sorted(one for one in notices if one.late_on(_day(on)))


def still_time(notices: list[Notice], on: Day) -> list[Notice]:
    """The calls that can still be made in time, soonest first."""
    return sorted(one for one in notices if not one.late_on(_day(on)))


def notice_sheet(notices: list[Notice], on: Day, number: str = "") -> list[str]:
    """The whole call sheet, ready to print."""
    missed = late(notices, on)
    ahead = still_time(notices, on)
    title = f"notice list for {number}" if number else "notice list"
    sheet = Sheet().title(f"{title} as at {format_day(on)}")
    if not notices:
        return sheet.note("nobody has to be told about this one").done()
    headings = ["tell by", "days", "owner", "where"]
    aligns = [LEFT, RIGHT, LEFT, LEFT]
    for name, batch in (("already late", missed), ("still time", ahead)):
        if not batch:
            continue
        sheet.section(name).rows(
            headings,
            [
                [
                    format_day(one.tell_by),
                    str((one.tell_by - on).days),
                    one.owner,
                    place,
                ]
                for one in batch
                for place in one.places
            ],
            aligns=aligns,
        )
    return sheet.summary(
        [
            ("calls to make", str(len(notices))),
            ("already late", str(len(missed))),
        ]
    ).done()
