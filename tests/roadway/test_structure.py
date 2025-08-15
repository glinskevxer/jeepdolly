import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.limits.finding import Severity
from jeepdolly.roadway.structure import CARRYING_KINDS, OVERHEAD_KINDS, Structure, StructureKind
from jeepdolly.units.distance import miles
from jeepdolly.units.length import feet, feet_inches, inches
from jeepdolly.units.mass import pounds


def a_bridge(**over: object) -> Structure:
    """A posted bridge, with any part of it swapped out."""
    kw: dict[str, object] = {
        "reference": "STR-00001",
        "segment": "SEG-01",
        "name": "Sixmile Creek",
        "kind": StructureKind.BRIDGE,
        "milepost": miles("4.20"),
        "rating": pounds(64000),
    }
    kw.update(over)
    return Structure(**kw)  # type: ignore[arg-type]


def an_overhead(**over: object) -> Structure:
    """A railroad overhead, with any part of it swapped out."""
    kw: dict[str, object] = {
        "reference": "STR-00002",
        "segment": "SEG-01",
        "name": "MRL overhead",
        "kind": StructureKind.OVERHEAD,
        "milepost": miles("6.05"),
        "clearance": feet_inches(15, 2),
    }
    kw.update(over)
    return Structure(**kw)  # type: ignore[arg-type]


def test_bridge_normalises_its_references():
    made = a_bridge(reference="str-00001", segment="seg-01")
    assert (made.reference, made.segment) == ("STR-00001", "SEG-01")


def test_bridge_collapses_whitespace_in_the_name():
    assert a_bridge(name="Sixmile   Creek").name == "Sixmile Creek"


def test_bridge_refuses_an_empty_name():
    with pytest.raises(BadValueError):
        a_bridge(name=" ")


def test_a_bridge_limits_weight_and_not_height():
    made = a_bridge()
    assert made.limits_weight
    assert not made.limits_height


def test_an_overhead_limits_height_and_not_weight():
    made = an_overhead()
    assert made.limits_height
    assert not made.limits_weight


def test_a_bridge_refuses_a_clearance():
    with pytest.raises(BadValueError):
        a_bridge(clearance=feet(15))


def test_an_overhead_refuses_a_rating():
    with pytest.raises(BadValueError):
        an_overhead(rating=pounds(64000))


def test_an_overhead_needs_a_clearance():
    with pytest.raises(BadValueError):
        an_overhead(clearance=None)


def test_a_tunnel_is_an_overhead():
    made = an_overhead(kind=StructureKind.TUNNEL)
    assert made.kind in OVERHEAD_KINDS
    assert made.limits_height


def test_a_culvert_carries_the_rig_over():
    assert StructureKind.CULVERT in CARRYING_KINDS


def test_a_bridge_with_no_rating_is_unposted():
    assert a_bridge(rating=None).unposted


def test_a_rated_bridge_is_not_unposted():
    assert not a_bridge().unposted


def test_an_overhead_is_never_unposted():
    assert not an_overhead().unposted


def test_bridge_refuses_a_rating_of_nothing():
    with pytest.raises(BadValueError):
        a_bridge(rating=pounds(0))


def test_overhead_refuses_a_clearance_of_nothing():
    with pytest.raises(BadValueError):
        an_overhead(clearance=inches(0))


def test_a_load_under_the_clearance_gets_through():
    assert an_overhead().clears_height(feet(15))


def test_a_load_exactly_at_the_clearance_gets_through():
    assert an_overhead().clears_height(feet_inches(15, 2))


def test_a_load_one_inch_over_does_not():
    assert not an_overhead().clears_height(feet_inches(15, 3))


def test_an_unposted_bridge_clears_any_height():
    assert a_bridge().clears_height(feet(20))


def test_a_rig_under_the_rating_is_carried():
    assert a_bridge().carries(pounds(60000))


def test_a_rig_exactly_at_the_rating_is_carried():
    assert a_bridge().carries(pounds(64000))


def test_a_rig_one_pound_over_is_not():
    assert not a_bridge().carries(pounds(64001))


def test_an_unrated_bridge_carries_anything():
    assert a_bridge(rating=None).carries(pounds(400000))


def test_check_is_quiet_when_the_load_fits():
    assert a_bridge().check(feet(14), pounds(60000)) == []


def test_check_reports_a_posted_bridge():
    found = a_bridge().check(feet(14), pounds(90000))
    assert [f.rule for f in found] == ["posted-bridge"]
    assert found[0].severity is Severity.REFUSE


def test_check_reports_a_clearance():
    found = an_overhead().check(feet(16), pounds(60000))
    assert [f.rule for f in found] == ["clearance"]
    assert found[0].severity is Severity.REFUSE


def test_a_clearance_finding_names_both_heights():
    found = an_overhead().check(feet(16), pounds(60000))
    assert "15'2\"" in found[0].detail
    assert "16'" in found[0].detail


def test_a_posted_bridge_finding_names_both_weights():
    found = a_bridge().check(feet(14), pounds(90000))
    assert "64,000 lb" in found[0].detail
    assert "90,000 lb" in found[0].detail


def test_a_structure_finding_carries_no_excess():
    found = a_bridge().check(feet(14), pounds(90000))
    assert int(found[0].excess) == 0


def test_a_bridge_prints_its_rating():
    assert str(a_bridge()).endswith("rated 64,000 lb")


def test_an_overhead_prints_its_clearance():
    assert str(an_overhead()).endswith("clearance 15'2\"")


def test_an_unposted_bridge_says_so():
    assert str(a_bridge(rating=None)).endswith("unposted")


def test_structures_order_by_reference():
    assert sorted([an_overhead(), a_bridge()])[0].reference == "STR-00001"
