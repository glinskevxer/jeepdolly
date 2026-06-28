import datetime as dt

import pytest

from jeepdolly.errors import NotFoundError
from jeepdolly.party.carrier import Carrier
from jeepdolly.party.surety import Certificate, Cover
from jeepdolly.store.carriers import CarrierStore
from jeepdolly.store.surety import SuretyStore
from jeepdolly.units.clock import DaySpan
from jeepdolly.units.money import cents

JAN = dt.date(2025, 1, 1)
JUN = dt.date(2025, 6, 30)
DEC = dt.date(2025, 12, 31)


def a_certificate(**over: object) -> Certificate:
    kw: dict[str, object] = {
        "carrier": "VANCE",
        "cover": Cover.BOND,
        "insurer": "Cascade Surety",
        "policy": "SB-4471",
        "amount": cents(100_000_00),
        "span": DaySpan(JAN, DEC),
    }
    kw.update(over)
    return Certificate(**kw)  # type: ignore[arg-type]


@pytest.fixture
def store(office):
    """A surety store with two carriers on file and nothing lodged."""
    carriers = CarrierStore(office)
    carriers.add(
        Carrier(code="VANCE", name="Vance Heavy Haul", usdot=1184062, home_state="MT")  # type: ignore[arg-type]
    )
    carriers.add(
        Carrier(code="OTHER", name="Other Haul", usdot=2, home_state="ID")  # type: ignore[arg-type]
    )
    return SuretyStore(office)


def test_a_store_with_no_certificates_is_empty(store):
    assert store.count() == 0
    assert len(store) == 0


def test_a_lodged_certificate_round_trips(store):
    store.put(a_certificate())
    found = store.get("VANCE", Cover.BOND, "SB-4471")
    assert found.insurer == "Cascade Surety"
    assert int(found.amount) == 100_000_00
    assert found.span == DaySpan(JAN, DEC)


def test_a_certificate_for_an_unknown_carrier_is_refused(store):
    with pytest.raises(NotFoundError):
        store.put(a_certificate(carrier="GHOST"))


def test_a_missing_certificate_comes_back_as_none(store):
    assert store.find("VANCE", Cover.BOND, "SB-4471") is None


def test_getting_a_missing_certificate_raises(store):
    with pytest.raises(NotFoundError):
        store.get("VANCE", Cover.BOND, "SB-4471")


def test_writing_the_same_policy_twice_replaces_it(store):
    store.put(a_certificate())
    store.put(a_certificate(amount=cents(250_000_00)))
    assert store.count() == 1
    assert int(store.get("VANCE", Cover.BOND, "SB-4471").amount) == 250_000_00


def test_two_policies_for_one_cover_both_stay(store):
    store.put(a_certificate())
    store.put(a_certificate(policy="SB-9000"))
    assert store.count() == 2


def test_a_carrier_listing_is_longest_running_first(store):
    store.put(a_certificate(policy="SHORT", span=DaySpan(JAN, JUN)))
    store.put(a_certificate(policy="LONG"))
    assert [one.policy for one in store.for_carrier("VANCE")] == ["LONG", "SHORT"]


def test_a_listing_for_an_unknown_carrier_raises(store):
    with pytest.raises(NotFoundError):
        store.for_carrier("GHOST")


def test_another_carriers_paper_is_not_listed(store):
    store.put(a_certificate())
    store.put(a_certificate(carrier="OTHER", policy="X-1"))
    assert [one.carrier for one in store.for_carrier("VANCE")] == ["VANCE"]


def test_only_the_cover_good_that_day_is_in_force(store):
    store.put(a_certificate())
    store.put(
        a_certificate(cover=Cover.CARGO, policy="C-1", span=DaySpan(JAN, dt.date(2025, 3, 1)))
    )
    assert [one.cover for one in store.in_force("VANCE", JUN)] == [Cover.BOND]


def test_the_longest_running_policy_wins_a_cover(store):
    store.put(a_certificate(policy="OLD", span=DaySpan(JAN, dt.date(2025, 8, 1))))
    store.put(a_certificate(policy="NEW"))
    held = store.in_force("VANCE", JUN)
    assert [one.policy for one in held] == ["NEW"]


def test_in_force_for_an_unknown_carrier_raises(store):
    with pytest.raises(NotFoundError):
        store.in_force("GHOST", JUN)


def test_the_chase_list_crosses_every_carrier(store):
    store.put(a_certificate(span=DaySpan(JAN, dt.date(2025, 7, 10))))
    store.put(
        a_certificate(carrier="OTHER", policy="X-1", span=DaySpan(JAN, dt.date(2025, 7, 4)))
    )
    found = store.lapsing(JUN, 30)
    assert [one.carrier for one in found] == ["OTHER", "VANCE"]


def test_a_certificate_outside_the_chase_window_is_left_out(store):
    store.put(a_certificate())
    assert store.lapsing(JUN, 30) == []


def test_a_lapsed_certificate_is_not_chased(store):
    store.put(a_certificate(span=DaySpan(dt.date(2024, 1, 1), dt.date(2024, 6, 1))))
    assert store.lapsing(JUN, 400) == []


def test_a_removed_certificate_is_gone(store):
    store.put(a_certificate())
    store.remove("VANCE", Cover.BOND, "SB-4471")
    assert store.count() == 0


def test_removing_a_missing_certificate_raises(store):
    with pytest.raises(NotFoundError):
        store.remove("VANCE", Cover.BOND, "SB-4471")


def test_retiring_a_carrier_takes_its_paper_with_it(store, office):
    store.put(a_certificate())
    office.commit()
    office.execute("PRAGMA foreign_keys = ON")
    office.execute("DELETE FROM carrier WHERE code = 'VANCE'")
    assert store.count() == 0
