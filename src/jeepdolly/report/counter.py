"""What is sitting unanswered at the counter, and how far past the promise.

The sheet the supervisor reads on a Monday. It is sorted worst first and it does
not try to be kind: an application eleven working days over is at the top with
the number of days next to it, because the alternative the office tried was a
list in filing order, and nobody reading that noticed the one from March.

Only unanswered applications count. Something already decided is not late however
long it took, and it is the workload report's business rather than this one's.
"""

from __future__ import annotations

from jeepdolly.permit.application import Application
from jeepdolly.permit.promise import Standing, standing_of
from jeepdolly.report.layout import LEFT, RIGHT
from jeepdolly.report.sheet import Sheet
from jeepdolly.units.clock import Day, format_day, only_a_day

__all__ = ["late", "queue_sheet", "standings", "waiting"]


def standings(open_applications: list[tuple[int, Application]], on: Day) -> list[Standing]:
    """Where every unanswered application stands, worst first."""
    only_a_day(on)
    found = [standing_of(key, one, on) for key, one in open_applications]
    return sorted(found, reverse=True)


def late(open_applications: list[tuple[int, Application]], on: Day) -> list[Standing]:
    """Just the ones the office is past its promise on."""
    return [one for one in standings(open_applications, on) if one.late]


def waiting(open_applications: list[tuple[int, Application]], on: Day) -> list[Standing]:
    """Just the ones still inside the promise, soonest due first."""
    inside = [one for one in standings(open_applications, on) if not one.late]
    return sorted(inside, key=lambda one: (one.due, one.key))


def queue_sheet(open_applications: list[tuple[int, Application]], on: Day) -> list[str]:
    """The whole counter queue, ready to print."""
    over = late(open_applications, on)
    inside = waiting(open_applications, on)
    sheet = Sheet().title(f"counter queue as at {format_day(on)}")
    if not over and not inside:
        return sheet.note("nothing waiting").done()
    headings = ["key", "carrier", "kind", "filed", "promised", "days over"]
    aligns = [RIGHT, LEFT, LEFT, LEFT, LEFT, RIGHT]
    for name, batch in (("past the promise", over), ("still inside it", inside)):
        if not batch:
            continue
        sheet.section(name).rows(
            headings,
            [
                [
                    str(one.key),
                    one.carrier,
                    str(one.kind),
                    format_day(one.filed_on),
                    format_day(one.due),
                    str(one.over) if one.late else "",
                ]
                for one in batch
            ],
            aligns=aligns,
        )
    worst = over[0].over if over else 0
    return sheet.summary(
        [
            ("waiting", str(len(over) + len(inside))),
            ("past the promise", str(len(over))),
            ("worst", f"{worst} working days"),
        ]
    ).done()
