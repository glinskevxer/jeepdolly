import pytest

from jeepdolly.errors import BadValueError, NotFoundError
from jeepdolly.rig.load import Load
from jeepdolly.store.loads import LoadStore
from jeepdolly.units.length import feet, feet_inches
from jeepdolly.units.mass import pounds


def a_load(**over: object) -> Load:
    kw: dict[str, object] = {
        "description": "step-up transformer",
        "weight": pounds(148000),
        "width": feet_inches(12, 6),
        "height": feet_inches(15, 2),
        "length": feet(48),
        "divisible": False,
        "reason": "single-piece",
    }
    kw.update(over)
    return Load(**kw)  # type: ignore[arg-type]


@pytest.fixture
def store(office):
    """A load store over a migrated office."""
    return LoadStore(office)


def test_a_new_store_is_empty(store):
    assert store.count() == 0
    assert store.all() == []


def test_add_hands_back_a_key(store):
    assert store.add(a_load()) == 1


def test_keys_climb(store):
    store.add(a_load())
    assert store.add(a_load()) == 2


def test_add_then_get_round_trips(store):
    key = store.add(a_load())
    assert store.get(key) == a_load()


def test_the_overhangs_round_trip(store):
    key = store.add(a_load(front_overhang=feet(3), rear_overhang=feet(9)))
    read = store.get(key)
    assert int(read.front_overhang) == 36
    assert int(read.rear_overhang) == 108


def test_the_divisible_flag_round_trips_as_a_bool(store):
    key = store.add(a_load(divisible=True, reason=""))
    assert store.get(key).divisible is True


def test_the_reason_round_trips(store):
    key = store.add(a_load())
    assert store.get(key).reason == "single-piece"


def test_get_raises_when_it_is_not_there(store):
    with pytest.raises(NotFoundError):
        store.get(1)


def test_find_returns_none_when_it_is_not_there(store):
    assert store.find(1) is None


def test_find_returns_the_load(store):
    key = store.add(a_load())
    assert store.find(key) == a_load()


def test_save_overwrites(store):
    key = store.add(a_load())
    store.save(key, a_load(description="generator stator"))
    assert store.get(key).description == "generator stator"


def test_save_refuses_a_key_that_is_not_there(store):
    with pytest.raises(NotFoundError):
        store.save(1, a_load())


def test_save_returns_what_it_wrote(store):
    key = store.add(a_load())
    assert store.save(key, a_load(width=feet(14))) == a_load(width=feet(14))


def test_all_is_oldest_first(store):
    store.add(a_load(description="first"))
    store.add(a_load(description="second"))
    assert [x.description for x in store.all()] == ["first", "second"]


def test_keys_are_oldest_first(store):
    store.add(a_load())
    store.add(a_load())
    assert store.keys() == [1, 2]


def test_nondivisible_leaves_out_the_divisible(store):
    store.add(a_load())
    store.add(a_load(description="sand", divisible=True, reason=""))
    assert [x.description for x in store.nondivisible()] == ["step-up transformer"]


def test_remove_deletes(store):
    key = store.add(a_load())
    store.remove(key)
    assert store.find(key) is None


def test_remove_raises_when_it_is_not_there(store):
    with pytest.raises(NotFoundError):
        store.remove(1)


def test_count_and_len_agree(store):
    store.add(a_load())
    store.add(a_load())
    assert store.count() == len(store) == 2


def test_a_row_edited_by_hand_into_a_contradiction_fails_on_the_way_out(store, office):
    key = store.add(a_load())
    office.execute("UPDATE load_item SET divisible = 1 WHERE id = ?", (key,))
    with pytest.raises(BadValueError):
        store.get(key)


def test_the_table_refuses_a_zero_width(store, office):
    with pytest.raises(Exception, match="CHECK"):
        office.execute(
            "INSERT INTO load_item (description, weight, width, height, length)"
            " VALUES ('x', 1, 0, 1, 1)"
        )
