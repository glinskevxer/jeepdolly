import pytest

from jeepdolly.errors import BadValueError, NotFoundError
from jeepdolly.rig.axle import Axle
from jeepdolly.rig.config import Configuration
from jeepdolly.rig.load import Load
from jeepdolly.roadway.network import build
from jeepdolly.route.search import (
    cheapest_distance,
    clearing,
    every_route,
    passable_for,
    shortest,
)
from jeepdolly.units.length import feet, feet_inches, inches
from jeepdolly.units.mass import pounds

from .conftest import node, segment


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


def test_shortest_takes_the_short_way(corridor):
    found = shortest(corridor, "JCT-A", "JCT-D")
    assert found is not None
    assert [s.code for s in found.segments] == ["SEG-AB", "SEG-BC", "SEG-CD"]


def test_shortest_reports_the_distance(corridor):
    found = shortest(corridor, "JCT-A", "JCT-D")
    assert found is not None
    assert int(found.distance) == 1200 + 850 + 600


def test_cheapest_distance_agrees_with_shortest(corridor):
    found = shortest(corridor, "JCT-A", "JCT-D")
    assert found is not None
    assert cheapest_distance(corridor, "JCT-A", "JCT-D") == found.distance


def test_shortest_between_neighbours_is_one_leg(corridor):
    found = shortest(corridor, "JCT-A", "JCT-B")
    assert found is not None
    assert len(found) == 1


def test_shortest_refuses_the_same_junction_twice(corridor):
    with pytest.raises(BadValueError):
        shortest(corridor, "JCT-A", "JCT-A")


def test_shortest_raises_on_a_junction_that_is_not_there(corridor):
    with pytest.raises(NotFoundError):
        shortest(corridor, "JCT-A", "JCT-Z")


def test_shortest_returns_nothing_when_there_is_no_way():
    apart = build(
        nodes=[node("JCT-A"), node("JCT-B"), node("JCT-X"), node("JCT-Y")],
        segments=[
            segment("SEG-AB", "JCT-A", "JCT-B"),
            segment("SEG-XY", "JCT-X", "JCT-Y"),
        ],
    )
    assert shortest(apart, "JCT-A", "JCT-Y") is None


def test_shortest_will_not_go_the_wrong_way_up_a_one_way():
    one_way = build(
        nodes=[node("JCT-A"), node("JCT-B")],
        segments=[segment("SEG-AB", "JCT-A", "JCT-B", one_way=True)],
    )
    assert shortest(one_way, "JCT-A", "JCT-B") is not None
    assert shortest(one_way, "JCT-B", "JCT-A") is None


def test_clearing_takes_the_bypass_around_the_local_order(corridor):
    found = clearing(corridor, "JCT-A", "JCT-D", a_rig(), a_load())
    assert found is not None
    assert [s.code for s in found.segments] == ["SEG-AB", "SEG-BD"]


def test_clearing_is_longer_than_shortest_here(corridor):
    short = shortest(corridor, "JCT-A", "JCT-D")
    clean = clearing(corridor, "JCT-A", "JCT-D", a_rig(), a_load())
    assert short is not None
    assert clean is not None
    assert int(clean.distance) > int(short.distance)


def test_a_light_rig_gets_the_short_way(corridor):
    light = Configuration(
        name="LIGHT",  # type: ignore[arg-type]
        axles=(steer(10000), drive(12000), drive(12000)),
        spacings=(feet(15), feet(4)),
    )
    found = clearing(corridor, "JCT-A", "JCT-D", light, a_load())
    assert found is not None
    assert [s.code for s in found.segments] == ["SEG-AB", "SEG-BC", "SEG-CD"]


def test_a_tall_load_still_takes_the_bypass(corridor):
    found = clearing(corridor, "JCT-A", "JCT-D", a_rig(), a_load(height=feet(16)))
    assert found is not None
    assert "SEG-BC" not in [s.code for s in found.segments]


def test_clearing_returns_nothing_when_every_way_is_blocked():
    blocked = build(
        nodes=[node("JCT-A"), node("JCT-B")],
        segments=[segment("SEG-AB", "JCT-A", "JCT-B", posted_gross=pounds(20000))],
    )
    assert clearing(blocked, "JCT-A", "JCT-B", a_rig(), a_load()) is None


def test_passable_for_says_no_to_a_posted_leg(corridor):
    from jeepdolly.route.plan import Leg

    usable = passable_for(corridor, a_rig(), a_load())
    leg = Leg(segment=corridor.segment("SEG-CD"), from_node="JCT-C", to_node="JCT-D")  # type: ignore[arg-type]
    assert not usable(leg)


def test_passable_for_says_yes_to_a_clear_leg(corridor):
    from jeepdolly.route.plan import Leg

    usable = passable_for(corridor, a_rig(), a_load())
    leg = Leg(segment=corridor.segment("SEG-AB"), from_node="JCT-A", to_node="JCT-B")  # type: ignore[arg-type]
    assert usable(leg)


def test_every_route_finds_both_ways(corridor):
    found = list(every_route(corridor, "JCT-A", "JCT-D"))
    assert len(found) == 2


def test_every_route_is_shortest_first(corridor):
    found = list(every_route(corridor, "JCT-A", "JCT-D"))
    assert int(found[0].distance) < int(found[1].distance)


def test_every_route_never_revisits(corridor):
    assert all(not r.revisits for r in every_route(corridor, "JCT-A", "JCT-D"))


def test_every_route_obeys_the_leg_cap(corridor):
    assert list(every_route(corridor, "JCT-A", "JCT-D", max_legs=2)) == [] or all(
        len(r) <= 2 for r in every_route(corridor, "JCT-A", "JCT-D", max_legs=2)
    )


def test_every_route_refuses_a_cap_of_zero(corridor):
    with pytest.raises(BadValueError):
        list(every_route(corridor, "JCT-A", "JCT-D", max_legs=0))


def test_every_route_refuses_a_bool_cap(corridor):
    with pytest.raises(BadValueError):
        list(every_route(corridor, "JCT-A", "JCT-D", max_legs=True))


def test_the_search_is_reproducible(corridor):
    first = shortest(corridor, "JCT-A", "JCT-D")
    for _ in range(5):
        again = shortest(corridor, "JCT-A", "JCT-D")
        assert first is not None
        assert again is not None
        assert [s.code for s in again.segments] == [s.code for s in first.segments]


def test_a_tie_breaks_on_the_segment_code():
    twin = build(
        nodes=[node("JCT-A"), node("JCT-B")],
        segments=[
            segment("SEG-ZZ", "JCT-A", "JCT-B"),
            segment("SEG-AA", "JCT-A", "JCT-B"),
        ],
    )
    found = shortest(twin, "JCT-A", "JCT-B")
    assert found is not None
    assert found.segments[0].code == "SEG-AA"
