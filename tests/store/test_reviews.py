import datetime as dt

import pytest

from jeepdolly.errors import ConflictError, NotFoundError
from jeepdolly.party.carrier import Carrier
from jeepdolly.permit.application import Application, Kind
from jeepdolly.permit.review import ReviewState, open_review
from jeepdolly.rig.axle import Axle
from jeepdolly.rig.config import Configuration
from jeepdolly.rig.load import Load
from jeepdolly.roadway.node import Node
from jeepdolly.store.applications import ApplicationStore
from jeepdolly.store.carriers import CarrierStore
from jeepdolly.store.reviews import ReviewStore
from jeepdolly.store.rigs import RigStore
from jeepdolly.store.roadway import RoadwayStore
from jeepdolly.units.clock import DaySpan
from jeepdolly.units.length import feet, feet_inches, inches
from jeepdolly.units.mass import pounds

FILED = dt.date(2025, 6, 16)
OPENED = dt.date(2025, 7, 1)
DECIDED = dt.date(2025, 7, 10)
TRIP = DaySpan(dt.date(2025, 6, 18), dt.date(2025, 6, 20))


@pytest.fixture
def store(office):
    """A review store with one application already on file."""
    CarrierStore(office).add(
        Carrier(code="VANCE", name="Vance Heavy Haul", usdot=1184062, home_state="MT")  # type: ignore[arg-type]
    )
    RigStore(office).add(
        "VANCE",
        Configuration(
            name="3S2",  # type: ignore[arg-type]
            axles=(
                Axle(weight=pounds(12000), tires=2, tire_width=inches(11), steering=True),
                Axle(weight=pounds(17000), tires=4, tire_width=inches(11)),
            ),
            spacings=(feet(15),),
        ),
        FILED,
    )
    road = RoadwayStore(office)
    road.add_node(Node(code="JCT-A", name="a", county="Missoula"))  # type: ignore[arg-type]
    road.add_node(Node(code="JCT-D", name="d", county="Missoula"))  # type: ignore[arg-type]
    ApplicationStore(office).add(
        Application(
            carrier="VANCE",  # type: ignore[arg-type]
            rig="R-00001",  # type: ignore[arg-type]
            load=Load(
                description="stator",
                weight=pounds(148000),
                width=feet_inches(17, 0),
                height=feet_inches(14, 2),
                length=feet(48),
                divisible=False,
                reason="single-piece",
            ),
            span=TRIP,
            filed_on=FILED,
            kind=Kind.SUPERLOAD,
            origin="JCT-A",  # type: ignore[arg-type]
            destination="JCT-D",  # type: ignore[arg-type]
        )
    )
    return ReviewStore(office)


def test_a_new_store_is_empty(store):
    assert store.count() == 0
    assert store.all() == []


def test_the_first_reference_is_one(store):
    assert store.next_reference() == "E-00001"


def test_review_references_climb_by_one(store):
    store.add(open_review(store.next_reference(), 1, OPENED))
    assert store.next_reference() == "E-00002"


def test_an_open_review_round_trips(store):
    made = store.add(open_review(store.next_reference(), 1, OPENED))
    read = store.get(made.reference)
    assert read.open
    assert read.application_key == 1


def test_add_refuses_an_application_that_is_not_there(store):
    with pytest.raises(NotFoundError):
        store.add(open_review("E-00001", 99, OPENED))  # type: ignore[arg-type]


def test_add_refuses_a_reference_that_is_taken(store):
    made = store.add(open_review(store.next_reference(), 1, OPENED))
    with pytest.raises(ConflictError):
        store.add(made)


def test_get_raises_when_it_is_not_there(store):
    with pytest.raises(NotFoundError):
        store.get("E-00001")


def test_find_returns_none_when_it_is_not_there(store):
    assert store.find("E-00001") is None


