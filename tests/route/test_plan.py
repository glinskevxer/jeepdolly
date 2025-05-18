import pytest

from jeepdolly.errors import BadValueError, NotFoundError
from jeepdolly.roadway.network import build
from jeepdolly.route.plan import Leg, Route, along_segments, through_nodes
from jeepdolly.units.distance import miles

from .conftest import node, segment


def test_a_leg_runs_the_segments_own_way(corridor):
    leg = Leg(segment=corridor.segment("SEG-AB"), from_node="JCT-A", to_node="JCT-B")  # type: ignore[arg-type]
    assert not leg.reversed


def test_a_leg_may_run_backwards_on_a_two_way(corridor):
    leg = Leg(segment=corridor.segment("SEG-AB"), from_node="JCT-B", to_node="JCT-A")  # type: ignore[arg-type]
    assert leg.reversed


def test_a_leg_refuses_a_direction_the_segment_does_not_run():
    one_way = build(
        nodes=[node("JCT-A"), node("JCT-B")],
        segments=[segment("SEG-AB", "JCT-A", "JCT-B", one_way=True)],
    )
    with pytest.raises(BadValueError):
        Leg(segment=one_way.segment("SEG-AB"), from_node="JCT-B", to_node="JCT-A")  # type: ignore[arg-type]


def test_a_leg_carries_its_distance(corridor):
    leg = Leg(segment=corridor.segment("SEG-AB"), from_node="JCT-A", to_node="JCT-B")  # type: ignore[arg-type]
    assert int(leg.distance) == 1200


def test_a_leg_prints_its_route_and_ends(corridor):
    leg = Leg(segment=corridor.segment("SEG-AB"), from_node="JCT-A", to_node="JCT-B")  # type: ignore[arg-type]
    assert str(leg) == "US-12 JCT-A to JCT-B (12.00 mi)"


def test_along_segments_builds_a_route(corridor):
    made = along_segments(corridor, "JCT-A", ["SEG-AB", "SEG-BC", "SEG-CD"])
    assert len(made) == 3


def test_along_segments_finds_the_ends(corridor):
    made = along_segments(corridor, "JCT-A", ["SEG-AB", "SEG-BC", "SEG-CD"])
    assert made.origin == "JCT-A"
    assert made.destination == "JCT-D"


def test_along_segments_adds_the_distance(corridor):
    made = along_segments(corridor, "JCT-A", ["SEG-AB", "SEG-BC", "SEG-CD"])
    assert int(made.distance) == 1200 + 850 + 600


def test_along_segments_lists_the_junctions(corridor):
    made = along_segments(corridor, "JCT-A", ["SEG-AB", "SEG-BC"])
    assert made.nodes == ("JCT-A", "JCT-B", "JCT-C")


def test_along_segments_refuses_an_empty_list(corridor):
    with pytest.raises(BadValueError):
        along_segments(corridor, "JCT-A", [])


def test_along_segments_refuses_a_segment_that_does_not_touch(corridor):
    with pytest.raises(BadValueError):
        along_segments(corridor, "JCT-A", ["SEG-BC"])


def test_along_segments_refuses_a_segment_that_is_not_there(corridor):
    with pytest.raises(NotFoundError):
        along_segments(corridor, "JCT-A", ["SEG-ZZ"])


def test_along_segments_refuses_a_start_that_is_not_there(corridor):
    with pytest.raises(NotFoundError):
        along_segments(corridor, "JCT-Z", ["SEG-AB"])


def test_along_segments_can_double_back(corridor):
    made = along_segments(corridor, "JCT-A", ["SEG-AB", "SEG-AB"])
    assert made.destination == "JCT-A"
    assert made.revisits


def test_a_plain_route_does_not_revisit(corridor):
    made = along_segments(corridor, "JCT-A", ["SEG-AB", "SEG-BC"])
    assert not made.revisits


def test_through_nodes_builds_a_route(corridor):
    made = through_nodes(corridor, ["JCT-A", "JCT-B", "JCT-C"])
    assert [s.code for s in made.segments] == ["SEG-AB", "SEG-BC"]


def test_through_nodes_takes_the_shorter_of_two_links():
    twin = build(
        nodes=[node("JCT-A"), node("JCT-B")],
        segments=[
            segment("SEG-LONG", "JCT-A", "JCT-B", distance=miles("30.00")),
            segment("SEG-SHORT", "JCT-A", "JCT-B", distance=miles("4.00")),
        ],
    )
    made = through_nodes(twin, ["JCT-A", "JCT-B"])
    assert made.segments[0].code == "SEG-SHORT"


def test_through_nodes_refuses_one_junction(corridor):
    with pytest.raises(BadValueError):
        through_nodes(corridor, ["JCT-A"])


def test_through_nodes_refuses_junctions_that_do_not_connect(corridor):
    with pytest.raises(BadValueError):
        through_nodes(corridor, ["JCT-A", "JCT-D"])


def test_through_nodes_can_go_backwards(corridor):
    made = through_nodes(corridor, ["JCT-C", "JCT-B", "JCT-A"])
    assert made.destination == "JCT-A"
    assert made.legs[0].reversed


def test_a_route_refuses_legs_that_do_not_join_up(corridor):
    first = Leg(segment=corridor.segment("SEG-AB"), from_node="JCT-A", to_node="JCT-B")  # type: ignore[arg-type]
    apart = Leg(segment=corridor.segment("SEG-CD"), from_node="JCT-C", to_node="JCT-D")  # type: ignore[arg-type]
    with pytest.raises(BadValueError):
        Route(legs=(first, apart))


def test_a_route_refuses_no_legs():
    with pytest.raises(BadValueError):
        Route(legs=())


def test_a_route_prints_a_summary(corridor):
    made = along_segments(corridor, "JCT-A", ["SEG-AB", "SEG-BC"])
    assert str(made) == "JCT-A to JCT-C, 2 legs, 20.50 mi"


def test_the_bypass_is_longer_than_the_short_way(corridor):
    short = through_nodes(corridor, ["JCT-B", "JCT-C", "JCT-D"])
    bypass = through_nodes(corridor, ["JCT-B", "JCT-D"])
    assert int(bypass.distance) > int(short.distance)
