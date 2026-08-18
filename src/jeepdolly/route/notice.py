"""Who has to be rung before an overheight load goes past their gear.

A permit is not the only permission a move needs. The power company owns the
line over the crossing at milepost eight and wants three days to send somebody
out with a pole. The railway owns the bridge at fourteen and wants ten, because
they have to book a track window to have anybody standing near it. Neither of
them hears about the move from the permit, and neither of them is happy about
finding out from the driver.

Three rules, and the third is the one worth reading.

Notice is wanted when the load comes within a margin of the clearance, not when
it will not fit. A load two inches under a wire clears on paper and does not
clear in a wind, and the owner is the one who decides that, not the office.

The lead time is the owner's own figure, and the deadline is the first travel day
less that many days.

And then: one owner rung once. A route with four of the same utility's crossings
is one phone call with four locations on it, made against the earliest of the
four deadlines. Working that out per structure produced a call list where the
same lineman was rung four times with three different dates, which is how the
office learned to do it this way.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from jeepdolly.errors import BadValueError
from jeepdolly.roadway.structure import Structure
from jeepdolly.route.plan import Route
from jeepdolly.units.clock import Day, format_day, only_a_day
from jeepdolly.units.length import Inches, format_length, inches

__all__ = ["MARGIN", "Notice", "notices_for", "wants_notice_of"]

#: How close to a posted clearance a load has to come before the owner is rung.
MARGIN = inches(6)


def wants_notice_of(structure: Structure, height: Inches, margin: Inches = MARGIN) -> bool:
    """Does this structure's owner have to be told about a load this tall.

    A structure with nobody on file wants nothing, whatever the height. That is
    not the same as nothing being there: it means the office does not know who
    owns it, which is a gap in the map rather than a clear road.
    """
    if not isinstance(structure, Structure):
        raise BadValueError("structure", structure, "want a structure")
    if not structure.wants_notice or structure.clearance is None:
        return False
    return int(height) + int(inches(int(margin))) >= int(structure.clearance)


@dataclass(frozen=True, slots=True, order=True)
class Notice:
    """One phone call, and everything on the route it covers."""

    tell_by: Day
    owner: str
    lead_days: int
    places: tuple[str, ...]

    def __post_init__(self) -> None:
        only_a_day(self.tell_by, "tell by")
        if not isinstance(self.owner, str) or not self.owner.strip():
            raise BadValueError("owner", self.owner, "want some text")
        object.__setattr__(self, "owner", " ".join(self.owner.split()))
        if isinstance(self.lead_days, bool) or not isinstance(self.lead_days, int):
            raise BadValueError("lead days", self.lead_days, "want a whole number")
        if self.lead_days < 1:
            raise BadValueError("lead days", self.lead_days, "a notice wants some warning")
        object.__setattr__(self, "places", tuple(self.places))
        if not self.places:
            raise BadValueError("places", self.owner, "a notice covers something")

    def late_on(self, day: Day) -> bool:
        """Would giving this notice on a day already be too late."""
        only_a_day(day, "day")
        return day > self.tell_by

    def __str__(self) -> str:
        where = ", ".join(self.places)
        return f"tell {self.owner} by {format_day(self.tell_by)}: {where}"


def notices_for(
    route: Route,
    structures: Mapping[str, Sequence[Structure]],
    height: Inches,
    first_day: Day,
    margin: Inches = MARGIN,
) -> list[Notice]:
    """Every call that has to be made before this load travels this route.

    ``structures`` is keyed by segment code, which is how the network hands them
    over, and takes any mapping of sequences so the store's tuples go straight
    in. One notice per owner, at the earliest deadline any of their structures
    puts on it, with the places listed in the order the rig meets them.
    """
    if not isinstance(route, Route):
        raise BadValueError("route", route, "want a route")
    only_a_day(first_day, "first day")
    wanted: dict[str, tuple[int, list[str]]] = {}
    for leg in route.legs:
        for structure in structures.get(str(leg.segment.code), []):
            if not wants_notice_of(structure, height, margin):
                continue
            lead, places = wanted.get(structure.owner, (0, []))
            where = (
                f"{structure.name} on {leg.segment.route}"
                f" ({format_length(structure.clearance or inches(1))})"
            )
            if where not in places:
                places.append(where)
            wanted[structure.owner] = (max(lead, structure.notice_days), places)
    return sorted(
        Notice(
            tell_by=first_day - dt.timedelta(days=lead),
            owner=owner,
            lead_days=lead,
            places=tuple(places),
        )
        for owner, (lead, places) in wanted.items()
    )
