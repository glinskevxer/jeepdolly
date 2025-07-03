import datetime as dt

import pytest

from jeepdolly.billing.account import DEFAULT_FLOOR, EntryKind
from jeepdolly.errors import BadValueError, NotAllowedError, NotFoundError
from jeepdolly.party.carrier import Carrier
from jeepdolly.store.accounts import AccountStore
from jeepdolly.store.carriers import CarrierStore
from jeepdolly.units.money import cents

DAY = dt.date(2025, 7, 1)
LATER = dt.date(2025, 7, 15)


@pytest.fixture
def store(office):
    """An account store with two carriers on file."""
    carriers = CarrierStore(office)
    carriers.add(
        Carrier(code="VANCE", name="Vance Heavy Haul", usdot=1184062, home_state="MT")  # type: ignore[arg-type]
    )
    carriers.add(
        Carrier(code="OTHER", name="Other Haul", usdot=2, home_state="ID")  # type: ignore[arg-type]
    )
    return AccountStore(office)


def test_a_new_account_is_empty(store):
    assert int(store.balance("VANCE")) == 0
    assert store.entries("VANCE") == []


def test_the_first_sequence_is_one(store):
    assert store.next_sequence("VANCE") == 1


def test_sequences_climb(store):
    store.deposit("VANCE", DAY, cents(100000))
    assert store.next_sequence("VANCE") == 2


def test_sequences_are_per_carrier(store):
    store.deposit("VANCE", DAY, cents(100000))
    assert store.next_sequence("OTHER") == 1


def test_a_deposit_raises_the_balance(store):
    store.deposit("VANCE", DAY, cents(100000))
    assert int(store.balance("VANCE")) == 100000


def test_a_charge_lowers_the_balance(store):
    store.deposit("VANCE", DAY, cents(100000))
    store.charge("VANCE", LATER, cents(30000), "P-000001")
    assert int(store.balance("VANCE")) == 70000


def test_a_charge_needs_a_permit(store):
    with pytest.raises(BadValueError):
        store.post("VANCE", DAY, EntryKind.CHARGE, cents(1000))


def test_a_charge_past_the_floor_is_refused(store):
    with pytest.raises(NotAllowedError):
        store.charge("VANCE", DAY, cents(50001), "P-000001")


def test_a_charge_to_the_floor_is_allowed(store):
    store.charge("VANCE", DAY, cents(50000), "P-000001")
    assert int(store.balance("VANCE")) == -50000


def test_a_refused_charge_leaves_nothing_behind(store):
    with pytest.raises(NotAllowedError):
        store.charge("VANCE", DAY, cents(50001), "P-000001")
    assert store.entries("VANCE") == []


def test_the_default_floor_applies(store):
    assert store.floor_of("VANCE") == DEFAULT_FLOOR


def test_a_floor_may_be_set(store):
    store.set_floor("VANCE", cents(-200000))
    assert int(store.floor_of("VANCE")) == -200000


def test_setting_a_floor_twice_keeps_the_last(store):
    store.set_floor("VANCE", cents(-200000))
    store.set_floor("VANCE", cents(-10000))
    assert int(store.floor_of("VANCE")) == -10000


def test_a_wider_floor_allows_a_bigger_charge(store):
    store.set_floor("VANCE", cents(-200000))
    store.charge("VANCE", DAY, cents(150000), "P-000001")
    assert int(store.balance("VANCE")) == -150000


def test_the_table_refuses_a_positive_floor(store, office):
    with pytest.raises(Exception, match="CHECK"):
        office.execute("INSERT INTO account_terms VALUES ('VANCE', 1)")


def test_entries_are_oldest_first(store):
    store.deposit("VANCE", LATER, cents(100))
    store.deposit("VANCE", DAY, cents(200))
    assert [e.day for e in store.entries("VANCE")] == [DAY, LATER]


def test_an_adjustment_may_be_negative(store):
    store.post("VANCE", DAY, EntryKind.ADJUSTMENT, cents(-500), note="scale error")
    assert int(store.balance("VANCE")) == -500


def test_an_adjustment_needs_a_note(store):
    with pytest.raises(BadValueError):
        store.post("VANCE", DAY, EntryKind.ADJUSTMENT, cents(-500))


def test_a_refund_raises_the_balance(store):
    store.post("VANCE", DAY, EntryKind.REFUND, cents(1000), note="permit voided")
    assert int(store.balance("VANCE")) == 1000


def test_the_account_comes_back_built(store):
    store.deposit("VANCE", DAY, cents(100000))
    account = store.account("VANCE")
    assert account.carrier == "VANCE"
    assert len(account) == 1


def test_the_account_carries_the_floor(store):
    store.set_floor("VANCE", cents(-1000))
    assert int(store.account("VANCE").floor) == -1000


def test_an_unknown_carrier_is_refused(store):
    with pytest.raises(NotFoundError):
        store.balance("NOBODY")


def test_posting_to_an_unknown_carrier_is_refused(store):
    with pytest.raises(NotFoundError):
        store.deposit("NOBODY", DAY, cents(100))


def test_owing_lists_the_overdrawn(store):
    store.charge("VANCE", DAY, cents(30000), "P-000001")
    assert [str(c) for c, _ in store.owing()] == ["VANCE"]


def test_owing_leaves_out_the_ones_in_credit(store):
    store.deposit("VANCE", DAY, cents(100))
    assert store.owing() == []


def test_owing_is_worst_first(store):
    store.charge("VANCE", DAY, cents(30000), "P-000001")
    store.charge("OTHER", DAY, cents(40000), "P-000002")
    assert [str(c) for c, _ in store.owing()] == ["OTHER", "VANCE"]


def test_count_and_len_agree(store):
    store.deposit("VANCE", DAY, cents(100))
    store.deposit("OTHER", DAY, cents(100))
    assert store.count() == len(store) == 2


def test_entries_of_one_carrier_leave_the_other_alone(store):
    store.deposit("VANCE", DAY, cents(100))
    assert store.entries("OTHER") == []


def test_the_office_hands_out_an_account_store(office):
    from jeepdolly.store.office import Office

    assert isinstance(Office(office).accounts, AccountStore)
