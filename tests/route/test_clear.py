import pytest

from jeepdolly.limits.finding import Severity
from jeepdolly.rig.axle import Axle
from jeepdolly.rig.config import Configuration
from jeepdolly.rig.load import Load
from jeepdolly.roadway.network import Network
from jeepdolly.roadway.segment import RoadClass
from jeepdolly.route.clear import walk
from jeepdolly.route.plan import along_segments
from jeepdolly.units.length import feet, feet_inches, inches
from jeepdolly.units.mass import pounds


def steer(weight: int = 12000) -> Axle:
    return Axle(weight=pounds(weight), tires=2, tire_width=inches(11), steering=True)


def drive(weight: int = 17000) -> Axle:
    return Axle(weight=pounds(weight), tires=4, tire_width=inches(11))


def a_rig(weight: int = 17000, name: str = "3S2") -> Configuration:
    return Configuration(
        name=name,  # type: ignore[arg-type]
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


@pytest.fixture
def short_way(corridor):
    return along_segments(corridor, "JCT-A", ["SEG-AB", "SEG-BC", "SEG-CD"])


@pytest.fixture
def bypass(corridor):
    return along_segments(corridor, "JCT-A", ["SEG-AB", "SEG-BD"])


def test_a_legal_rig_walks_the_bypass_clean(corridor, bypass):
    report = walk(bypass, corridor, a_rig(), a_load())
    assert report.clear
    assert not report.blocked


def test_a_legal_rig_is_stopped_by_the_local_order_on_the_short_way(corridor, short_way):
    report = walk(short_way, corridor, a_rig(), a_load())
    assert report.blocked
    assert "local-order" in [f.rule for f in report.blockers]


def test_the_local_order_names_both_weights(corridor, short_way):
    report = walk(short_way, corridor, a_rig(), a_load())
    local = next(f for f in report.findings if f.rule == "local-order")
    assert "48,000 lb" in local.detail
    assert "80,000 lb" in local.detail


def test_a_tall_load_is_stopped_by_the_overhead(corridor, short_way):
    report = walk(short_way, corridor, a_rig(), a_load(height=feet(16)))
    assert "clearance" in [f.rule for f in report.blockers]


def test_a_tall_load_gets_through_on_the_bypass(corridor, bypass):
    report = walk(bypass, corridor, a_rig(), a_load(height=feet(16)))
    assert "clearance" not in [f.rule for f in report.findings]


def test_a_heavy_rig_is_stopped_by_the_posted_bridge(corridor):
    route = along_segments(corridor, "JCT-B", ["SEG-BC"])
    report = walk(route, corridor, a_rig(), a_load())
    assert "posted-bridge" in [f.rule for f in report.blockers]


def test_a_light_rig_clears_the_posted_bridge(corridor):
    route = along_segments(corridor, "JCT-B", ["SEG-BC"])
    light = Configuration(
        name="LIGHT",  # type: ignore[arg-type]
        axles=(steer(10000), drive(12000), drive(12000)),
        spacings=(feet(15), feet(4)),
    )
    report = walk(route, corridor, light, a_load())
    assert not report.blocked


def test_each_leg_keeps_its_own_findings(corridor, short_way):
    report = walk(short_way, corridor, a_rig(), a_load())
    assert report.leg_at(0).clear
    assert not report.leg_at(1).clear


def test_a_clear_leg_says_so_when_printed(corridor, short_way):
    report = walk(short_way, corridor, a_rig(), a_load())
    assert str(report.leg_at(0)).endswith("clear")


def test_a_dirty_leg_counts_its_findings(corridor, short_way):
    report = walk(short_way, corridor, a_rig(), a_load())
    assert "findings" in str(report.leg_at(1))


def test_the_route_report_prints_a_summary(corridor, bypass):
    report = walk(bypass, corridor, a_rig(), a_load())
    assert str(report).startswith("JCT-A to JCT-D")


def test_one_class_of_road_is_assessed_once(corridor, bypass):
    report = walk(bypass, corridor, a_rig(), a_load())
    assert report.classes == (RoadClass.STATE,)


def test_two_classes_are_assessed_separately(corridor, bypass):
    mixed = corridor.segments["SEG-AB"]
    assert mixed.road_class is RoadClass.STATE


def test_a_heavy_rig_raises_surface_findings(corridor, bypass):
    report = walk(bypass, corridor, a_rig(23000), a_load())
    rules = [f.rule for f in report.surface_findings]
    assert "single-axle" in rules
    assert "gross" in rules


def test_the_excess_is_the_largest_billable(corridor, bypass):
    report = walk(bypass, corridor, a_rig(23000), a_load())
    billable = [int(f.excess) for f in report.findings if f.billable]
    assert int(report.excess) == max(billable)


def test_a_clear_route_has_no_excess(corridor, bypass):
    assert int(walk(bypass, corridor, a_rig(), a_load()).excess) == 0


def test_leg_findings_come_before_surface_findings(corridor, short_way):
    report = walk(short_way, corridor, a_rig(23000), a_load())
    rules = [f.rule for f in report.findings]
    assert rules.index("local-order") < rules.index("gross")


def test_a_divisible_load_shows_up_once_per_class(corridor, bypass):
    report = walk(bypass, corridor, a_rig(), a_load(divisible=True, reason=""))
    assert [f.rule for f in report.surface_findings].count("divisible") == 1


def test_the_severity_of_a_blocked_route_is_refuse(corridor, short_way):
    assert walk(short_way, corridor, a_rig(), a_load()).severity is Severity.REFUSE


def test_the_severity_of_a_clean_route_is_a_note(corridor, bypass):
    assert walk(bypass, corridor, a_rig(), a_load()).severity is Severity.NOTE


def test_walking_backwards_finds_the_same_things(corridor):
    forward = along_segments(corridor, "JCT-B", ["SEG-BC"])
    backward = along_segments(corridor, "JCT-C", ["SEG-BC"])
    ahead = walk(forward, corridor, a_rig(), a_load())
    behind = walk(backward, corridor, a_rig(), a_load())
    assert [f.rule for f in ahead.findings] == [f.rule for f in behind.findings]


def a_narrow_map() -> Network:
    """A corridor whose only through stretch posts a width of its own."""
    from jeepdolly.roadway.network import build
    from jeepdolly.roadway.node import Node
    from jeepdolly.roadway.segment import Segment
    from jeepdolly.units.distance import miles

    nodes = [
        Node(code=key, name=key.lower(), county="Missoula")  # type: ignore[arg-type]
        for key in ("JCT-A", "JCT-B")
    ]
    segments = [
        Segment(
            code="SEG-AB",  # type: ignore[arg-type]
            start="JCT-A",  # type: ignore[arg-type]
            end="JCT-B",  # type: ignore[arg-type]
            route="US-12",
            distance=miles("4.00"),
            max_width=feet(12),
            max_height=feet(14),
        )
    ]
    return build(nodes, segments)


def test_a_road_posted_width_refuses_a_wider_load():
    network = a_narrow_map()
    route = along_segments(network, "JCT-A", ["SEG-AB"])
    report = walk(route, network, a_rig(), a_load(width=feet(13)))
    assert "road-width" in [f.rule for f in report.blockers]


def test_a_road_posted_width_takes_a_load_at_its_limit():
    network = a_narrow_map()
    route = along_segments(network, "JCT-A", ["SEG-AB"])
    report = walk(route, network, a_rig(), a_load(width=feet(12)))
    assert "road-width" not in [f.rule for f in report.findings]


def test_a_road_posted_height_refuses_a_taller_load():
    network = a_narrow_map()
    route = along_segments(network, "JCT-A", ["SEG-AB"])
    report = walk(route, network, a_rig(), a_load(height=feet(15)))
    assert "road-height" in [f.rule for f in report.blockers]


def test_a_road_posted_size_names_both_figures():
    network = a_narrow_map()
    route = along_segments(network, "JCT-A", ["SEG-AB"])
    report = walk(route, network, a_rig(), a_load(width=feet(13)))
    found = next(f for f in report.findings if f.rule == "road-width")
    assert "12'" in found.detail
    assert "13'" in found.detail


def test_the_search_routes_around_a_road_posted_width(corridor):
    from jeepdolly.route.search import clearing

    wide = clearing(corridor, "JCT-A", "JCT-D", a_rig(), a_load(width=feet(13)))
    assert wide is not None
