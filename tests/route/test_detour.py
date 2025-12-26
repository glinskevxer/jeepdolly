import pytest

from jeepdolly.errors import BadValueError, NotFoundError
from jeepdolly.rig.axle import Axle
from jeepdolly.rig.config import Configuration
from jeepdolly.rig.load import Load
from jeepdolly.route.detour import affected, detour_for, without
from jeepdolly.route.plan import along_segments
from jeepdolly.route.search import passable_for
from jeepdolly.units.length import feet, feet_inches, inches
from jeepdolly.units.mass import pounds


def steer(weight: int = 12000) -> Axle:
    return Axle(weight=pounds(weight), tires=2, tire_width=inches(11), steering=True)


def drive(weight: int = 17000) -> Axle:
    return Axle(weight=pounds(weight), tires=4, tire_width=inches(11))


def a_rig(weight: int = 17000) -> Configuration:
    return Configuration(
        name="3S2",  # type: ignore[arg-type]
        axles=(steer(), drive(weight), drive(weight), drive(weight), drive(weight)),
        spacings=(feet(15), feet(4), feet(30), feet(4)),
    )


def a_light_rig() -> Configuration:
    return Configuration(
        name="LIGHT",  # type: ignore[arg-type]
        axles=(steer(10000), drive(12000), drive(12000)),
        spacings=(feet(15), feet(4)),
    )


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


def test_closing_the_bypass_pushes_a_heavy_rig_off_the_road(corridor):
    made = detour_for(corridor, "JCT-A", "JCT-D", a_rig(), a_load(), ["SEG-BD"])
    assert made.affected
    assert made.stranded


def test_a_stranded_detour_says_so_when_printed(corridor):
    made = detour_for(corridor, "JCT-A", "JCT-D", a_rig(), a_load(), ["SEG-BD"])
    assert "nothing gets through" in str(made)


def test_closing_a_stretch_the_rig_does_not_use_changes_nothing(corridor):
    made = detour_for(corridor, "JCT-A", "JCT-D", a_rig(), a_load(), ["SEG-CD"])
    assert not made.affected
    assert not made.stranded
    assert int(made.extra) == 0


def test_a_stretch_off_the_route_says_so_when_printed(corridor):
    made = detour_for(corridor, "JCT-A", "JCT-D", a_rig(), a_load(), ["SEG-CD"])
    assert "is not on the route" in str(made)


def test_a_light_rig_is_pushed_onto_the_long_way(corridor):
    made = detour_for(corridor, "JCT-A", "JCT-D", a_light_rig(), a_load(), ["SEG-BC"])
    assert made.affected
    assert not made.stranded
    assert int(made.extra) > 0


def test_the_extra_distance_is_the_difference(corridor):
    made = detour_for(corridor, "JCT-A", "JCT-D", a_light_rig(), a_load(), ["SEG-BC"])
    assert made.usual is not None
    assert made.instead is not None
    assert int(made.extra) == int(made.instead.distance) - int(made.usual.distance)


def test_a_detour_that_costs_miles_says_how_many(corridor):
    made = detour_for(corridor, "JCT-A", "JCT-D", a_light_rig(), a_load(), ["SEG-BC"])
    assert "further" in str(made)


def test_closing_the_only_way_out_strands_the_rig(corridor):
    made = detour_for(corridor, "JCT-A", "JCT-D", a_light_rig(), a_load(), ["SEG-AB"])
    assert made.stranded


def test_two_closures_are_both_honoured(corridor):
    made = detour_for(corridor, "JCT-A", "JCT-D", a_light_rig(), a_load(), ["SEG-BC", "SEG-BD"])
    assert made.stranded


def test_a_closure_is_normalised_before_it_is_matched(corridor):
    made = detour_for(corridor, "JCT-A", "JCT-D", a_light_rig(), a_load(), ["seg-bc"])
    assert made.affected


def test_a_closure_naming_no_stretch_is_refused(corridor):
    with pytest.raises(NotFoundError):
        detour_for(corridor, "JCT-A", "JCT-D", a_rig(), a_load(), ["SEG-ZZ"])


def test_the_same_junction_at_both_ends_is_refused(corridor):
    with pytest.raises(BadValueError):
        detour_for(corridor, "JCT-A", "JCT-A", a_rig(), a_load(), ["SEG-AB"])


def test_without_refuses_an_empty_closure_list(corridor):
    base = passable_for(corridor, a_rig(), a_load())
    with pytest.raises(BadValueError):
        without(base, [])


def test_without_still_refuses_what_the_base_refuses(corridor):
    from jeepdolly.route.plan import Leg

    base = passable_for(corridor, a_rig(), a_load())
    usable = without(base, ["SEG-AB"])
    posted = Leg(segment=corridor.segment("SEG-CD"), from_node="JCT-C", to_node="JCT-D")  # type: ignore[arg-type]
    assert not usable(posted)


def test_without_refuses_the_closed_stretch(corridor):
    from jeepdolly.route.plan import Leg

    base = passable_for(corridor, a_light_rig(), a_load())
    usable = without(base, ["SEG-AB"])
    shut = Leg(segment=corridor.segment("SEG-AB"), from_node="JCT-A", to_node="JCT-B")  # type: ignore[arg-type]
    assert not usable(shut)


def test_affected_names_the_stretches_a_route_uses(corridor):
    route = along_segments(corridor, "JCT-A", ["SEG-AB", "SEG-BC"])
    assert affected(route, ["SEG-BC", "SEG-CD"]) == ("SEG-BC",)


def test_affected_is_empty_when_nothing_is_used(corridor):
    route = along_segments(corridor, "JCT-A", ["SEG-AB"])
    assert affected(route, ["SEG-CD"]) == ()
