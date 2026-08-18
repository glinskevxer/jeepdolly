import datetime as dt

import pytest

from jeepdolly.enforce.ticket import Discrepancy, Ticket
from jeepdolly.enforce.violation import Violation
from jeepdolly.errors import ConflictError, NotFoundError
from jeepdolly.permit.decision import decide
from jeepdolly.permit.permit import issue
from jeepdolly.store.enforcement import EnforcementStore
from jeepdolly.store.permits import PermitStore
from jeepdolly.units.distance import miles
from jeepdolly.units.mass import pounds
from jeepdolly.units.money import cents
from tests.store.test_permits import DECIDED, an_application

WEIGHED = dt.date(2025, 6, 19)


@pytest.fixture
def permits(stocked):
    """A permit store with one issued permit on the stocked office."""
    store = PermitStore(stocked)
    filed = store.applications.add(an_application())
    decision = decide(an_application(), (), DECIDED, miles("42.00"))
    store.add(issue(store.next_number(), decision, DECIDED), filed.key)
    return store


@pytest.fixture
def store(stocked, permits):
    """An enforcement store against one issued permit."""
    return EnforcementStore(stocked)


def a_ticket(store: EnforcementStore, **over: object) -> Ticket:
    kw: dict[str, object] = {
        "number": store.next_number(),
        "permit": "P-000001",
        "weighed_on": WEIGHED,
        "place": "Bonner scales",
        "officer": "Sgt Ramos",
        "axles": (pounds(12000), pounds(19000)),
    }
    kw.update(over)
    return Ticket(**kw)  # type: ignore[arg-type]


def a_violation(**over: object) -> Violation:
    kw: dict[str, object] = {
        "on": WEIGHED,
        "ticket": "WT-00001",
        "permit": "P-000001",
        "carrier": "VANCE",
        "kind": Discrepancy.GROSS,
        "over": pounds(2000),
        "penalty": cents(2500),
    }
    kw.update(over)
    return Violation(**kw)  # type: ignore[arg-type]


def test_a_store_with_nothing_weighed_is_empty(store):
    assert store.count() == 0
    assert len(store) == 0


def test_the_first_ticket_number_is_one(store):
    assert store.next_number() == "WT-00001"


def test_ticket_numbers_climb_by_one(store):
    store.add(a_ticket(store), [])
    assert store.next_number() == "WT-00002"


def test_a_ticket_round_trips(store):
    store.add(a_ticket(store), [])
    found = store.get("WT-00001")
    assert found.place == "Bonner scales"
    assert found.officer == "Sgt Ramos"


def test_the_pad_weights_round_trip_in_order(store):
    store.add(a_ticket(store, axles=(pounds(11000), pounds(12000), pounds(13000))), [])
    assert [int(one) for one in store.get("WT-00001").axles] == [11000, 12000, 13000]


def test_the_gross_is_added_back_from_the_pads(store):
    store.add(a_ticket(store), [])
    assert int(store.get("WT-00001").gross) == 31000


def test_a_ticket_against_an_unknown_permit_is_refused(store):
    with pytest.raises(NotFoundError):
        store.add(a_ticket(store, permit="P-999999"), [])


def test_the_same_ticket_twice_is_refused(store):
    store.add(a_ticket(store), [])
    with pytest.raises(ConflictError):
        store.add(a_ticket(store, number="WT-00001"), [])


def test_a_missing_ticket_reads_as_none(store):
    assert store.find("WT-00001") is None


def test_getting_a_missing_ticket_raises(store):
    with pytest.raises(NotFoundError):
        store.get("WT-00001")


def test_a_violation_written_with_a_ticket_reads_back(store):
    store.add(a_ticket(store), [a_violation()])
    found = store.violations_on("WT-00001")
    assert len(found) == 1
    assert int(found[0].penalty) == 2500


def test_a_clean_ticket_has_no_violations(store):
    store.add(a_ticket(store), [])
    assert store.violations_on("WT-00001") == []


def test_a_carriers_record_is_oldest_first(store):
    store.add(a_ticket(store), [a_violation(on=WEIGHED)])
    store.add(
        a_ticket(store, number="WT-00002"),
        [a_violation(ticket="WT-00002", on=WEIGHED - dt.timedelta(days=5))],
    )
    record = store.violations_of("VANCE")
    assert [str(one.ticket) for one in record] == ["WT-00002", "WT-00001"]


def test_a_carrier_with_a_clean_record_has_nothing(store):
    assert store.violations_of("VANCE") == []


def test_tickets_for_a_permit_come_back_oldest_first(store):
    store.add(a_ticket(store), [])
    store.add(a_ticket(store, number="WT-00002", weighed_on=WEIGHED - dt.timedelta(days=1)), [])
    found = store.for_permit("P-000001")
    assert [str(one.number) for one in found] == ["WT-00002", "WT-00001"]


def test_a_permit_never_weighed_has_no_tickets(store):
    assert store.for_permit("P-000001") == []


def test_violations_since_a_day_leave_out_the_older_ones(store):
    store.add(a_ticket(store), [a_violation(on=WEIGHED - dt.timedelta(days=10))])
    assert store.since(WEIGHED) == []


def test_violations_since_a_day_keep_the_newer_ones(store):
    store.add(a_ticket(store), [a_violation()])
    assert len(store.since(WEIGHED)) == 1


def test_an_ordinary_ticket_is_not_forgiven(store):
    store.add(a_ticket(store), [])
    assert not store.forgiven("WT-00001")


def test_a_forgiven_ticket_says_so(store):
    store.add(a_ticket(store), [], forgiven=True)
    assert store.forgiven("WT-00001")


def test_asking_whether_a_missing_ticket_was_forgiven_raises(store):
    with pytest.raises(NotFoundError):
        store.forgiven("WT-00001")
