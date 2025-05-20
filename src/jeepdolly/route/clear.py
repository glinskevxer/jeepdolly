"""Walking a route with a rig on it.

Two different questions get answered here and they are kept apart on purpose.

The first is about the road surface: what may this rig weigh on this class of
road. That is the flat limits and the bridge formula, and the answer is the same
for every stretch of the same class, so it is worked out once per class and not
once per leg.

The second is about the individual things in the way: a posted bridge, a low
overhead, a local gross order. Those are per leg and they are nearly always
refusals rather than fees.

A route report holds both, keeps the leg each finding came from, and adds
nothing up. The permit desk does the adding.
"""

from __future__ import annotations

from dataclasses import dataclass

from jeepdolly.limits.assess import Assessment, assess
from jeepdolly.limits.dimension import LEGAL, SizeRule
from jeepdolly.limits.finding import Finding, Severity, excess_of, worst
from jeepdolly.rig.config import Configuration
from jeepdolly.rig.load import Load
from jeepdolly.roadway.network import Network
from jeepdolly.roadway.segment import RoadClass, statute_for
from jeepdolly.route.plan import Leg, Route
from jeepdolly.units.length import Inches
from jeepdolly.units.mass import Pounds, format_weight

__all__ = ["LegReport", "RouteReport", "check_leg", "walk"]


def check_leg(leg: Leg, network: Network, gross: Pounds, height: Inches) -> list[Finding]:
    """What one stretch has to say about one rig.

    Only the things that belong to the stretch itself: the local gross order and
    whatever is built on it. The statutory limits are handled once per road
    class rather than here.
    """
    found: list[Finding] = []
    segment = leg.segment
    if segment.posted and int(gross) > int(segment.gross_limit):
        found.append(
            Finding(
                rule="local-order",
                subject=f"{segment.code} {segment.route}",
                severity=Severity.REFUSE,
                detail=(
                    f"posted at {format_weight(segment.gross_limit)} and the rig"
                    f" grosses {format_weight(gross)}"
                ),
            )
        )
    for structure in network.structures_on(str(segment.code)):
        found.extend(structure.check(height, gross))
    return found


@dataclass(frozen=True, slots=True)
class LegReport:
    """One leg and everything it had to say."""

    leg: Leg
    findings: tuple[Finding, ...]

    @property
    def clear(self) -> bool:
        """Did the leg raise nothing at all."""
        return not self.findings

    @property
    def blocked(self) -> bool:
        """Is there something on this leg no permit can fix."""
        return any(f.blocking for f in self.findings)

    def __str__(self) -> str:
        if self.clear:
            return f"{self.leg} clear"
        return f"{self.leg} {len(self.findings)} findings"


@dataclass(frozen=True, slots=True)
class RouteReport:
    """A whole route walked with one rig and one load."""

    route: Route
    legs: tuple[LegReport, ...]
    surfaces: tuple[tuple[RoadClass, Assessment], ...]

    @property
    def leg_findings(self) -> tuple[Finding, ...]:
        """Everything the individual stretches raised, in order."""
        return tuple(f for report in self.legs for f in report.findings)

    @property
    def surface_findings(self) -> tuple[Finding, ...]:
        """Everything the road classes raised, worst class first."""
        return tuple(f for _, seen in self.surfaces for f in seen.findings)

    @property
    def findings(self) -> tuple[Finding, ...]:
        """Everything, stretches first."""
        return self.leg_findings + self.surface_findings

    @property
    def severity(self) -> Severity:
        """The worst thing found anywhere on the route."""
        return worst(self.findings)

    @property
    def blocked(self) -> bool:
        """Is there anything no permit can fix."""
        return any(f.blocking for f in self.findings)

    @property
    def blockers(self) -> tuple[Finding, ...]:
        """The findings that stop a permit being written."""
        return tuple(f for f in self.findings if f.blocking)

    @property
    def excess(self) -> Pounds:
        """The largest single billable overage on the route."""
        return excess_of(self.findings)

    @property
    def clear(self) -> bool:
        """Could this run be made with no permit at all."""
        return all(f.severity is Severity.NOTE for f in self.findings)

    @property
    def classes(self) -> tuple[RoadClass, ...]:
        """Which classes of road the route uses."""
        return tuple(road_class for road_class, _ in self.surfaces)

    def leg_at(self, index: int) -> LegReport:
        """One leg's report by position."""
        return self.legs[index]

    def __str__(self) -> str:
        return f"{self.route}: {len(self.findings)} findings, worst {self.severity}"


def walk(
    route: Route,
    network: Network,
    config: Configuration,
    load: Load,
    size_rule: SizeRule = LEGAL,
) -> RouteReport:
    """Take a rig and load over a route and report everything found."""
    gross = config.gross
    reports = tuple(
        LegReport(leg=leg, findings=tuple(check_leg(leg, network, gross, load.height)))
        for leg in route.legs
    )
    seen: list[RoadClass] = []
    for leg in route.legs:
        if leg.segment.road_class not in seen:
            seen.append(leg.segment.road_class)
    surfaces = tuple(
        (road_class, assess(config, load, statute_for(road_class), size_rule))
        for road_class in sorted(seen, key=str)
    )
    return RouteReport(route=route, legs=reports, surfaces=surfaces)