def test_an_approval_is_written_back(store):
    made = store.add(open_review(store.next_reference(), 1, OPENED))
    store.save_state(made.approved_by("R Halloran", DECIDED, ("walking pace",)))
    read = store.get(made.reference)
    assert read.approved
    assert read.engineer == "R Halloran"


def test_the_conditions_round_trip_in_order(store):
    made = store.add(open_review(store.next_reference(), 1, OPENED))
    conditions = ("walking pace over the bridge", "county notified a day ahead")
    store.save_state(made.approved_by("R Halloran", DECIDED, conditions))
    assert store.get(made.reference).conditions == conditions


def test_a_condition_holding_a_separator_survives(store):
    made = store.add(open_review(store.next_reference(), 1, OPENED))
    tricky = ("hold at the gate | call the yard",)
    store.save_state(made.approved_by("R Halloran", DECIDED, tricky))
    assert store.get(made.reference).conditions == tricky


def test_a_refusal_is_written_back(store):
    made = store.add(open_review(store.next_reference(), 1, OPENED))
    store.save_state(made.refused_by("R Halloran", DECIDED, "the bridge will not take it"))
    read = store.get(made.reference)
    assert read.state is ReviewState.REFUSED
    assert "bridge" in read.note


def test_a_withdrawal_is_written_back(store):
    made = store.add(open_review(store.next_reference(), 1, OPENED))
    store.save_state(made.withdrawn(DECIDED))
    assert store.get(made.reference).state is ReviewState.WITHDRAWN


def test_save_state_refuses_a_review_that_is_not_there(store):
    stray = open_review("E-00099", 1, OPENED)  # type: ignore[arg-type]
    with pytest.raises(NotFoundError):
        store.save_state(stray)


def test_the_open_list_holds_only_the_open_ones(store):
    first = store.add(open_review(store.next_reference(), 1, OPENED))
    store.add(open_review(store.next_reference(), 1, OPENED))
    store.save_state(first.approved_by("R Halloran", DECIDED))
    assert [r.reference for r in store.open_list()] == ["E-00002"]


def test_for_application_finds_every_review(store):
    store.add(open_review(store.next_reference(), 1, OPENED))
    store.add(open_review(store.next_reference(), 1, OPENED))
    assert len(store.for_application(1)) == 2


def test_for_another_application_is_empty(store):
    store.add(open_review(store.next_reference(), 1, OPENED))
    assert store.for_application(2) == []


def test_decided_between_finds_the_decision(store):
    made = store.add(open_review(store.next_reference(), 1, OPENED))
    store.save_state(made.approved_by("R Halloran", DECIDED))
    assert len(store.decided_between(OPENED, DECIDED)) == 1


def test_decided_between_leaves_out_an_open_review(store):
    store.add(open_review(store.next_reference(), 1, OPENED))
    assert store.decided_between(OPENED, DECIDED) == []


def test_decided_between_leaves_out_a_decision_outside_the_span(store):
    made = store.add(open_review(store.next_reference(), 1, OPENED))
    store.save_state(made.approved_by("R Halloran", DECIDED))
    assert store.decided_between(OPENED, OPENED) == []


def test_conditions_are_replaced_rather_than_added_to(store):
    made = store.add(open_review(store.next_reference(), 1, OPENED))
    store.save_state(made.approved_by("R Halloran", DECIDED, ("first", "second")))
    read = store.get(made.reference)
    assert len(read.conditions) == 2


def test_count_and_len_agree(store):
    store.add(open_review(store.next_reference(), 1, OPENED))
    assert store.count() == len(store) == 1


def test_the_table_refuses_an_open_review_with_an_engineer(store, office):
    store.add(open_review(store.next_reference(), 1, OPENED))
    with pytest.raises(Exception, match="CHECK"):
        office.execute("UPDATE review SET engineer = 'R Halloran' WHERE reference = 'E-00001'")


def test_the_office_hands_out_a_review_store(office):
    from jeepdolly.store.office import Office

    assert isinstance(Office(office).reviews, ReviewStore)
