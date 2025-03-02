import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.rig.load import MAX_DESCRIPTION, NONDIVISIBLE_REASONS, Load
from jeepdolly.units.length import feet, feet_inches, inches
from jeepdolly.units.mass import pounds


def a_load(**over: object) -> Load:
    """A transformer on a lowboy, with any part of it swapped out."""
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


def test_load_keeps_its_description():
    assert a_load().description == "step-up transformer"


def test_load_collapses_inner_whitespace():
    assert a_load(description="step   up\ttransformer").description == "step up transformer"


def test_load_refuses_an_empty_description():
    with pytest.raises(BadValueError):
        a_load(description="   ")


def test_load_refuses_a_description_that_is_too_long():
    with pytest.raises(BadValueError):
        a_load(description="x" * (MAX_DESCRIPTION + 1))


def test_load_takes_the_longest_description():
    assert len(a_load(description="x" * MAX_DESCRIPTION).description) == MAX_DESCRIPTION


def test_load_refuses_a_description_that_is_not_text():
    with pytest.raises(BadValueError):
        a_load(description=12)


def test_load_refuses_zero_width():
    with pytest.raises(BadValueError):
        a_load(width=inches(0))


def test_load_refuses_zero_height():
    with pytest.raises(BadValueError):
        a_load(height=inches(0))


def test_load_refuses_zero_length():
    with pytest.raises(BadValueError):
        a_load(length=inches(0))


def test_load_allows_zero_overhang():
    assert int(a_load().overhang) == 0


def test_overall_length_adds_both_overhangs():
    load = a_load(front_overhang=feet(3), rear_overhang=feet(9))
    assert int(load.overall_length) == (48 + 3 + 9) * 12


def test_overhang_sums_the_two_ends():
    load = a_load(front_overhang=feet(3), rear_overhang=feet(9))
    assert int(load.overhang) == 12 * 12


def test_divisible_load_may_not_be_permitted_overweight():
    load = a_load(divisible=True, reason="")
    assert not load.permittable_overweight


def test_nondivisible_load_may_be_permitted_overweight():
    assert a_load().permittable_overweight


def test_divisible_load_gives_its_refusal():
    load = a_load(divisible=True, reason="")
    assert "divisible" in load.refusal()


def test_nondivisible_load_has_no_refusal():
    assert a_load().refusal() == ""


def test_divisible_load_refuses_a_reason():
    with pytest.raises(BadValueError):
        a_load(divisible=True, reason="single-piece")


def test_nondivisible_load_needs_a_reason():
    with pytest.raises(BadValueError):
        a_load(reason="")


def test_nondivisible_load_refuses_an_unknown_reason():
    with pytest.raises(BadValueError):
        a_load(reason="customer says so")


@pytest.mark.parametrize("reason", NONDIVISIBLE_REASONS)
def test_every_listed_reason_is_accepted(reason):
    assert a_load(reason=reason).reason == reason


def test_load_refuses_a_non_bool_divisible():
    with pytest.raises(BadValueError):
        a_load(divisible="no")


def test_load_defaults_to_divisible():
    load = Load(
        description="sand",
        weight=pounds(50000),
        width=feet(8),
        height=feet(10),
        length=feet(40),
    )
    assert load.divisible


def test_load_is_frozen():
    with pytest.raises(AttributeError):
        a_load().width = feet(8)  # type: ignore[misc]


def test_loads_with_the_same_parts_are_equal():
    assert a_load() == a_load()


def test_load_prints_its_size():
    assert str(a_load()) == "step-up transformer, 148,000 lb, 12'6\" wide by 15'2\" high"
