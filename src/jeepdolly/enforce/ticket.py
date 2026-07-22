"""A weight ticket off a portable scale, checked against what was permitted.

Enforcement weighs an axle at a time on a set of portable pads, so a ticket is a
list of axle weights and not a gross. The gross is the sum, and working it out
here rather than taking it off the ticket is deliberate: the officer's own gross
figure and the sum of their axle figures disagree often enough that the office
would rather see the disagreement than pick one.

What the ticket is compared against is the permit, not the statute. That is the
whole point of enforcement on a permitted move. A rig thirty thousand pounds over
the statutory limit and inside its permit is fine, and the same rig two hundred
pounds outside its permit is not, however far under the statute it is.

Three ways a ticket comes back wrong and they are different findings, because
they are three different conversations with the carrier. The rig is heavier than
the permit allowed. The axles are in different places than the permit described.
Or the load is not the load on the permit at all, which is the one that ends with
the permit being pulled.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from enum import StrEnum

from jeepdolly.errors import BadValueError
from jeepdolly.ids.reference import Serial, serial
from jeepdolly.rig.config import Configuration
from jeepdolly.units.clock import Day, format_day
from jeepdolly.units.mass import MAX_POUNDS, Pounds, format_weight, pounds

__all__ = [
    "AXLE_TOLERANCE",
    "GROSS_TOLERANCE",
    "MAX_AXLES",
    "Discrepancy",
    "Overage",
    "Ticket",
    "check_ticket",
    "worst_axle",
]

#: How far one axle may be out before it is worth writing down. Portable pads on
#: a road with any camber are simply not better than this.
AXLE_TOLERANCE = pounds(500)

#: How far the whole rig may be out. Tighter than the axle figure by design: the
#: pad errors are as likely to cancel as to add, so a gross that is out is out.
GROSS_TOLERANCE = pounds(1_000)

MAX_AXLES = 13


class Discrepancy(StrEnum):
    """What a weight ticket disagrees with the permit about."""

    GROSS = "gross over permit"
    AXLE = "axle over permit"
    COUNT = "different number of axles"
    UNDER = "lighter than permitted"


@dataclass(frozen=True, slots=True)
class Ticket:
    """One rig on a set of portable pads, at one place, on one day."""

    number: Serial
    permit: Serial
    weighed_on: Day
    place: str
    officer: str
    axles: tuple[Pounds, ...]

    def __post_init__(self) -> None:
        for name in ("number", "permit"):
            object.__setattr__(self, name, serial(str(getattr(self, name))))
        if not isinstance(self.weighed_on, dt.date) or isinstance(self.weighed_on, dt.datetime):
            raise BadValueError("weighed on", self.weighed_on, "want a date")
        for name in ("place", "officer"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise BadValueError(name, value, "want some text")
            object.__setattr__(self, name, " ".join(value.split()))
        weights = tuple(pounds(int(one)) for one in self.axles)
        object.__setattr__(self, "axles", weights)
        if not 1 <= len(weights) <= MAX_AXLES:
            raise BadValueError("axles", len(weights), f"want 1 to {MAX_AXLES}")
        for position, weight in enumerate(weights, start=1):
            if int(weight) <= 0:
                raise BadValueError(f"axle {position}", int(weight), "want some weight")
            if int(weight) > MAX_POUNDS:
                raise BadValueError(f"axle {position}", int(weight), "heavier than anything")

    @property
    def gross(self) -> Pounds:
        """The whole rig, added up from the pads rather than read off a scale."""
        return pounds(sum(int(one) for one in self.axles))

    @property
    def count(self) -> int:
        """How many axles were weighed."""
        return len(self.axles)

    def heaviest(self) -> tuple[int, Pounds]:
        """Which axle was heaviest, and by how much, counting from one."""
        best = max(range(self.count), key=lambda i: int(self.axles[i]))
        return best + 1, self.axles[best]

    def __str__(self) -> str:
        return (
            f"{self.number} against {self.permit} at {self.place}"
            f" {format_day(self.weighed_on)}: {format_weight(self.gross)}"
        )


@dataclass(frozen=True, slots=True, order=True)
class Overage:
    """One thing a ticket is over the permit by."""

    kind: Discrepancy
    subject: str
    over: Pounds

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", Discrepancy(self.kind))
        object.__setattr__(self, "over", pounds(int(self.over)))
        if not isinstance(self.subject, str) or not self.subject.strip():
            raise BadValueError("subject", self.subject, "want some text")
        object.__setattr__(self, "subject", " ".join(self.subject.split()))

    def __str__(self) -> str:
        if int(self.over) == 0:
            return f"{self.subject}: {self.kind}"
        return f"{self.subject}: {self.kind} by {format_weight(self.over)}"


def worst_axle(ticket: Ticket, config: Configuration) -> Overage | None:
    """The axle furthest over what the permit's rig said it would weigh.

    Compared axle by axle in order. A rig with its axles in a different order
    from the permit is not this function's problem, and pairing them up by weight
    to be helpful would hide exactly the case enforcement is looking for.
    """
    if not isinstance(config, Configuration):
        raise BadValueError("configuration", config, "want a rig")
    if ticket.count != len(config.axles):
        return None
    found: Overage | None = None
    for position, (weighed, declared) in enumerate(
        zip(ticket.axles, config.axles, strict=False), start=1
    ):
        over = int(weighed) - int(declared.weight)
        if over <= int(AXLE_TOLERANCE):
            continue
        if found is None or over > int(found.over):
            found = Overage(
                kind=Discrepancy.AXLE, subject=f"axle {position}", over=pounds(over)
            )
    return found


def check_ticket(ticket: Ticket, config: Configuration, permitted: Pounds) -> list[Overage]:
    """Everything one weight ticket disagrees with its permit about.

    An axle count that does not match is reported on its own and stops the axle
    comparison, because comparing five weighed axles against six permitted ones
    position by position produces five findings that all say the same thing.
    """
    if not isinstance(ticket, Ticket):
        raise BadValueError("ticket", ticket, "want a ticket")
    if not isinstance(config, Configuration):
        raise BadValueError("configuration", config, "want a rig")
    allowed = pounds(int(permitted))
    found: list[Overage] = []
    if ticket.count != len(config.axles):
        found.append(
            Overage(
                kind=Discrepancy.COUNT,
                subject=f"{ticket.count} axles weighed",
                over=pounds(0),
            )
        )
    over_gross = int(ticket.gross) - int(allowed)
    if over_gross > int(GROSS_TOLERANCE):
        found.append(Overage(kind=Discrepancy.GROSS, subject="gross", over=pounds(over_gross)))
    elif over_gross < -int(allowed) // 4:
        found.append(Overage(kind=Discrepancy.UNDER, subject="gross", over=pounds(-over_gross)))
    axle = worst_axle(ticket, config)
    if axle is not None:
        found.append(axle)
    return found
