import datetime as dt

import pytest

from jeepdolly.errors import BadValueError, NotFoundError
from jeepdolly.party.carrier import Carrier
from jeepdolly.permit.application import ANNUAL_DAYS, Application, Kind
from jeepdolly.rig.axle import Axle
from jeepdolly.rig.config import Configuration
from jeepdolly.rig.load import Load
from jeepdolly.roadway.node import Node
from jeepdolly.store.applications import ApplicationStore
from jeepdolly.store.carriers import CarrierStore
from jeepdolly.store.rigs import RigStore
from jeepdolly.store.roadway import RoadwayStore
from jeepdolly.units.clock import DaySpan
from jeepdolly.units.length import feet, feet_inches, inches
from jeepdolly.units.mass import pounds

FILED = dt.date(2025, 6, 16)
TRIP = DaySpan(dt.date(2025, 6, 18), dt.date(2025, 6, 20))
YEAR = DaySpan(dt.date(2025, 7, 1), dt.date(2025, 7, 1) + dt.timedelta(days=ANNUAL_DAYS - 1))


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


@pytest.fixture
def store(office):
    """An application store with a carrier, a rig and two junctions on file."""
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
    return ApplicationStore(office)


def test_a_new_store_is_empty(store):
    assert store.count() == 0
    assert store.all() == []


def test_add_hands_back_a_key(store):
    assert store.add(an_application()).key == 1


def test_add_writes_the_load_too(store):
    filed = store.add(an_application())
    assert store.loads.get(filed.load_id) == a_load()


def test_add_then_get_round_trips(store):
    filed = store.add(an_application())
    assert store.get(filed.key).application == an_application()


def test_the_span_round_trips(store):
    filed = store.add(an_application())
    assert store.get(filed.key).application.span == TRIP


def test_the_route_ends_round_trip(store):
    filed = store.add(an_application())
    read = store.get(filed.key).application
    assert (read.origin, read.destination) == ("JCT-A", "JCT-D")


def test_an_annual_round_trips_without_a_route(store):
    annual = an_application(kind=Kind.ANNUAL, span=YEAR, origin=None, destination=None)
    filed = store.add(annual)
    assert store.get(filed.key).application.origin is None


def test_add_refuses_a_carrier_that_is_not_there(store):
    with pytest.raises(NotFoundError):
        store.add(an_application(carrier="NOBODY"))


def test_add_refuses_a_rig_that_is_not_there(store):
    with pytest.raises(NotFoundError):
        store.add(an_application(rig="R-00099"))


def test_get_raises_when_it_is_not_there(store):
    with pytest.raises(NotFoundError):
        store.get(1)


def test_find_returns_none_when_it_is_not_there(store):
    assert store.find(1) is None


def test_find_returns_the_application(store):
    filed = store.add(an_application())
    found = store.find(filed.key)
    assert found is not None
    assert found.application == an_application()


def test_all_is_oldest_first(store):
    store.add(an_application())
    store.add(an_application())
    assert [f.key for f in store.all()] == [1, 2]


def test_for_carrier_finds_them(store):
    store.add(an_application())
    assert len(store.for_carrier("VANCE")) == 1


def test_for_carrier_of_someone_else_is_empty(store, office):
    CarrierStore(office).add(
        Carrier(code="OTHER", name="Other Haul", usdot=2, home_state="ID")  # type: ignore[arg-type]
    )
    store.add(an_application())
    assert store.for_carrier("OTHER") == []


def test_on_day_finds_one_inside_the_span(store):
    store.add(an_application())
    assert len(store.on_day(dt.date(2025, 6, 19))) == 1


def test_on_day_finds_nothing_outside_the_span(store):
    store.add(an_application())
    assert store.on_day(dt.date(2025, 6, 21)) == []


def test_of_kind_picks_the_annuals(store):
    store.add(an_application())
    store.add(an_application(kind=Kind.ANNUAL, span=YEAR, origin=None, destination=None))
    assert [f.application.kind for f in store.of_kind(Kind.ANNUAL)] == [Kind.ANNUAL]


def test_count_and_len_agree(store):
    store.add(an_application())
    assert store.count() == len(store) == 1


def test_a_row_edited_into_a_contradiction_fails_on_the_way_out(store, office):
    filed = store.add(an_application())
    office.execute("UPDATE load_item SET divisible = 1 WHERE id = ?", (filed.load_id,))
    with pytest.raises(BadValueError):
        store.get(filed.key)


def test_the_table_refuses_an_annual_with_a_route(store, office):
    with pytest.raises(Exception, match="CHECK"):
        office.execute(
            "INSERT INTO application (carrier_code, rig_reference, load_id, kind,"
            " first_day, last_day, filed_on, origin, destination)"
            " VALUES ('VANCE', 'R-00001', 1, 'annual', '2025-01-01', '2025-01-02',"
            " '2025-01-01', 'JCT-A', 'JCT-D')"
        )


def test_a_filed_application_prints_its_key(store):
    filed = store.add(an_application())
    assert repr(filed).startswith("<FiledApplication 1 ")


def test_filed_applications_compare_on_key_and_application(store):
    first = store.add(an_application())
    assert first == store.get(first.key)
    assert first != "not an application"


def test_filed_applications_hash(store):
    first = store.add(an_application())
    assert len({first, store.get(first.key)}) == 1


def test_the_office_hands_out_an_application_store(office):
    from jeepdolly.store.office import Office

    assert isinstance(Office(office).applications, ApplicationStore)
