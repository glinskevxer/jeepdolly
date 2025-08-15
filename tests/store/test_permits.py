import datetime as dt

import pytest

from jeepdolly.errors import ConflictError, NotFoundError
from jeepdolly.limits.finding import Finding, Severity
from jeepdolly.party.carrier import Carrier
from jeepdolly.permit.application import Application, Kind
from jeepdolly.permit.decision import decide
from jeepdolly.permit.permit import Permit, issue
from jeepdolly.rig.axle import Axle
from jeepdolly.rig.config import Configuration
from jeepdolly.rig.load import Load
from jeepdolly.roadway.node import Node
from jeepdolly.store.applications import FiledApplication
from jeepdolly.store.carriers import CarrierStore
from jeepdolly.store.permits import PermitStore
from jeepdolly.store.rigs import RigStore
from jeepdolly.store.roadway import RoadwayStore
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


@pytest.fixture
def store(office):
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
    return PermitStore(office)


def write_one(
    store: PermitStore, findings: tuple[Finding, ...] = ()
) -> tuple[Permit, FiledApplication]:
    """File an application, decide it and issue the permit."""
    filed = store.applications.add(an_application())
    decision = decide(an_application(), findings, DECIDED, miles("42.00"))
    permit = issue(store.next_number(), decision, DECIDED)
    return store.add(permit, filed.key), filed


def test_a_new_store_is_empty(store):
    assert store.count() == 0
    assert store.all() == []


def test_the_first_number_is_one(store):
    assert store.next_number() == "P-000001"


def test_permit_numbers_climb_by_one(store):
    write_one(store)
    assert store.next_number() == "P-000002"


def test_a_permit_round_trips(store):
    made, _ = write_one(store)
    assert store.get(made.number).number == made.number


def test_the_span_round_trips(store):
    made, _ = write_one(store)
    assert store.get(made.number).span == TRIP


def test_the_fee_round_trips(store):
    made, _ = write_one(store)
    assert store.get(made.number).fee == made.fee


def test_the_fee_lines_round_trip(store):
    made, _ = write_one(store)
    read = store.get(made.number)
    assert read.decision.invoice is not None
    assert made.decision.invoice is not None
    assert read.decision.invoice.codes == made.decision.invoice.codes


def test_the_escorts_round_trip(store):
    made, _ = write_one(store)
    read = store.get(made.number)
    assert [e.role for e in read.decision.escorts] == [e.role for e in made.decision.escorts]


def test_an_escorts_reasons_round_trip(store):
    made, _ = write_one(store)
    read = store.get(made.number)
    assert read.decision.escorts[0].reasons == made.decision.escorts[0].reasons


def test_the_findings_round_trip(store):
    found = Finding(
        rule="gross",
        subject="the rig",
        severity=Severity.PERMIT,
        detail="over the limit",
        excess=pounds(20000),
    )
    made, _ = write_one(store, (found,))
    read = store.get(made.number)
    assert read.decision.findings == (found,)


def test_a_permit_with_no_findings_reads_back_empty(store):
    made, _ = write_one(store)
    assert store.get(made.number).decision.findings == ()


def test_the_application_comes_back_with_the_permit(store):
    made, _ = write_one(store)
    assert store.get(made.number).application == an_application()


def test_add_refuses_a_number_that_is_taken(store):
    made, filed = write_one(store)
    with pytest.raises(ConflictError):
        store.add(made, filed.key)


def test_add_refuses_an_application_that_is_not_there(store):
    decision = decide(an_application(), (), DECIDED, miles("42.00"))
    permit = issue(store.next_number(), decision, DECIDED)
    with pytest.raises(NotFoundError):
        store.add(permit, 99)


def test_get_raises_when_it_is_not_there(store):
    with pytest.raises(NotFoundError):
        store.get("P-000001")


def test_find_returns_none_when_it_is_not_there(store):
    assert store.find("P-000001") is None


def test_voiding_is_written_back(store):
    made, _ = write_one(store)
    store.save_state(made.voided("carrier cancelled", DECIDED))
    read = store.get(made.number)
    assert not read.live
    assert read.reason == "carrier cancelled"


def test_extending_is_written_back(store):
    made, _ = write_one(store)
    store.save_state(made.extended(dt.date(2025, 6, 22)))
    assert store.get(made.number).span.last == dt.date(2025, 6, 22)


def test_save_state_refuses_a_permit_that_is_not_there(store):
    decision = decide(an_application(), (), DECIDED, miles("42.00"))
    permit = issue("P-000099", decision, DECIDED)  # type: ignore[arg-type]
    with pytest.raises(NotFoundError):
        store.save_state(permit)


def test_for_carrier_finds_it(store):
    write_one(store)
    assert len(store.for_carrier("VANCE")) == 1


def test_for_carrier_of_someone_else_is_empty(store, office):
    CarrierStore(office).add(
        Carrier(code="OTHER", name="Other Haul", usdot=2, home_state="ID")  # type: ignore[arg-type]
    )
    write_one(store)
    assert store.for_carrier("OTHER") == []


def test_good_on_finds_a_live_permit(store):
    write_one(store)
    assert len(store.good_on(dt.date(2025, 6, 19))) == 1


def test_good_on_skips_a_void_permit(store):
    made, _ = write_one(store)
    store.save_state(made.voided("cancelled", DECIDED))
    assert store.good_on(dt.date(2025, 6, 19)) == []


def test_good_on_skips_a_day_outside_the_span(store):
    write_one(store)
    assert store.good_on(dt.date(2025, 6, 21)) == []


def test_all_is_in_number_order(store):
    write_one(store)
    write_one(store)
    assert [p.number for p in store.all()] == ["P-000001", "P-000002"]


def test_count_and_len_agree(store):
    write_one(store)
    assert store.count() == len(store) == 1


def test_the_table_refuses_a_void_with_no_reason(store, office):
    write_one(store)
    with pytest.raises(Exception, match="CHECK"):
        office.execute("UPDATE permit SET state = 'void' WHERE number = 'P-000001'")


def test_the_office_hands_out_a_permit_store(office):
    from jeepdolly.store.office import Office

    assert isinstance(Office(office).permits, PermitStore)
