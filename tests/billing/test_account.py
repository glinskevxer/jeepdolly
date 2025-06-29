import datetime as dt

import pytest

from jeepdolly.billing.account import (
    DEFAULT_FLOOR,
    SIGNS,
    Account,
    Entry,
    EntryKind,
    running,
)
from jeepdolly.errors import BadValueError, NotAllowedError
from jeepdolly.units.clock import DaySpan
from jeepdolly.units.money import cents

DAY = dt.date(2025, 7, 1)
LATER = dt.date(2025, 7, 15)


def an_entry(**over: object) -> Entry:
    """A deposit, with any part of it swapped out."""
    kw: dict[str, object] = {
        "day": DAY,
        "sequence": 1,
        "carrier": "VANCE",
        "kind": EntryKind.DEPOSIT,
        "amount": cents(100000),
    }
    kw.update(over)
    return Entry(**kw)  # type: ignore[arg-type]


def a_charge(**over: object) -> Entry:
    """A permit charge."""
    return an_entry(kind=EntryKind.CHARGE, reference="P-000001", **over)


def test_a_deposit_is_positive():
    assert int(an_entry().signed) == 100000


def test_a_charge_is_negative():
    assert int(a_charge(sequence=2).signed) == -100000


def test_a_refund_is_positive():
    assert int(an_entry(kind=EntryKind.REFUND).signed) > 0


def test_an_adjustment_keeps_its_own_sign():
    made = an_entry(kind=EntryKind.ADJUSTMENT, amount=cents(-500), note="scale error")
    assert int(made.signed) == -500


def test_the_signs_table_covers_every_kind():
    assert set(SIGNS) == set(EntryKind)


def test_an_entry_normalises_the_carrier():
    assert an_entry(carrier="vance").carrier == "VANCE"


def test_an_entry_refuses_a_zero_deposit():
    with pytest.raises(BadValueError):
        an_entry(amount=cents(0))


def test_an_entry_refuses_a_negative_deposit():
    with pytest.raises(BadValueError):
        an_entry(amount=cents(-1))


def test_an_adjustment_refuses_zero():
    with pytest.raises(BadValueError):
        an_entry(kind=EntryKind.ADJUSTMENT, amount=cents(0), note="x")


def test_an_adjustment_needs_a_note():
    with pytest.raises(BadValueError):
        an_entry(kind=EntryKind.ADJUSTMENT, amount=cents(-500))


def test_a_charge_needs_a_permit_reference():
    with pytest.raises(BadValueError):
        an_entry(kind=EntryKind.CHARGE)


def test_an_entry_refuses_sequence_zero():
    with pytest.raises(BadValueError):
        an_entry(sequence=0)


def test_an_entry_refuses_a_bool_sequence():
    with pytest.raises(BadValueError):
        an_entry(sequence=True)


def test_an_entry_refuses_a_datetime():
    with pytest.raises(BadValueError):
        an_entry(day=dt.datetime(2025, 7, 1, tzinfo=dt.UTC))


def test_an_entry_collapses_whitespace_in_the_note():
    made = an_entry(kind=EntryKind.ADJUSTMENT, amount=cents(-1), note="scale   error")
    assert made.note == "scale error"


def test_an_entry_prints_its_reference():
    assert "P-000001" in str(a_charge(sequence=2))


def test_entries_order_by_day_then_sequence():
    first = an_entry(day=DAY, sequence=2)
    second = an_entry(day=LATER, sequence=1)
    assert sorted([second, first])[0] is first


def test_an_empty_account_has_a_zero_balance():
    made = Account(carrier="VANCE", entries=())  # type: ignore[arg-type]
    assert int(made.balance) == 0
    assert made.in_credit


def test_the_balance_is_the_sum_of_the_entries():
    made = Account(
        carrier="VANCE",  # type: ignore[arg-type]
        entries=(an_entry(), a_charge(sequence=2, amount=cents(30000))),
    )
    assert int(made.balance) == 70000


