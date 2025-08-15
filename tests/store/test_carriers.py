import pytest

from jeepdolly.errors import BadValueError, ConflictError, NotFoundError
from jeepdolly.party.carrier import Carrier
from jeepdolly.store.carriers import CarrierStore


def a_carrier(**over: object) -> Carrier:
    kw: dict[str, object] = {
        "code": "VANCE",
        "name": "Vance Heavy Haul",
        "usdot": 1184062,
        "home_state": "MT",
    }
    kw.update(over)
    return Carrier(**kw)  # type: ignore[arg-type]


@pytest.fixture
def store(office):
    """A carrier store over a migrated office."""
    return CarrierStore(office)


def test_a_new_store_is_empty(store):
    assert store.count() == 0
    assert store.all() == []


def test_add_then_get_round_trips(store):
    store.add(a_carrier())
    assert store.get("VANCE") == a_carrier()


def test_add_returns_what_it_wrote(store):
    assert store.add(a_carrier()) == a_carrier()


def test_get_normalises_the_key(store):
    store.add(a_carrier())
    assert store.get("vance").code == "VANCE"


def test_get_raises_when_it_is_not_there(store):
    with pytest.raises(NotFoundError):
        store.get("VANCE")


def test_get_refuses_a_key_that_is_not_a_code(store):
    with pytest.raises(BadValueError):
        store.get("!")


def test_find_returns_none_when_it_is_not_there(store):
    assert store.find("VANCE") is None


def test_find_returns_the_carrier(store):
    store.add(a_carrier())
    assert store.find("VANCE") == a_carrier()


def test_add_refuses_a_code_that_is_taken(store):
    store.add(a_carrier())
    with pytest.raises(ConflictError):
        store.add(a_carrier(name="Someone Else", usdot=99))


def test_add_refuses_a_usdot_that_is_taken(store):
    store.add(a_carrier())
    with pytest.raises(ConflictError):
        store.add(a_carrier(code="OTHER", name="Other Haul"))


def test_save_overwrites_what_was_there(store):
    store.add(a_carrier())
    store.save(a_carrier(name="Vance Transport"))
    assert store.get("VANCE").name == "Vance Transport"


def test_save_refuses_a_carrier_that_is_not_there(store):
    with pytest.raises(NotFoundError):
        store.save(a_carrier())


def test_save_refuses_a_usdot_belonging_to_someone_else(store):
    store.add(a_carrier())
    store.add(a_carrier(code="OTHER", name="Other Haul", usdot=222))
    with pytest.raises(ConflictError):
        store.save(a_carrier(code="OTHER", name="Other Haul", usdot=1184062))


def test_save_keeps_its_own_usdot(store):
    store.add(a_carrier())
    store.save(a_carrier(name="Vance Transport"))
    assert store.get("VANCE").usdot == 1184062


def test_save_writes_back_a_retired_carrier(store):
    store.add(a_carrier())
    store.save(a_carrier().retired())
    assert not store.get("VANCE").active


def test_by_usdot_finds_the_carrier(store):
    store.add(a_carrier())
    assert store.by_usdot(1184062).code == "VANCE"


def test_by_usdot_raises_when_there_is_none(store):
    with pytest.raises(NotFoundError):
        store.by_usdot(1184062)


def test_all_is_in_code_order(store):
    store.add(a_carrier(code="ZED", name="Zed Haul", usdot=1))
    store.add(a_carrier())
    store.add(a_carrier(code="ACE", name="Ace Haul", usdot=2))
    assert [c.code for c in store.all()] == ["ACE", "VANCE", "ZED"]


def test_active_leaves_out_the_retired(store):
    store.add(a_carrier())
    store.add(a_carrier(code="GONE", name="Gone Haul", usdot=2, active=False))
    assert [c.code for c in store.active()] == ["VANCE"]


def test_search_matches_the_name(store):
    store.add(a_carrier())
    assert [c.code for c in store.search("heavy")] == ["VANCE"]


def test_search_matches_the_code(store):
    store.add(a_carrier())
    assert [c.code for c in store.search("van")] == ["VANCE"]


def test_search_ignores_the_case_it_is_given(store):
    store.add(a_carrier())
    assert store.search("VANCE HEAVY")


def test_search_finds_nothing_when_nothing_matches(store):
    store.add(a_carrier())
    assert store.search("zzz") == []


def test_remove_takes_the_record_off_file(store):
    store.add(a_carrier())
    store.remove("VANCE")
    assert store.find("VANCE") is None


def test_remove_raises_when_it_is_not_there(store):
    with pytest.raises(NotFoundError):
        store.remove("VANCE")


def test_count_and_len_agree(store):
    store.add(a_carrier())
    store.add(a_carrier(code="OTHER", name="Other Haul", usdot=2))
    assert store.count() == len(store) == 2


def test_contains_takes_a_code(store):
    store.add(a_carrier())
    assert "VANCE" in store
    assert "OTHER" not in store


def test_contains_of_something_that_is_not_a_string_is_false(store):
    assert 12 not in store


def test_the_active_flag_round_trips_as_a_bool(store):
    store.add(a_carrier(active=False))
    assert store.get("VANCE").active is False
