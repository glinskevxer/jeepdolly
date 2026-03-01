"""Splitting a run into the days it will actually take.

A permit says the load may move over a span of days and the schedule says which
hours of each of those days it may move in. What the carrier wants to know is
where the truck will be each night, and that is neither of those: it is the route
laid over the hours at whatever speed the load can be moved.

Two rules make this different from dividing distance by speed.

A leg is not started unless it can be finished. An oversize load cannot be left
on the shoulder at dusk, so a stretch that will not fit in what is left of the
day waits until the morning. That is what makes the answer lumpy and it is why
the last stage of a run is often nearly empty.

A stage ends at a junction. The office writes the overnight stop into the permit
and a junction is somewhere the driver can be told to be.

Speed is a single figure per run rather than per stretch. A permit load moves at
whatever the escort can hold, and the office has never had a reason to model it
more finely than that.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal

from jeepdolly.errors import BadValueError
from jeepdolly.ids.reference import Code
from jeepdolly.route.plan import Leg, Route
from jeepdolly.travel.schedule import Schedule
from jeepdolly.units.clock import Day, format_day
from jeepdolly.units.distance import Miles, format_distance, hundredths, to_miles

__all__ = ["DEFAULT_SPEED", "MAX_SPEED", "Stage", "Staging", "minutes_for", "stage_run"]

#: How fast the office assumes a permit load moves, in miles an hour.
DEFAULT_SPEED = 35

#: Above this the figure is a typo rather than a haul speed.
MAX_SPEED = 70


def minutes_for(distance: Miles, speed: int) -> int:
    """How long a distance takes at a speed, rounded up to the whole minute."""
    if isinstance(speed, bool) or not isinstance(speed, int):
        raise BadValueError("speed", speed, "want a whole number of miles an hour")
    if not 1 <= speed <= MAX_SPEED:
        raise BadValueError("speed", speed, f"want 1 to {MAX_SPEED}")
    exact = to_miles(distance) * 60 / Decimal(speed)
    return int(exact.to_integral_value(rounding=ROUND_CEILING))


@dataclass(frozen=True, slots=True)
class Stage:
    """One day of a run, and where it ends."""

    day: Day
    legs: tuple[Leg, ...]
    minutes: int

    @property
    def distance(self) -> Miles:
        """How far the truck moves on this day."""
        return hundredths(sum(int(leg.distance) for leg in self.legs))

    @property
    def moving(self) -> bool:
        """Does the truck move at all on this day."""
        return bool(self.legs)

    @property
    def ends_at(self) -> Code | None:
        """The junction the truck stops at, or nothing if it did not move."""
        return self.legs[-1].to_node if self.legs else None

    def __str__(self) -> str:
        if not self.legs:
            return f"{format_day(self.day)} no movement"
        return (
            f"{format_day(self.day)} {format_distance(self.distance)}"
            f" to {self.ends_at} in {self.minutes} minutes"
        )


@dataclass(frozen=True, slots=True)
class Staging:
    """A whole run split into days."""

    route: Route
    speed: int
    stages: tuple[Stage, ...]
    left_over: tuple[Leg, ...]

    @property
    def finished(self) -> bool:
        """Does the run get there inside the permit's days."""
        return not self.left_over

    @property
    def days(self) -> int:
        """How many days the truck actually moves on."""
        return sum(1 for stage in self.stages if stage.moving)

    @property
    def minutes(self) -> int:
        """Total driving time across the run."""
        return sum(stage.minutes for stage in self.stages)

    @property
    def covered(self) -> Miles:
        """How far the truck gets."""
        return hundredths(sum(int(stage.distance) for stage in self.stages))

    @property
    def stops(self) -> tuple[Code, ...]:
        """The overnight stops, in order."""
        return tuple(stage.ends_at for stage in self.stages if stage.ends_at is not None)

    def __str__(self) -> str:
        if self.finished:
            return (
                f"{self.route.origin} to {self.route.destination} in {self.days} days"
                f" at {self.speed} mph"
            )
        return (
            f"{self.route.origin} to {self.route.destination}:"
            f" {len(self.left_over)} legs do not fit in the permit"
        )


def stage_run(route: Route, schedule: Schedule, speed: int = DEFAULT_SPEED) -> Staging:
    """Lay a route over a schedule and say where the truck stops each night."""
    if not isinstance(schedule, Schedule):
        raise BadValueError("schedule", schedule, "want a schedule")
    minutes_for(hundredths(0), speed)
    remaining = list(route.legs)
    stages: list[Stage] = []
    for plan in schedule.days:
        spare = plan.minutes
        taken: list[Leg] = []
        spent = 0
        while remaining:
            need = minutes_for(remaining[0].distance, speed)
            if need > spare:
                break
            taken.append(remaining.pop(0))
            spare -= need
            spent += need
        stages.append(Stage(day=plan.day, legs=tuple(taken), minutes=spent))
        if not remaining:
            break
    return Staging(route=route, speed=speed, stages=tuple(stages), left_over=tuple(remaining))
