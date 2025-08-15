import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.rig.axle import MAX_TIRES, POUNDS_PER_TIRE_INCH, Axle
from jeepdolly.units.length import inches
from jeepdolly.units.mass import pounds


def an_axle(**over: object) -> Axle:
    """An ordinary drive axle, with any part of it swapped out."""
    kw: dict[str, object] = {"weight": pounds(17000), "tires": 4, "tire_width": inches(11)}
    kw.update(over)
    return Axle(**kw)  # type: ignore[arg-type]


def test_axle_keeps_its_weight():
    assert int(an_axle().weight) == 17000


def test_axle_defaults_to_fixed():
    axle = an_axle()
    assert not axle.liftable
    assert not axle.steering


def test_axle_refuses_zero_tires():
    with pytest.raises(BadValueError):
        an_axle(tires=0)


def test_axle_refuses_too_many_tires():
    with pytest.raises(BadValueError):
        an_axle(tires=MAX_TIRES + 1)


def test_axle_takes_the_most_tires():
    assert an_axle(tires=MAX_TIRES).tires == MAX_TIRES


def test_axle_refuses_a_bool_tire_count():
    with pytest.raises(BadValueError):
        an_axle(tires=True)


def test_axle_refuses_a_float_tire_count():
    with pytest.raises(BadValueError):
        an_axle(tires=4.0)


def test_axle_refuses_zero_tire_width():
    with pytest.raises(BadValueError):
        an_axle(tire_width=inches(0))


def test_axle_refuses_a_negative_weight():
    with pytest.raises(BadValueError):
        an_axle(weight=-1)


def test_steer_axle_takes_two_tires():
    axle = an_axle(tires=2, steering=True)
    assert axle.steering


def test_steer_axle_refuses_four_tires():
    with pytest.raises(BadValueError):
        an_axle(tires=4, steering=True)


def test_steer_axle_refuses_to_lift():
    with pytest.raises(BadValueError):
        an_axle(tires=2, steering=True, liftable=True)


def test_liftable_axle_is_allowed_on_its_own():
    assert an_axle(liftable=True).liftable


def test_tread_is_tires_times_width():
    assert int(an_axle(tires=4, tire_width=inches(11)).tread) == 44


def test_narrow_tire_is_under_eleven_inches():
    assert an_axle(tire_width=inches(10)).narrow
    assert not an_axle(tire_width=inches(11)).narrow


def test_tire_limit_uses_the_pounds_per_inch_rule():
    axle = an_axle(tires=4, tire_width=inches(11))
    assert int(axle.tire_limit) == 4 * 11 * POUNDS_PER_TIRE_INCH


def test_axle_within_its_rubber_is_not_over():
    assert not an_axle(weight=pounds(26400), tires=4, tire_width=inches(11)).over_tires


def test_axle_one_pound_past_its_rubber_is_over():
    assert an_axle(weight=pounds(26401), tires=4, tire_width=inches(11)).over_tires


def test_reloaded_changes_only_the_weight():
    axle = an_axle(liftable=True)
    lighter = axle.reloaded(pounds(9000))
    assert int(lighter.weight) == 9000
    assert lighter.tires == axle.tires
    assert lighter.tire_width == axle.tire_width
    assert lighter.liftable is axle.liftable


def test_reloaded_keeps_the_steer_flag():
    axle = an_axle(tires=2, steering=True)
    assert axle.reloaded(pounds(12000)).steering


def test_axles_with_the_same_parts_are_equal():
    assert an_axle() == an_axle()


def test_two_equal_axles_hash_the_same():
    assert len({an_axle(), an_axle()}) == 1


def test_an_axle_cannot_be_written_to():
    axle = an_axle()
    with pytest.raises(AttributeError):
        axle.tires = 8  # type: ignore[misc]


def test_axle_prints_its_kind():
    assert str(an_axle()).startswith("fixed")
    assert str(an_axle(liftable=True)).startswith("lift")
    assert str(an_axle(tires=2, steering=True)).startswith("steer")


def test_axle_prints_its_rubber():
    assert str(an_axle()) == 'fixed 17,000 lb on 4 at 11"'


def test_axle_prints_the_tire_width_in_plain_inches():
    assert str(an_axle(tire_width=inches(24))).endswith('24"')