def test_an_account_sorts_its_entries():
    made = Account(
        carrier="VANCE",  # type: ignore[arg-type]
        entries=(an_entry(day=LATER, sequence=2), an_entry(day=DAY, sequence=1)),
    )
    assert made.entries[0].day == DAY


def test_an_account_refuses_an_entry_from_another_carrier():
    with pytest.raises(BadValueError):
        Account(carrier="VANCE", entries=(an_entry(carrier="OTHER"),))  # type: ignore[arg-type]


def test_an_account_refuses_two_entries_with_one_sequence():
    with pytest.raises(BadValueError):
        Account(carrier="VANCE", entries=(an_entry(), an_entry()))  # type: ignore[arg-type]


def test_an_account_refuses_a_positive_floor():
    with pytest.raises(BadValueError):
        Account(carrier="VANCE", entries=(), floor=cents(1))  # type: ignore[arg-type]


def test_an_overdrawn_account_is_not_in_credit():
    made = Account(
        carrier="VANCE",  # type: ignore[arg-type]
        entries=(a_charge(amount=cents(1000)),),
    )
    assert not made.in_credit


def test_headroom_is_the_balance_above_the_floor():
    made = Account(carrier="VANCE", entries=())  # type: ignore[arg-type]
    assert int(made.headroom) == -int(DEFAULT_FLOOR)


def test_a_charge_inside_the_headroom_is_allowed():
    made = Account(carrier="VANCE", entries=())  # type: ignore[arg-type]
    assert made.allows(cents(10000))


def test_a_charge_past_the_floor_is_not():
    made = Account(carrier="VANCE", entries=())  # type: ignore[arg-type]
    assert not made.allows(cents(50001))


def test_a_charge_exactly_to_the_floor_is_allowed():
    made = Account(carrier="VANCE", entries=())  # type: ignore[arg-type]
    assert made.allows(cents(50000))


def test_allows_refuses_a_negative_charge():
    made = Account(carrier="VANCE", entries=())  # type: ignore[arg-type]
    with pytest.raises(BadValueError):
        made.allows(cents(-1))


def test_check_raises_past_the_floor():
    made = Account(carrier="VANCE", entries=())  # type: ignore[arg-type]
    with pytest.raises(NotAllowedError):
        made.check(cents(50001))


def test_check_is_quiet_inside_the_floor():
    made = Account(carrier="VANCE", entries=())  # type: ignore[arg-type]
    made.check(cents(10000))


def test_a_deposit_buys_headroom():
    made = Account(carrier="VANCE", entries=(an_entry(),))  # type: ignore[arg-type]
    assert made.allows(cents(150000))


def test_within_picks_a_span():
    made = Account(
        carrier="VANCE",  # type: ignore[arg-type]
        entries=(an_entry(), an_entry(day=LATER, sequence=2)),
    )
    assert len(made.within(DaySpan(DAY, DAY))) == 1


def test_balance_on_a_day_ignores_later_entries():
    made = Account(
        carrier="VANCE",  # type: ignore[arg-type]
        entries=(an_entry(), a_charge(day=LATER, sequence=2, amount=cents(30000))),
    )
    assert int(made.balance_on(DAY)) == 100000
    assert int(made.balance_on(LATER)) == 70000


def test_of_kind_picks_the_charges():
    made = Account(
        carrier="VANCE",  # type: ignore[arg-type]
        entries=(an_entry(), a_charge(sequence=2)),
    )
    assert len(made.of_kind(EntryKind.CHARGE)) == 1


def test_an_account_counts_its_entries():
    made = Account(carrier="VANCE", entries=(an_entry(),))  # type: ignore[arg-type]
    assert len(made) == 1


def test_an_account_prints_its_balance():
    made = Account(carrier="VANCE", entries=(an_entry(),))  # type: ignore[arg-type]
    assert str(made) == "VANCE $1,000.00 over 1 entries"


def test_running_shows_the_balance_after_each_entry():
    got = running((an_entry(), a_charge(sequence=2, amount=cents(30000))))
    assert [int(balance) for _, balance in got] == [100000, 70000]


def test_running_of_nothing_is_empty():
    assert running(()) == []
