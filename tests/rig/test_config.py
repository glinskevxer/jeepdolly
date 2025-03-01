import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.rig.config import MAX_AXLES, MIN_SPACING, Configuration, Run
from jeepdolly.units.length import feet, inches
from jeepdolly.units.mass import pounds

from .conftest import drive, rig, steer


def test_configuration_counts_its_axles(five_axle):
    assert five_axle.count == 5


def test_configuration_sums_the_gross(five_axle):
    assert int(five_axle.gross) == 12000 + 17000 * 4


def test_wheelbase_is_the_sum_of_the_spacings(five_axle):
    assert int(five_axle.wheelbase) == (15 + 4 + 30 + 4) * 12


def test_configuration_normalises_the_name():
    made = rig("3s2", [steer(), drive()], [feet(15)])
    assert made.name == "3S2"


def test_configuration_refuses_one_axle():
    with pytest.raises(BadValueError):
        rig("SOLO", [steer()], [])


def test_configuration_refuses_too_many_axles():
    axles = [steer()] + [drive() for _ in range(MAX_AXLES)]
    gaps = [feet(4) for _ in range(MAX_AXLES)]
    with pytest.raises(BadValueError):
        rig("LONG", axles, gaps)


def test_configuration_refuses_a_spacing_count_that_does_not_match():
    with pytest.raises(BadValueError):
        rig("BAD", [steer(), drive(), drive()], [feet(15)])


def test_configuration_refuses_axles_too_close():
    with pytest.raises(BadValueError):
        rig("TIGHT", [steer(), drive()], [inches(int(MIN_SPACING) - 1)])


def test_configuration_takes_the_minimum_spacing():
    made = rig("TIGHT", [steer(), drive()], [MIN_SPACING])
    assert int(made.spacings[0]) == int(MIN_SPACING)


def test_configuration_refuses_a_rig_that_does_not_steer():
    with pytest.raises(BadValueError):
        rig("NOSTEER", [drive(), drive()], [feet(15)])


def test_configuration_refuses_two_steer_axles():
    with pytest.raises(BadValueError):
        rig("TWOSTEER", [steer(), steer()], [feet(15)])


def test_extreme_of_a_single_axle_is_zero(five_axle):
    assert int(five_axle.extreme(2, 2)) == 0


def test_extreme_of_a_tandem(five_axle):
    assert int(five_axle.extreme(1, 2)) == 48


def test_extreme_of_the_whole_rig_is_the_wheelbase(five_axle):
    assert five_axle.extreme(0, 4) == five_axle.wheelbase


def test_weight_of_a_single_axle(five_axle):
    assert int(five_axle.weight_of(0, 0)) == 12000


def test_weight_of_a_tandem(five_axle):
    assert int(five_axle.weight_of(1, 2)) == 34000


def test_weight_of_the_whole_rig_is_the_gross(five_axle):
    assert five_axle.weight_of(0, 4) == five_axle.gross


def test_index_out_of_range_is_refused(five_axle):
    with pytest.raises(BadValueError):
        five_axle.extreme(0, 5)


def test_negative_index_is_refused(five_axle):
    with pytest.raises(BadValueError):
        five_axle.extreme(-1, 2)


def test_backwards_range_is_refused(five_axle):
    with pytest.raises(BadValueError):
        five_axle.weight_of(3, 1)


def test_bool_index_is_refused(five_axle):
    with pytest.raises(BadValueError):
        five_axle.extreme(True, 2)


def test_float_index_is_refused(five_axle):
    with pytest.raises(BadValueError):
        five_axle.extreme(0.0, 2)


def test_runs_counts_every_consecutive_stretch(five_axle):
    assert len(list(five_axle.runs())) == 5 * 6 // 2


def test_runs_start_with_the_singles(five_axle):
    first_five = list(five_axle.runs())[:5]
    assert all(r.single for r in first_five)


def test_runs_end_with_the_whole_rig(five_axle):
    last = list(five_axle.runs())[-1]
    assert (last.first, last.last) == (0, 4)


def test_run_counts_its_axles(five_axle):
    assert five_axle.run(1, 3).count == 3


def test_run_of_one_says_it_is_single(five_axle):
    assert five_axle.run(2, 2).single


def test_groups_splits_at_a_wide_gap(five_axle):
    groups = [(g.first, g.last) for g in five_axle.groups(feet(8))]
    assert groups == [(0, 0), (1, 2), (3, 4)]


def test_groups_of_the_whole_rig_when_nothing_is_wide(five_axle):
    groups = list(five_axle.groups(feet(40)))
    assert len(groups) == 1
    assert (groups[0].first, groups[0].last) == (0, 4)


def test_groups_are_all_singles_when_nothing_is_close(five_axle):
    groups = list(five_axle.groups(inches(1)))
    assert [g.count for g in groups] == [1, 1, 1, 1, 1]


def test_groups_run_of_four_stays_one_group(seven_axle):
    groups = [(g.first, g.last) for g in seven_axle.groups(feet(8))]
    assert groups == [(0, 0), (1, 2), (3, 6)]


def test_run_prints_a_single_axle(five_axle):
    assert str(five_axle.run(2, 2)) == "axle 3"


def test_run_prints_a_stretch(five_axle):
    assert str(five_axle.run(1, 2)) == "axles 2-3 over 4'"


def test_configuration_prints_its_shape(five_axle):
    assert str(five_axle) == "3S2 5 axles over 53'"


def test_run_orders_by_its_first_axle():
    a = Run(first=0, last=1, extreme=feet(4), weight=pounds(34000))
    b = Run(first=1, last=2, extreme=feet(4), weight=pounds(34000))
    assert sorted([b, a])[0] is a


def test_configuration_is_frozen(five_axle):
    with pytest.raises(AttributeError):
        five_axle.axles = ()


def test_configuration_accepts_a_list_of_axles():
    made = Configuration(name="X1", axles=[steer(), drive()], spacings=[feet(15)])  # type: ignore[arg-type]
    assert made.count == 2
