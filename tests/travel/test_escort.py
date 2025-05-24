import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.rig.load import Load
from jeepdolly.travel.escort import (
    ORDINARY,
    Escort,
    EscortSchedule,
    Role,
    escort_count,
    escorts_for,
)
from jeepdolly.units.length import feet, feet_inches
from jeepdolly.units.mass import pounds


def a_load(**over: object) -> Load:
    kw: dict[str, object] = {
        "description": "excavator",
        "weight": pounds(96000),
        "width": feet_inches(8, 6),
        "height": feet_inches(13, 6),
        "length": feet(48),
        "divisible": False,
        "reason": "single-piece",
    }
    kw.update(over)
    return Load(**kw)  # type: ignore[arg-type]


def roles(load: Load) -> list[Role]:
    """The roles called for, in the order the office lists them."""
    return [e.role for e in escorts_for(load)]


def test_a_legal_load_needs_nothing():
    assert escorts_for(a_load()) == ()
    assert escort_count(a_load()) == 0


def test_twelve_feet_exactly_needs_nothing():
    assert roles(a_load(width=feet(12))) == []


def test_one_inch_over_twelve_feet_needs_a_rear_car():
    assert roles(a_load(width=feet_inches(12, 1))) == [Role.REAR]


def test_over_fourteen_feet_needs_a_front_car_too():
    assert roles(a_load(width=feet_inches(14, 1))) == [Role.FRONT, Role.REAR]


def test_over_sixteen_feet_needs_the_police():
    assert roles(a_load(width=feet_inches(16, 1))) == [Role.POLICE, Role.FRONT, Role.REAR]


def test_a_long_load_needs_a_rear_car():
    assert roles(a_load(length=feet(110))) == [Role.REAR]


def test_a_load_exactly_at_the_length_needs_nothing():
    assert roles(a_load(length=feet(100))) == []


def test_the_overhang_counts_toward_the_escort_length():
    assert roles(a_load(length=feet(95), rear_overhang=feet(10))) == [Role.REAR]


def test_a_tall_load_needs_a_height_pole():
    assert roles(a_load(height=feet(16))) == [Role.HEIGHT_POLE]


def test_a_load_exactly_at_the_pole_height_needs_nothing():
    assert roles(a_load(height=feet_inches(15, 6))) == []


def test_a_long_rear_overhang_needs_a_rear_car():
    assert roles(a_load(rear_overhang=feet(22), length=feet(40))) == [Role.REAR]


def test_two_rules_calling_for_a_rear_car_produce_one_car():
    made = escorts_for(a_load(width=feet(13), length=feet(110)))
    rear = [e for e in made if e.role is Role.REAR]
    assert len(rear) == 1
    assert len(rear[0].reasons) == 2


def test_the_reasons_name_the_thresholds():
    made = escorts_for(a_load(width=feet(13)))
    assert "12'" in made[0].reasons[0]


def test_a_wide_tall_long_load_needs_four_vehicles():
    made = a_load(width=feet(17), height=feet(17), length=feet(120))
    assert escort_count(made) == 4


def test_the_police_come_first_in_the_listing():
    made = a_load(width=feet(17), height=feet(17))
    assert escorts_for(made)[0].role is Role.POLICE


def test_the_height_pole_comes_before_the_pilot_cars():
    made = a_load(width=feet(13), height=feet(17))
    assert [e.role for e in escorts_for(made)] == [Role.HEIGHT_POLE, Role.REAR]


def test_an_escort_prints_its_reasons():
    made = escorts_for(a_load(width=feet(13)))[0]
    assert str(made).startswith("rear: width over")


def test_an_escort_refuses_no_reason():
    with pytest.raises(BadValueError):
        Escort(role=Role.REAR, reasons=())


def test_a_stricter_schedule_calls_for_more():
    strict = EscortSchedule(
        name="metro",
        one_escort_width=feet(10),
        two_escort_width=feet(12),
        police_width=feet(14),
        escort_length=feet(80),
        pole_height=feet(14),
        escort_rear_overhang=feet(15),
    )
    assert escorts_for(a_load(width=feet(11)), strict)[0].role is Role.REAR
    assert escorts_for(a_load(width=feet(11))) == ()


def test_a_schedule_refuses_a_second_width_below_the_first():
    with pytest.raises(BadValueError):
        EscortSchedule(
            name="odd",
            one_escort_width=feet(14),
            two_escort_width=feet(12),
            police_width=feet(16),
            escort_length=feet(100),
            pole_height=feet(15),
            escort_rear_overhang=feet(20),
        )


def test_a_schedule_refuses_a_police_width_below_the_second():
    with pytest.raises(BadValueError):
        EscortSchedule(
            name="odd",
            one_escort_width=feet(12),
            two_escort_width=feet(14),
            police_width=feet(13),
            escort_length=feet(100),
            pole_height=feet(15),
            escort_rear_overhang=feet(20),
        )


def test_a_schedule_refuses_an_empty_name():
    with pytest.raises(BadValueError):
        EscortSchedule(
            name=" ",
            one_escort_width=feet(12),
            two_escort_width=feet(14),
            police_width=feet(16),
            escort_length=feet(100),
            pole_height=feet(15),
            escort_rear_overhang=feet(20),
        )


def test_the_ordinary_schedule_is_twelve_fourteen_sixteen():
    assert int(ORDINARY.one_escort_width) == 144
    assert int(ORDINARY.two_escort_width) == 168
    assert int(ORDINARY.police_width) == 192
