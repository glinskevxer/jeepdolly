"""A stocked office and one issued permit for the report suite."""

import datetime as dt
from collections.abc import Iterator

import pytest

from jeepdolly.party.carrier import Carrier
from jeepdolly.permit.application import Application, Kind
from jeepdolly.permit.desk import Desk
from jeepdolly.permit.permit import Permit
from jeepdolly.rig.axle import Axle
from jeepdolly.rig.config import Configuration
from jeepdolly.rig.load import Load
from jeepdolly.roadway.node import Node
from jeepdolly.roadway.segment import Segment
from jeepdolly.roadway.structure import Structure, StructureKind
from jeepdolly.store.office import Office, opened_new_office
from jeepdolly.units.clock import DaySpan
from jeepdolly.units.distance import miles
from jeepdolly.units.length import feet, feet_inches, inches
from jeepdolly.units.mass import pounds

FILED = dt.date(2025, 6, 16)
DECIDED = dt.date(2025, 6, 17)
TRIP = DaySpan(dt.date(2025, 6, 18), dt.date(2025, 6, 20))


def a_load(**over: object) -> Load:
    kw: dict[str, object] = {
        "description": "step-up transformer",
        "weight": pounds(148000),
        "width": feet_inches(12, 6),
        "height": feet_inches(14, 2),
        "length": feet(48),
        "divisible": False,
        "reason": "single-piece",
    }
    kw.update(over)
    return Load(**kw)  # type: ignore[arg-type]


def an_application(**over: object) -> Application:
    kw: dict[str, object] = {
        "carrier": "VANCE",
        "rig": "R-00001",
        "load": a_load(),
        "span": TRIP,
        "filed_on": FILED,
        "kind": Kind.TRIP,
        "origin": "JCT-A",
        "destination": "JCT-D",
    }
    kw.update(over)
    return Application(**kw)  # type: ignore[arg-type]


def stock(office: Office) -> None:
    """Put a carrier, a rig and the corridor map on a fresh office."""
    office.carriers.add(
        Carrier(code="VANCE", name="Vance Heavy Haul", usdot=1184062, home_state="MT")  # type: ignore[arg-type]
    )
    office.rigs.add(
        "VANCE",
        Configuration(
            name="3S2",  # type: ignore[arg-type]
            axles=(
                Axle(weight=pounds(12000), tires=2, tire_width=inches(11), steering=True),
                Axle(weight=pounds(17000), tires=4, tire_width=inches(11)),
                Axle(weight=pounds(17000), tires=4, tire_width=inches(11)),
                Axle(weight=pounds(17000), tires=4, tire_width=inches(11)),
                Axle(weight=pounds(17000), tires=4, tire_width=inches(11)),
            ),
            spacings=(feet(15), feet(4), feet(30), feet(4)),
        ),
        FILED,
    )
    road = office.roadway
    for key in ("JCT-A", "JCT-B", "JCT-C", "JCT-D"):
        road.add_node(Node(code=key, name=key.lower(), county="Missoula"))  # type: ignore[arg-type]
    for key, start, end, route, length, posted in (
        ("SEG-AB", "JCT-A", "JCT-B", "US-12", "12.00", None),
        ("SEG-BC", "JCT-B", "JCT-C", "US-12", "8.50", None),
        ("SEG-CD", "JCT-C", "JCT-D", "US-12", "6.00", pounds(48000)),
        ("SEG-BD", "JCT-B", "JCT-D", "SR-200", "31.00", None),
    ):
        road.add_segment(
            Segment(
                code=key,  # type: ignore[arg-type]
                start=start,  # type: ignore[arg-type]
                end=end,  # type: ignore[arg-type]
                route=route,
                distance=miles(length),
                posted_gross=posted,
            )
        )
    road.add_structure(
        Structure(
            reference=road.next_structure(),
            segment="SEG-BD",  # type: ignore[arg-type]
            name="Clark Fork bridge",
            kind=StructureKind.BRIDGE,
            milepost=miles("18.40"),
            rating=pounds(96000),
        )
    )


@pytest.fixture
def desk() -> Iterator[Desk]:
    """A desk over a stocked office."""
    with opened_new_office() as office:
        stock(office)
        yield Desk(office=office)


@pytest.fixture
def issued(desk: Desk) -> Permit:
    """One issued permit."""
    filed = desk.file(an_application())
    return desk.issue(filed.key, DECIDED)
