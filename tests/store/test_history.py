import datetime as dt

import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.store.history import MAX_DETAIL, Event, EventKind, HistoryStore
from jeepdolly.units.clock import DaySpan

DAY = dt.date(2025, 6, 17)
LATER = dt.date(2025, 7, 1)


@pytest.fixture
def store(office):
    """A history store over a migrated office."""
    return HistoryStore(office)


def test_a_new_journal_is_empty(store):
    assert store.count() == 0
    assert store.all() == []


def test_the_first_sequence_is_one(store):
    assert store.next_sequence() == 1


def test_journal_sequences_climb_by_one(store):
    store.write(DAY, EventKind.FILED, "application 1")
    assert store.next_sequence() == 2


def test_an_entry_round_trips(store):
    store.write(DAY, EventKind.ISSUED, "P-000001", "VANCE $97.52", "jhalloran")
    read = store.all()[0]
    assert read.kind is EventKind.ISSUED
    assert read.subject == "P-000001"
    assert read.clerk == "jhalloran"


def test_entries_come_back_oldest_first(store):
    store.write(LATER, EventKind.FILED, "application 2")
    store.write(DAY, EventKind.FILED, "application 1")
    assert [e.sequence for e in store.all()] == [1, 2]


def test_about_narrows_to_one_subject(store):
    store.write(DAY, EventKind.ISSUED, "P-000001")
    store.write(DAY, EventKind.ISSUED, "P-000002")
    assert [e.subject for e in store.about("P-000001")] == ["P-000001"]


def test_about_tidies_the_subject_it_is_given(store):
    store.write(DAY, EventKind.ISSUED, "P-000001")
    assert len(store.about("  P-000001  ")) == 1


def test_of_kind_narrows_to_one_kind(store):
    store.write(DAY, EventKind.FILED, "application 1")
    store.write(DAY, EventKind.ISSUED, "P-000001")
    assert [e.kind for e in store.of_kind(EventKind.ISSUED)] == [EventKind.ISSUED]


def test_within_narrows_to_a_span(store):
    store.write(DAY, EventKind.FILED, "application 1")
    store.write(LATER, EventKind.FILED, "application 2")
    assert len(store.within(DaySpan(DAY, DAY))) == 1


def test_an_entry_refuses_an_empty_subject(store):
    with pytest.raises(BadValueError):
        store.write(DAY, EventKind.FILED, "  ")


def test_an_entry_refuses_a_detail_that_is_too_long(store):
    with pytest.raises(BadValueError):
        store.write(DAY, EventKind.FILED, "application 1", "x" * (MAX_DETAIL + 1))


def test_an_entry_takes_the_longest_detail(store):
    made = store.write(DAY, EventKind.FILED, "application 1", "x" * MAX_DETAIL)
    assert len(made.detail) == MAX_DETAIL


def test_an_entry_refuses_a_datetime(store):
    with pytest.raises(BadValueError):
        store.write(dt.datetime(2025, 6, 17, tzinfo=dt.UTC), EventKind.FILED, "x1")


def test_an_entry_refuses_a_bool_sequence():
    with pytest.raises(BadValueError):
        Event(sequence=True, day=DAY, kind=EventKind.FILED, subject="x1")


def test_an_entry_refuses_sequence_zero():
    with pytest.raises(BadValueError):
        Event(sequence=0, day=DAY, kind=EventKind.FILED, subject="x1")


def test_an_entry_refuses_a_detail_that_is_not_text():
    with pytest.raises(BadValueError):
        Event(sequence=1, day=DAY, kind=EventKind.FILED, subject="x1", detail=12)  # type: ignore[arg-type]


def test_an_entry_collapses_whitespace_in_the_detail(store):
    made = store.write(DAY, EventKind.FILED, "application 1", "a   b")
    assert made.detail == "a b"


def test_an_entry_prints_its_clerk(store):
    made = store.write(DAY, EventKind.ISSUED, "P-000001", "VANCE", "jhalloran")
    assert str(made) == "2025-06-17 P-000001 issued by jhalloran: VANCE"


def test_an_entry_without_a_clerk_prints_plainly(store):
    made = store.write(DAY, EventKind.ISSUED, "P-000001")
    assert str(made) == "2025-06-17 P-000001 issued"


def test_entries_order_by_their_sequence():
    first = Event(sequence=1, day=LATER, kind=EventKind.FILED, subject="a1")
    second = Event(sequence=2, day=DAY, kind=EventKind.FILED, subject="b1")
    assert sorted([second, first])[0] is first


def test_count_and_len_agree(store):
    store.write(DAY, EventKind.FILED, "application 1")
    assert store.count() == len(store) == 1


def test_the_office_hands_out_a_history_store(office):
    from jeepdolly.store.office import Office

    assert isinstance(Office(office).history, HistoryStore)


def test_the_table_refuses_an_empty_kind(store, office):
    with pytest.raises(Exception, match="CHECK"):
        office.execute(
            "INSERT INTO journal (day, kind, subject) VALUES ('2025-01-01', '', 'x')"
        )
