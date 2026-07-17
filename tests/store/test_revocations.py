import datetime as dt

import pytest

from jeepdolly.errors import ConflictError, NotFoundError
from jeepdolly.party.carrier import Carrier
from jeepdolly.permit.decision import decide
from jeepdolly.permit.permit import issue
from jeepdolly.permit.revoke import BLOCK_DAYS, Cause, Revocation
from jeepdolly.rig.axle import Axle
from jeepdolly.rig.config import Configuration
from jeepdolly.roadway.node import Node
from jeepdolly.store.carriers import CarrierStore
from jeepdolly.store.permits import PermitStore
from jeepdolly.store.revocations import RevocationStore
from jeepdolly.store.rigs import RigStore
from jeepdolly.store.roadway import RoadwayStore
from jeepdolly.units.distance import miles
from jeepdolly.units.length import feet, inches
from jeepdolly.units.mass import pounds
from jeepdolly.units.money import cents
from tests.store.test_permits import DECIDED, FILED, an_application

PULLED = dt.date(2025, 6, 17)


@pytest.fixture
def permits(office):
    """A permit store with a carrier, a rig and two junctions on file."""
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
    RigStore(office).add("VANCE", config, FILED)
    road = RoadwayStore(office)
    road.add_node(Node(code="JCT-A", name="a", county="Missoula"))  # type: ignore[arg-type]
    road.add_node(Node(code="JCT-D", name="d", county="Missoula"))  # type: ignore[arg-type]
    store = PermitStore(office)
    for _ in range(2):
        filed = store.applications.add(an_application())
        decision = decide(an_application(), (), DECIDED, miles("42.00"))
        store.add(issue(store.next_number(), decision, DECIDED), filed.key)
    return store


@pytest.fixture
def store(office, permits):
    """A revocation store against two issued permits."""
    return RevocationStore(office)


def a_revocation(**over: object) -> Revocation:
    kw: dict[str, object] = {
        "number": "P-000001",
        "cause": Cause.CANCELLED,
        "on": PULLED,
        "refunded": cents(7258),
        "detail": "",
    }
    kw.update(over)
    return Revocation(**kw)  # type: ignore[arg-type]


def test_a_store_with_nothing_pulled_is_empty(store):
    assert store.count() == 0
    assert len(store) == 0


def test_a_revocation_round_trips(store):
    store.add(a_revocation(), "VANCE")
    found = store.get("P-000001")
    assert found.cause is Cause.CANCELLED
    assert int(found.refunded) == 7258


def test_a_detail_round_trips(store):
    store.add(a_revocation(cause=Cause.FALSE_LOAD, detail="steel coil"), "VANCE")
    assert store.get("P-000001").detail == "steel coil"


def test_a_permit_never_pulled_reads_as_none(store):
    assert store.find("P-000001") is None


def test_getting_a_permit_never_pulled_raises(store):
    with pytest.raises(NotFoundError):
        store.get("P-000001")


def test_pulling_an_unknown_permit_is_refused(store):
    with pytest.raises(NotFoundError):
        store.add(a_revocation(number="P-999999"), "VANCE")


def test_pulling_the_same_permit_twice_is_refused(store):
    store.add(a_revocation(), "VANCE")
    with pytest.raises(ConflictError):
        store.add(a_revocation(), "VANCE")


def test_a_carrier_listing_is_oldest_first(store):
    store.add(a_revocation(number="P-000002", on=PULLED), "VANCE")
    store.add(a_revocation(on=PULLED - dt.timedelta(days=1)), "VANCE")
    assert [str(one.number) for one in store.for_carrier("VANCE")] == ["P-000001", "P-000002"]


def test_a_carrier_with_nothing_pulled_lists_nothing(store):
    assert store.for_carrier("VANCE") == []


def test_a_cancellation_blocks_nobody(store):
    store.add(a_revocation(), "VANCE")
    assert store.blocking("VANCE", PULLED) is None


def test_an_undeclared_load_blocks_the_carrier(store):
    store.add(a_revocation(cause=Cause.FALSE_LOAD, detail="steel coil"), "VANCE")
    holding = store.blocking("VANCE", PULLED)
    assert holding is not None
    assert holding.cause is Cause.FALSE_LOAD


def test_the_block_runs_out_after_the_stated_days(store):
    store.add(a_revocation(cause=Cause.FALSE_LOAD, detail="steel coil"), "VANCE")
    past = PULLED + dt.timedelta(days=BLOCK_DAYS + 1)
    assert store.blocking("VANCE", past) is None


def test_a_block_on_one_carrier_does_not_touch_another(store):
    store.add(a_revocation(cause=Cause.FALSE_LOAD, detail="steel coil"), "VANCE")
    assert store.blocking("OTHER", PULLED) is None


def test_pulls_of_one_cause_come_back_together(store):
    store.add(a_revocation(), "VANCE")
    store.add(a_revocation(number="P-000002", cause=Cause.ROUTE_CLOSED), "VANCE")
    assert [str(one.number) for one in store.of_cause(Cause.ROUTE_CLOSED)] == ["P-000002"]


def test_a_cause_nothing_was_pulled_for_comes_back_empty(store):
    store.add(a_revocation(), "VANCE")
    assert store.of_cause(Cause.UNSAFE_MOVE) == []


def test_two_pulls_count_as_two(store):
    store.add(a_revocation(), "VANCE")
    store.add(a_revocation(number="P-000002"), "VANCE")
    assert store.count() == 2
