import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.rig.axle import Axle
from jeepdolly.rig.dolly import Dolly, Hitch, attach
from jeepdolly.units.length import feet, inches
from jeepdolly.units.mass import pounds

from .conftest import drive


def a_dolly(**over: object) -> Dolly:
    """A two axle jeep, with any part of it swapped out."""
    kw: dict[str, object] = {
        "kind": Hitch.JEEP,
        "axles": (drive(3000), drive(3000)),
        "spacings": (feet(4),),
        "hitch": feet(9),
        "capacity": pounds(40000),
    }
    kw.update(over)
    return Dolly(**kw)  # type: ignore[arg-type]


def test_dolly_counts_its_axles():
    assert a_dolly().count == 2


def test_dolly_tare_is_the_sum_of_its_axles():
    assert int(a_dolly().tare) == 6000


def test_dolly_length_is_its_internal_spacing():
    assert int(a_dolly().length) == 48


def test_one_axle_dolly_has_no_length():
    solo = a_dolly(axles=(drive(3000),), spacings=())
    assert int(solo.length) == 0


def test_dolly_takes_the_kind_as_text():
    assert a_dolly(kind="booster").kind is Hitch.BOOSTER


def test_dolly_refuses_an_unknown_kind():
    with pytest.raises(ValueError, match="booster|jeep|not a valid"):
        a_dolly(kind="wagon")


def test_dolly_refuses_no_axles():
    with pytest.raises(BadValueError):
        a_dolly(axles=(), spacings=())


def test_dolly_refuses_a_spacing_count_that_does_not_match():
    with pytest.raises(BadValueError):
        a_dolly(axles=(drive(3000), drive(3000)), spacings=())


def test_dolly_refuses_a_tight_hitch():
    with pytest.raises(BadValueError):
        a_dolly(hitch=inches(6))


def test_dolly_refuses_a_steering_axle():
    steer_axle = Axle(weight=pounds(3000), tires=2, tire_width=inches(11), steering=True)
    with pytest.raises(BadValueError):
        a_dolly(axles=(steer_axle,), spacings=())


def test_attach_adds_the_dolly_axles(five_axle):
    made = attach(five_axle, a_dolly(), at=2, transfer=pounds(20000))
    assert made.count == 7


def test_attach_adds_the_dolly_tare_to_the_gross(five_axle):
    made = attach(five_axle, a_dolly(), at=2, transfer=pounds(20000))
    assert int(made.gross) == int(five_axle.gross) + 6000


def test_attach_conserves_the_transfer(five_axle):
    made = attach(five_axle, a_dolly(), at=2, transfer=pounds(20000))
    on_dolly = int(made.axles[3].weight) + int(made.axles[4].weight)
    assert on_dolly == 6000 + 20000


def test_attach_takes_the_transfer_off_the_drives(five_axle):
    made = attach(five_axle, a_dolly(), at=2, transfer=pounds(20000))
    drives = int(made.axles[1].weight) + int(made.axles[2].weight)
    assert drives == 34000 - 20000


def test_attach_leaves_the_trailer_alone_for_a_jeep(five_axle):
    made = attach(five_axle, a_dolly(), at=2, transfer=pounds(20000))
    assert [int(a.weight) for a in made.axles[5:]] == [17000, 17000]


def test_attach_never_relieves_the_steer_axle(five_axle):
    made = attach(five_axle, a_dolly(), at=2, transfer=pounds(20000))
    assert int(made.axles[0].weight) == 12000


def test_attach_splits_the_transfer_evenly_across_the_dolly(five_axle):
    made = attach(five_axle, a_dolly(), at=2, transfer=pounds(20001))
    assert int(made.axles[3].weight) - int(made.axles[4].weight) == 1


def test_attach_names_the_new_rig(five_axle):
    made = attach(five_axle, a_dolly(), at=2, transfer=pounds(20000))
    assert made.name == "3S2-J"


def test_attach_names_a_booster_rig(five_axle):
    booster = a_dolly(kind=Hitch.BOOSTER)
    made = attach(five_axle, booster, at=4, transfer=pounds(10000))
    assert made.name == "3S2-B"


def test_booster_goes_on_the_back(five_axle):
    booster = a_dolly(kind=Hitch.BOOSTER)
    made = attach(five_axle, booster, at=4, transfer=pounds(10000))
    assert made.count == 7
    assert int(made.axles[5].weight) + int(made.axles[6].weight) == 6000 + 10000


def test_booster_relieves_everything_but_the_steer(five_axle):
    booster = a_dolly(kind=Hitch.BOOSTER)
    made = attach(five_axle, booster, at=4, transfer=pounds(10000))
    assert int(made.axles[0].weight) == 12000
    assert sum(int(a.weight) for a in made.axles[1:5]) == 68000 - 10000


def test_booster_refuses_a_hitch_that_is_not_the_back(five_axle):
    with pytest.raises(BadValueError):
        attach(five_axle, a_dolly(kind=Hitch.BOOSTER), at=2, transfer=pounds(1000))


def test_attach_refuses_a_transfer_over_the_rating(five_axle):
    with pytest.raises(BadValueError):
        attach(five_axle, a_dolly(capacity=pounds(5000)), at=2, transfer=pounds(6000))


def test_attach_refuses_a_transfer_bigger_than_the_side_carries(five_axle):
    with pytest.raises(BadValueError):
        attach(five_axle, a_dolly(), at=2, transfer=pounds(40000))


def test_a_jeep_hitched_behind_the_last_axle_is_refused(five_axle):
    with pytest.raises(BadValueError):
        attach(five_axle, a_dolly(), at=4, transfer=pounds(1000))


def test_attach_refuses_a_hitch_off_the_end(five_axle):
    with pytest.raises(BadValueError):
        attach(five_axle, a_dolly(), at=5, transfer=pounds(1000))


def test_attach_refuses_a_bool_hitch_point(five_axle):
    with pytest.raises(BadValueError):
        attach(five_axle, a_dolly(), at=True, transfer=pounds(1000))


def test_attach_of_zero_transfer_only_adds_tare(five_axle):
    made = attach(five_axle, a_dolly(), at=2, transfer=pounds(0))
    assert int(made.gross) == int(five_axle.gross) + 6000
    assert int(made.axles[1].weight) == 17000


def test_attach_keeps_the_spacing_count_right(five_axle):
    made = attach(five_axle, a_dolly(), at=2, transfer=pounds(20000))
    assert len(made.spacings) == made.count - 1


def test_attach_puts_the_hitch_gap_on_both_sides_of_a_jeep(five_axle):
    made = attach(five_axle, a_dolly(), at=2, transfer=pounds(20000))
    assert int(made.spacings[2]) == 108
    assert int(made.spacings[4]) == 108
