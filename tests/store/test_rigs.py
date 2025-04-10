import datetime as dt

import pytest

from jeepdolly.errors import BadValueError, ConflictError, NotFoundError
from jeepdolly.party.carrier import Carrier
from jeepdolly.rig.axle import Axle
from jeepdolly.rig.config import Configuration
from jeepdolly.store.carriers import CarrierStore
from jeepdolly.store.rigs import FiledRig, RigStore
from jeepdolly.units.length import feet, inches
from jeepdolly.units.mass import pounds

DAY = dt.date(2025, 4, 15)


def steer(weight: int = 12000) -> Axle:
    return Axle(weight=pounds(weight), tires=2, tire_width=inches(11), steering=True)


def drive(weight: int = 17000) -> Axle:
    return Axle(weight=pounds(weight), tires=4, tire_width=inches(11))


def a_config(name: str = "3S2") -> Configuration:
    return Configuration(
        name=name,  # type: ignore[arg-type]
        axles=(steer(), drive(), drive(), drive(), drive()),
        spacings=(feet(15), feet(4), feet(30), feet(4)),
    )


@pytest.fixture
def store(office):
    """A rig store with one carrier already on file."""
    CarrierStore(office).add(
        Carrier(code="VANCE", name="Vance Heavy Haul", usdot=1184062, home_state="MT")  # type: ignore[arg-type]
    )
    return RigStore(office)


def test_a_new_store_is_empty(store):
    assert store.count() == 0


def test_the_first_reference_is_one(store):
    assert store.next_reference() == "R-00001"


def test_add_files_under_the_next_reference(store):
    filed = store.add("VANCE", a_config(), DAY)
    assert filed.reference == "R-00001"


def test_references_climb(store):
    store.add("VANCE", a_config(), DAY)
    assert store.add("VANCE", a_config(), DAY).reference == "R-00002"


def test_add_round_trips_the_axles(store):
    filed = store.add("VANCE", a_config(), DAY)
    read = store.get(filed.reference)
    assert read.config.axles == a_config().axles


def test_add_round_trips_the_spacings(store):
    filed = store.add("VANCE", a_config(), DAY)
    assert store.get(filed.reference).config.spacings == a_config().spacings


def test_add_round_trips_the_name(store):
    filed = store.add("VANCE", a_config(), DAY)
    assert store.get(filed.reference).config.name == "3S2"


def test_add_round_trips_the_day(store):
    filed = store.add("VANCE", a_config(), DAY)
    assert store.get(filed.reference).recorded_on == DAY


def test_add_keeps_the_steer_flag(store):
    filed = store.add("VANCE", a_config(), DAY)
    assert store.get(filed.reference).config.axles[0].steering


def test_add_keeps_the_lift_flag(store):
    lifting = Configuration(
        name="LIFT",  # type: ignore[arg-type]
        axles=(
            steer(),
            Axle(weight=pounds(9000), tires=4, tire_width=inches(11), liftable=True),
        ),
        spacings=(feet(15),),
    )
    filed = store.add("VANCE", lifting, DAY)
    assert store.get(filed.reference).config.axles[1].liftable


def test_add_refuses_a_carrier_that_is_not_there(store):
    with pytest.raises(NotFoundError):
        store.add("NOBODY", a_config(), DAY)


def test_get_raises_when_it_is_not_there(store):
    with pytest.raises(NotFoundError):
        store.get("R-00001")


def test_get_refuses_a_key_that_is_not_a_reference(store):
    with pytest.raises(BadValueError):
        store.get("nonsense!")


def test_find_returns_none_when_it_is_not_there(store):
    assert store.find("R-00001") is None


def test_put_files_under_a_chosen_reference(store):
    filed = FiledRig(
        reference="R-00042",  # type: ignore[arg-type]
        carrier="VANCE",  # type: ignore[arg-type]
        config=a_config(),
        recorded_on=DAY,
    )
    store.put(filed)
    assert store.get("R-00042").config.name == "3S2"


def test_put_refuses_a_reference_that_is_taken(store):
    filed = FiledRig(
        reference="R-00042",  # type: ignore[arg-type]
        carrier="VANCE",  # type: ignore[arg-type]
        config=a_config(),
        recorded_on=DAY,
    )
    store.put(filed)
    with pytest.raises(ConflictError):
        store.put(filed)


def test_put_refuses_a_carrier_that_is_not_there(store):
    filed = FiledRig(
        reference="R-00042",  # type: ignore[arg-type]
        carrier="NOBODY",  # type: ignore[arg-type]
        config=a_config(),
        recorded_on=DAY,
    )
    with pytest.raises(NotFoundError):
        store.put(filed)


def test_the_next_reference_follows_a_chosen_one(store):
    store.put(
        FiledRig(
            reference="R-00042",  # type: ignore[arg-type]
            carrier="VANCE",  # type: ignore[arg-type]
            config=a_config(),
            recorded_on=DAY,
        )
    )
    assert store.next_reference() == "R-00043"


def test_for_carrier_finds_them_all(store):
    store.add("VANCE", a_config(), DAY)
    store.add("VANCE", a_config("3S3"), DAY)
    assert len(store.for_carrier("VANCE")) == 2


def test_for_carrier_of_someone_else_is_empty(store, office):
    CarrierStore(office).add(
        Carrier(code="OTHER", name="Other Haul", usdot=2, home_state="ID")  # type: ignore[arg-type]
    )
    store.add("VANCE", a_config(), DAY)
    assert store.for_carrier("OTHER") == []


def test_all_is_in_reference_order(store):
    store.add("VANCE", a_config(), DAY)
    store.add("VANCE", a_config("3S3"), DAY)
    assert [r.reference for r in store.all()] == ["R-00001", "R-00002"]


def test_remove_deletes_the_rig(store):
    store.add("VANCE", a_config(), DAY)
    store.remove("R-00001")
    assert store.find("R-00001") is None


def test_remove_takes_the_axles_with_it(store, office):
    store.add("VANCE", a_config(), DAY)
    store.remove("R-00001")
    assert office.execute("SELECT count(*) FROM rig_axle").fetchone()[0] == 0


def test_remove_raises_when_it_is_not_there(store):
    with pytest.raises(NotFoundError):
        store.remove("R-00001")


def test_count_and_len_agree(store):
    store.add("VANCE", a_config(), DAY)
    assert store.count() == len(store) == 1


def test_filed_rig_exposes_the_arrangement_name(store):
    filed = store.add("VANCE", a_config(), DAY)
    assert filed.name == "3S2"


def test_filed_rig_refuses_a_datetime():
    with pytest.raises(BadValueError):
        FiledRig(
            reference="R-00001",  # type: ignore[arg-type]
            carrier="VANCE",  # type: ignore[arg-type]
            config=a_config(),
            recorded_on=dt.datetime(2025, 4, 15, tzinfo=dt.UTC),
        )


def test_filed_rig_prints_its_reference_and_shape(store):
    filed = store.add("VANCE", a_config(), DAY)
    assert str(filed).startswith("R-00001 VANCE 3S2")
