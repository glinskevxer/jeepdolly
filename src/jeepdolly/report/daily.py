"""The day sheet: what is moving today and when it may move.

This is the report the office prints at seven in the morning and pins to the
wall. It lists every permit good today, what it is carrying, and the hours the
load may actually be on the road once the daylight rule and the embargoes have
been applied.

The hours are per county, and a permit whose route crosses three counties gets
three lines. That looks redundant on the page and it is exactly what a dispatcher
needs, because the rush hour restriction in one of them is the reason the load
leaves at ten instead of seven.
"""

from __future__ import annotations

from dataclasses import dataclass

from jeepdolly.almanac.embargo import EmbargoBook
from jeepdolly.permit.permit import Permit
from jeepdolly.report.layout import LEFT, RIGHT
from jeepdolly.report.sheet import Sheet
from jeepdolly.roadway.network import Network
from jeepdolly.route.search import shortest
from jeepdolly.travel.window import ORDINARY, TravelRule, travel_windows
from jeepdolly.units.clock import Day, Window, format_day
from jeepdolly.units.length import format_length
from jeepdolly.units.mass import format_weight

__all__ = ["Movement", "counties_of", "day_sheet", "movements"]


def counties_of(permit: Permit, network: Network) -> tuple[str, ...]:
    """Every county the permit's route passes through, in order, once each.

    An annual permit has no route and so has no counties. It is reported
    statewide, which is what the permit actually says.
    """
    application = permit.application
    if not application.routed:
        return ()
    seen: list[str] = []
    for node_code in _route_nodes(permit, network):
        county = network.node(str(node_code)).county
        if county not in seen:
            seen.append(county)
    return tuple(seen)


def _route_nodes(permit: Permit, network: Network) -> tuple[str, ...]:
    """The junctions the permit touches, taken from the stored route ends.

    The office does not store the route on the permit, only its two ends and the
    distance, so this walks the map for the shortest way between them. That is
    an approximation and the day sheet says so in its heading.
    """
    application = permit.application
    assert application.origin is not None
    assert application.destination is not None
    route = shortest(network, str(application.origin), str(application.destination))
    if route is None:
        return (str(application.origin), str(application.destination))
    return tuple(str(node) for node in route.nodes)


@dataclass(frozen=True, slots=True)
class Movement:
    """One permit on one day in one county."""

    permit: Permit
    county: str
    windows: tuple[Window, ...]

    @property
    def blocked(self) -> bool:
        """Is there no hour at all the load may move here today."""
        return not self.windows

    @property
    def hours(self) -> str:
        """The windows as one printable field."""
        if not self.windows:
            return "no movement"
        return ", ".join(str(w) for w in self.windows)


def movements(
    permits: list[Permit],
    day: Day,
    network: Network,
    book: EmbargoBook,
    rule: TravelRule = ORDINARY,
) -> list[Movement]:
    """Every permit good on a day, split out by county."""
    out: list[Movement] = []
    for permit in permits:
        if not permit.good_on(day):
            continue
        counties = counties_of(permit, network) or ("statewide",)
        for county in counties:
            out.append(
                Movement(
                    permit=permit,
                    county=county,
                    windows=travel_windows(permit.application.load, day, county, book, rule),
                )
            )
    return out


def day_sheet(
    permits: list[Permit],
    day: Day,
    network: Network,
    book: EmbargoBook,
    rule: TravelRule = ORDINARY,
) -> list[str]:
    """The whole day sheet, ready to print."""
    found = movements(permits, day, network, book, rule)
    sheet = Sheet().title(f"movement sheet for {format_day(day)}")
    if not found:
        return sheet.note("nothing moving").done()
    sheet.rows(
        ["permit", "carrier", "county", "weight", "width", "hours"],
        [
            [
                str(m.permit.number),
                m.permit.carrier,
                m.county,
                format_weight(m.permit.application.load.weight),
                format_length(m.permit.application.load.width),
                m.hours,
            ]
            for m in found
        ],
        aligns=[LEFT, LEFT, LEFT, RIGHT, RIGHT, LEFT],
    )
    stopped = [m for m in found if m.blocked]
    return sheet.summary(
        [("movements", str(len(found))), ("stopped", str(len(stopped)))]
    ).done()
