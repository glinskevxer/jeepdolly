"""One axle.

Everything the limits care about is here: what it carries, how many tires it
carries it on, and how wide those tires are. Tire width matters because a state
that lets a single axle run twenty thousand pounds on eight tires will not let
it run the same weight on four, and the office refuses those on the ticket
rather than at the scale.

An axle is a value. It does not know its position in the rig and it does not
know the spacing to its neighbour, because both of those belong to the
arrangement rather than to the part.
"""

from __future__ import annotations

from dataclasses import dataclass

from jeepdolly.errors import BadValueError
from jeepdolly.units.length import Inches, inches
from jeepdolly.units.mass import Pounds, format_weight, pounds

__all__ = [
    "MAX_TIRES",
    "NARROW_TIRE",
    "POUNDS_PER_TIRE_INCH",
    "STEER_TIRES",
    "Axle",
]

#: A steer axle carries two tires and is the only axle allowed to.
STEER_TIRES = 2

#: Nothing the office has seen carries more than this on one axle.
MAX_TIRES = 16

#: A tire narrower than this is treated as a narrow tire for the width rule.
NARROW_TIRE = inches(11)

#: The width rule. Six hundred pounds per inch of tire tread across the axle.
POUNDS_PER_TIRE_INCH = 600


@dataclass(frozen=True, slots=True)
class Axle:
    """A single axle with its load and its rubber.

    ``liftable`` axles are the ones a driver can raise. They count toward the
    limits only while they are down, and the office writes the permit for the
    rig as presented, so a liftable axle that is down at the scale is an axle
    like any other. The flag is carried so a later amendment can tell which
    axles the carrier could drop.
    """

    weight: Pounds
    tires: int
    tire_width: Inches
    liftable: bool = False
    steering: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "weight", pounds(int(self.weight)))
        object.__setattr__(self, "tire_width", inches(int(self.tire_width)))
        if isinstance(self.tires, bool) or not isinstance(self.tires, int):
            raise BadValueError("tires", self.tires, "want a whole number")
        if not 1 <= self.tires <= MAX_TIRES:
            raise BadValueError("tires", self.tires, f"want 1 to {MAX_TIRES}")
        if int(self.tire_width) < 1:
            raise BadValueError("tire width", self.tire_width, "want at least one inch")
        if self.steering and self.tires != STEER_TIRES:
            raise BadValueError("tires", self.tires, "a steer axle carries two")
        if self.steering and self.liftable:
            raise BadValueError("axle", "steering", "a steer axle does not lift")

    @property
    def tread(self) -> Inches:
        """Total tire tread across the axle."""
        return inches(self.tires * int(self.tire_width))

    @property
    def narrow(self) -> bool:
        """Is this running tires the office calls narrow."""
        return int(self.tire_width) < int(NARROW_TIRE)

    @property
    def tire_limit(self) -> Pounds:
        """The most this axle may carry on the rubber it has."""
        return pounds(self.tires * int(self.tire_width) * POUNDS_PER_TIRE_INCH)

    @property
    def over_tires(self) -> bool:
        """Is the axle heavier than its rubber allows."""
        return int(self.weight) > int(self.tire_limit)

    def reloaded(self, weight: Pounds) -> Axle:
        """The same axle carrying a different weight."""
        return Axle(
            weight=weight,
            tires=self.tires,
            tire_width=self.tire_width,
            liftable=self.liftable,
            steering=self.steering,
        )

    def __str__(self) -> str:
        kind = "steer" if self.steering else ("lift" if self.liftable else "fixed")
        # Tire width is always spoken in plain inches, never in feet and
        # inches, so it does not go through the length formatter.
        return f'{kind} {format_weight(self.weight)} on {self.tires} at {int(self.tire_width)}"'
