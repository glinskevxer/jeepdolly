import datetime as dt

import pytest

from jeepdolly.errors import NotFoundError
from jeepdolly.permit.amendment import Amendment, Change, amend
from jeepdolly.permit.decision import decide
from jeepdolly.permit.permit import Permit, issue
from jeepdolly.store.amendments import AmendmentStore, FiledAmendment
from jeepdolly.store.permits import PermitStore
from jeepdolly.units.clock import DaySpan
from jeepdolly.units.distance import miles
from jeepdolly.units.mass import pounds
from jeepdolly.units.money import cents
from tests.store.test_permits import TRIP, a_load, an_application

DECIDED = dt.date(2025, 6, 17)
LONGER = DaySpan(TRIP.first, TRIP.last + dt.timedelta(days=2))


@pytest.fixture
def permits(stocked):
    """A permit store against the stocked office."""
    return PermitStore(stocked)


@pytest.fixture
def store(stocked, permits):
    """An amendment store against one issued permit."""
    filed = permits.applications.add(an_application())
    decision = decide(an_application(), (), DECIDED, miles("42.00"))
    permits.add(issue(permits.next_number(), decision, DECIDED), filed.key)
    return AmendmentStore(stocked)


def _file(store: AmendmentStore, made: Amendment, charged: int = 0) -> FiledAmendment:
    """File the amended application, then write the amendment against it."""
    key = store.applications.add(made.now).key
    return store.add(made, cents(charged), key)


def a_permit(permits: PermitStore) -> Permit:
    """The one issued permit the fixture wrote."""
    return permits.get("P-000001")


def test_a_new_store_has_no_amendments(store):
    assert store.count() == 0
    assert len(store) == 0


def test_an_amendment_round_trips(store, permits):
    made = amend(a_permit(permits), an_application(rig="R-00002"), DECIDED)
    _file(store, made, 3500)
    found = store.for_permit("P-000001")
    assert len(found) == 1
    assert found[0].changes == (Change.RIG,)


def test_the_charge_is_kept_beside_the_row(store, permits):
    made = amend(a_permit(permits), an_application(rig="R-00002"), DECIDED)
    _file(store, made, 3500)
    assert int(store.for_permit("P-000001")[0].charged) == 3500


def test_the_note_round_trips(store, permits):
    made = amend(a_permit(permits), an_application(rig="R-00002"), DECIDED, note="swap")
    _file(store, made)
    assert store.for_permit("P-000001")[0].amendment.note == "swap"


def test_an_amendment_against_an_unknown_permit_is_refused(store, permits):
    made = amend(a_permit(permits), an_application(rig="R-00002"), DECIDED)
    ghost = type(made)(
        number="P-999999",  # type: ignore[arg-type]
        was=made.was,
        now=made.now,
        filed_on=made.filed_on,
    )
    with pytest.raises(NotFoundError):
        store.add(ghost, cents(0), store.applications.add(ghost.now).key)


def test_an_unamended_permit_reads_as_issued(store, permits):
    assert store.current("P-000001") == a_permit(permits).application


def test_an_unamended_permit_has_no_latest(store):
    assert store.latest("P-000001") is None


def test_the_current_wording_follows_the_last_amendment(store, permits):
    made = amend(a_permit(permits), an_application(rig="R-00002"), DECIDED)
    _file(store, made)
    assert store.current("P-000001").rig == "R-00002"


def test_a_chain_reads_each_amendment_against_the_one_before(store, permits):
    first = amend(a_permit(permits), an_application(rig="R-00002"), DECIDED)
    _file(store, first)
    second_now = an_application(rig="R-00002", destination="JCT-C")
    permit = a_permit(permits)
    second = type(first)(
        number=permit.number,
        was=first.now,
        now=second_now,
        filed_on=DECIDED + dt.timedelta(days=1),
    )
    _file(store, second)
    chain = store.for_permit("P-000001")
    assert [one.changes for one in chain] == [(Change.RIG,), (Change.ROUTE,)]


def test_the_latest_amendment_is_the_end_of_the_chain(store, permits):
    first = amend(a_permit(permits), an_application(rig="R-00002"), DECIDED)
    _file(store, first)
    second = type(first)(
        number=a_permit(permits).number,
        was=first.now,
        now=an_application(rig="R-00002", destination="JCT-C"),
        filed_on=DECIDED + dt.timedelta(days=1),
    )
    _file(store, second)
    latest = store.latest("P-000001")
    assert latest is not None
    assert latest.changes == (Change.ROUTE,)


def test_a_load_change_survives_the_round_trip(store, permits):
    heavy = an_application(load=a_load(weight=pounds(160000)))
    _file(store, amend(a_permit(permits), heavy, DECIDED))
    assert int(store.current("P-000001").load.weight) == 160000


def test_a_date_change_survives_the_round_trip(store, permits):
    _file(store, amend(a_permit(permits), an_application(span=LONGER), DECIDED))
    assert store.current("P-000001").span == LONGER


def test_amendments_filed_on_a_day_come_back(store, permits):
    _file(store, amend(a_permit(permits), an_application(rig="R-00002"), DECIDED))
    assert len(store.on_day(DECIDED)) == 1


def test_amendments_filed_on_another_day_do_not(store, permits):
    _file(store, amend(a_permit(permits), an_application(rig="R-00002"), DECIDED))
    assert store.on_day(DECIDED + dt.timedelta(days=1)) == []


def test_reading_an_unknown_permits_amendments_raises(store):
    with pytest.raises(NotFoundError):
        store.for_permit("P-999999")


def test_two_amendments_count_as_two(store, permits):
    first = amend(a_permit(permits), an_application(rig="R-00002"), DECIDED)
    _file(store, first)
    second = type(first)(
        number=a_permit(permits).number,
        was=first.now,
        now=an_application(rig="R-00002", destination="JCT-C"),
        filed_on=DECIDED,
    )
    _file(store, second)
    assert store.count() == 2


def test_a_filed_amendment_prints_its_key(store, permits):
    made = _file(store, amend(a_permit(permits), an_application(rig="R-00002"), DECIDED))
    assert "FiledAmendment" in repr(made)


def test_two_filed_amendments_read_back_equal(store, permits):
    _file(store, amend(a_permit(permits), an_application(rig="R-00002"), DECIDED))
    once = store.for_permit("P-000001")
    twice = store.for_permit("P-000001")
    assert once == twice
    assert hash(once[0]) == hash(twice[0])


def test_a_store_with_no_amendments_points_at_no_applications(store):
    assert store.application_keys() == frozenset()


def test_an_amendment_names_the_application_it_moved_onto(store, permits):
    made = amend(a_permit(permits), an_application(rig="R-00002"), DECIDED)
    filed = _file(store, made)
    assert store.application_keys() == frozenset({filed.application_key})


def test_two_amendments_name_two_applications(store, permits):
    first = amend(a_permit(permits), an_application(rig="R-00002"), DECIDED)
    _file(store, first)
    second = Amendment(
        number=a_permit(permits).number,
        was=first.now,
        now=an_application(rig="R-00002", destination="JCT-C"),
        filed_on=DECIDED,
    )
    _file(store, second)
    assert len(store.application_keys()) == 2
