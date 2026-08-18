"""A migrated in memory office for the store suite, and a stocked one.

``stocked`` puts a carrier, two rigs and three junctions on the file. Three
suites were each building that themselves out of five stores, and the copies had
already drifted: two of them recorded one rig and the third recorded two, so a
test moved between files stopped meaning what it said.
"""

import datetime as dt
import sqlite3
from collections.abc import Iterator

import pytest

from jeepdolly.party.carrier import Carrier
from jeepdolly.rig.axle import Axle
from jeepdolly.rig.config import Configuration
from jeepdolly.roadway.node import Node
from jeepdolly.store.carriers import CarrierStore
from jeepdolly.store.migrations import migrate
from jeepdolly.store.rigs import RigStore
from jeepdolly.store.roadway import RoadwayStore
from jeepdolly.store.sqlite import MEMORY, opened
from jeepdolly.units.length import feet, inches
from jeepdolly.units.mass import pounds

FILED = dt.date(2025, 6, 16)


@pytest.fixture
def raw() -> Iterator[sqlite3.Connection]:
    """An open connection with no schema at all."""
    with opened(MEMORY) as connection:
        yield connection


@pytest.fixture
def office(raw: sqlite3.Connection) -> sqlite3.Connection:
    """An open connection with every migration applied."""
    migrate(raw)
    return raw


@pytest.fixture
def stocked(office: sqlite3.Connection) -> sqlite3.Connection:
    """An office with a carrier, two rigs and three junctions on file."""
    CarrierStore(office).add(
        Carrier(code="VANCE", name="Vance Heavy Haul", usdot=1184062, home_state="MT")  # type: ignore[arg-type]
    )
    config = Configuration(
        name="3S2",  # type: ignore[arg-type]
        axles=(
            Axle(weight=pounds(12000), tires=2, tire_width=inches(11), steering=True),
            Axle(weight=pounds(17000), tires=4, tire_width=inches(11)),
        ),
        spacings=(feet(15),),
    )
    rigs = RigStore(office)
    rigs.add("VANCE", config, FILED)
    rigs.add("VANCE", config, FILED)
    road = RoadwayStore(office)
    for key in ("JCT-A", "JCT-C", "JCT-D"):
        road.add_node(Node(code=key, name=key.lower(), county="Missoula"))  # type: ignore[arg-type]
    return office
