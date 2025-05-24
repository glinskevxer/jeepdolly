"""Which hours of a given day a load may actually move.

The answer starts as one window, usually daylight, and then has holes cut in it
by whatever embargoes are in force. Cutting holes needs the windows flattened
into plain minute intervals first, because a window that wraps past midnight is
two intervals and subtracting from it while it is still one is where this sort of
code goes wrong.

The daylight table is the office's own and is a month by month approximation, not
an ephemeris. It is deliberately conservative: half an hour later in the morning
and half an hour earlier in the evening than the almanac says, which is the
allowance the statute already builds in.
"""

from __future__ import annotations

from dataclasses import dataclass

from jeepdolly.almanac.embargo import EmbargoBook
from jeepdolly.errors import BadValueError
from jeepdolly.rig.load import Load
from jeepdolly.units.clock import MINUTES_PER_DAY, WEEKEND, Day, Window
from jeepdolly.units.length import Inches, feet, inches

__all__ = [
    "DAYLIGHT",
    "ORDINARY",
    "TravelRule",
    "daylight_on",
    "movable",
    "spans_of",
    "subtract",
    "travel_windows",
]

#: Roughly sunrise plus thirty minutes to sunset less thirty, by month.
DAYLIGHT: dict[int, Window] = {
    1: Window(8 * 60 + 20, 16 * 60 + 40),
    2: Window(7 * 60 + 50, 17 * 60 + 30),
    3: Window(7 * 60 + 30, 19 * 60 + 20),
    4: Window(6 * 60 + 40, 20 * 60 + 10),
    5: Window(6 * 60, 20 * 60 + 50),
    6: Window(5 * 60 + 40, 21 * 60 + 20),
    7: Window(5 * 60 + 50, 21 * 60 + 10),
    8: Window(6 * 60 + 30, 20 * 60 + 20),
    9: Window(7 * 60 + 10, 19 * 60 + 20),
    10: Window(7 * 60 + 50, 18 * 60 + 20),
    11: Window(7 * 60 + 30, 16 * 60 + 50),
    12: Window(8 * 60 + 10, 16 * 60 + 20),
}


def spans_of(window: Window) -> tuple[tuple[int, int], ...]:
    """Flatten a window into one or two plain half open minute intervals."""
    if window.empty:
        return ()
    if not window.wraps:
        return ((window.start, window.end),)
    return ((window.start, MINUTES_PER_DAY), (0, window.end))


def subtract(base: Window, cuts: tuple[Window, ...]) -> tuple[Window, ...]:
    """Everything in ``base`` that is in none of ``cuts``, earliest first.

    The result never wraps. A window that ran past midnight comes back as two,
    which is what a driver needs: they are two separate chances to move.
    """
    remaining = list(spans_of(base))
    for cut in cuts:
        for hole_start, hole_end in spans_of(cut):
            kept: list[tuple[int, int]] = []
            for start, end in remaining:
                if hole_end <= start or hole_start >= end:
                    kept.append((start, end))
                    continue
                if start < hole_start:
                    kept.append((start, hole_start))
                if hole_end < end:
                    kept.append((hole_end, end))
            remaining = kept
    return tuple(
        Window(start, end % MINUTES_PER_DAY) for start, end in sorted(remaining) if end > start
    )


def daylight_on(day: Day) -> Window:
    """The daylight window for the month this day falls in."""
    return DAYLIGHT[day.month]


@dataclass(frozen=True, slots=True)
class TravelRule:
    """The widths and lengths at which the hours start being restricted."""

    name: str
    daylight_width: Inches
    daylight_length: Inches
    no_weekend_width: Inches

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise BadValueError("name", self.name, "want some text")
        for field in ("daylight_width", "daylight_length", "no_weekend_width"):
            object.__setattr__(self, field, inches(int(getattr(self, field))))
        if int(self.no_weekend_width) < int(self.daylight_width):
            raise BadValueError(
                "no weekend width", self.no_weekend_width, "below the daylight width"
            )

    def daylight_only(self, load: Load) -> bool:
        """Is this load held to daylight hours."""
        return int(load.width) > int(self.daylight_width) or int(load.overall_length) > int(
            self.daylight_length
        )

    def weekday_only(self, load: Load) -> bool:
        """Is this load held to weekdays."""
        return int(load.width) > int(self.no_weekend_width)


#: The office's standing travel rule.
ORDINARY = TravelRule(
    name="ordinary",
    daylight_width=inches(120),
    daylight_length=feet(90),
    no_weekend_width=feet(14),
)


def travel_windows(
    load: Load,
    day: Day,
    county: str,
    book: EmbargoBook,
    rule: TravelRule = ORDINARY,
) -> tuple[Window, ...]:
    """Every stretch of this day the load may move, earliest first."""
    if rule.weekday_only(load) and day.weekday() in WEEKEND:
        return ()
    # A load with no daylight restriction may run the whole day. The window is
    # written to the last minute rather than wrapping to midnight, because a
    # window whose start equals its end is the empty one.
    base = daylight_on(day) if rule.daylight_only(load) else Window(0, MINUTES_PER_DAY - 1)
    cuts = tuple(e.window for e in book.on_day(day, county) if e.window is not None)
    whole_days = tuple(e for e in book.on_day(day, county) if e.window is None)
    if whole_days:
        return ()
    return subtract(base, cuts)


def movable(
    load: Load,
    day: Day,
    county: str,
    book: EmbargoBook,
    rule: TravelRule = ORDINARY,
) -> bool:
    """Is there any hour of this day the load may move."""
    return bool(travel_windows(load, day, county, book, rule))
