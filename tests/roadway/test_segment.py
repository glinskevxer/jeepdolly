import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.limits.statute import INTERSTATE, STATE_ROUTE
from jeepdolly.roadway.segment import RoadClass, Segment, statute_for
from jeepdolly.units.distance import miles
from jeepdolly.units.length import feet, feet_inches, inches
from jeepdolly.units.mass import pounds


def a_segment(**over: object) -> Segment:
    """A stretch of US 12, with any part of it swapped out."""
    kw: dict[str, object] = {
        "code": "SEG-01",
        "start": "JCT-12",
        "end": "JCT-13",
        "route": "US-12",
        "distance": miles("14.20"),
    }
    kw.update(over)
    return Segment(**kw)  # type: ignore[arg-type]


def test_segment_normalises_the_codes():
    made = a_segment(code="seg-01", start="jct-12", end="jct-13")
    assert (made.code, made.start, made.end) == ("SEG-01", "JCT-12", "JCT-13")


def test_segment_upper_cases_the_route():
    assert a_segment(route="us-12").route == "US-12"


@pytest.mark.parametrize("route", ["I-90", "US-12", "SR-200", "CR-14A", "FR-7"])
def test_the_route_forms_the_office_accepts(route):
    assert a_segment(route=route).route == route


def test_segment_refuses_a_route_that_is_not_a_designation():
    with pytest.raises(BadValueError):
        a_segment(route="Sixmile Road")


def test_segment_refuses_a_route_that_is_not_text():
    with pytest.raises(BadValueError):
        a_segment(route=12)


def test_segment_refuses_a_loop():
    with pytest.raises(BadValueError):
        a_segment(end="JCT-12")


def test_segment_refuses_no_distance():
    with pytest.raises(BadValueError):
        a_segment(distance=miles(0))


def test_segment_defaults_to_a_state_route():
    assert a_segment().road_class is RoadClass.STATE


def test_segment_takes_the_road_class_as_text():
    assert a_segment(road_class="interstate").road_class is RoadClass.INTERSTATE


def test_segment_refuses_an_unknown_road_class():
    with pytest.raises(ValueError, match="not a valid|interstate|state|local"):
        a_segment(road_class="gravel")


def test_segment_defaults_to_two_way():
    assert not a_segment().one_way


def test_segment_refuses_a_non_bool_one_way():
    with pytest.raises(BadValueError):
        a_segment(one_way="yes")


def test_statute_for_an_interstate_is_the_federal_set():
    assert statute_for(RoadClass.INTERSTATE) is INTERSTATE


def test_statute_for_a_local_road_is_the_state_set():
    assert statute_for(RoadClass.LOCAL) is STATE_ROUTE


def test_a_segment_carries_its_statute():
    assert a_segment(road_class="interstate").statute is INTERSTATE


def test_gross_limit_falls_back_to_the_statute():
    assert a_segment().gross_limit == STATE_ROUTE.gross


def test_a_posted_segment_uses_the_lower_number():
    made = a_segment(posted_gross=pounds(48000))
    assert int(made.gross_limit) == 48000
    assert made.posted


def test_a_posted_limit_above_the_statute_does_not_raise_it():
    made = a_segment(posted_gross=pounds(200000))
    assert made.gross_limit == STATE_ROUTE.gross
    assert not made.posted


def test_segment_refuses_a_posted_limit_of_nothing():
    with pytest.raises(BadValueError):
        a_segment(posted_gross=pounds(0))


def test_a_two_way_segment_runs_both_directions():
    made = a_segment()
    assert made.runs("JCT-12", "JCT-13")  # type: ignore[arg-type]
    assert made.runs("JCT-13", "JCT-12")  # type: ignore[arg-type]


def test_a_one_way_segment_runs_one_direction():
    made = a_segment(one_way=True)
    assert made.runs("JCT-12", "JCT-13")  # type: ignore[arg-type]
    assert not made.runs("JCT-13", "JCT-12")  # type: ignore[arg-type]


def test_a_segment_does_not_run_between_nodes_it_does_not_touch():
    assert not a_segment().runs("JCT-12", "JCT-99")  # type: ignore[arg-type]


def test_other_end_from_the_start():
    assert a_segment().other_end("JCT-12") == "JCT-13"  # type: ignore[arg-type]


def test_other_end_from_the_end():
    assert a_segment().other_end("JCT-13") == "JCT-12"  # type: ignore[arg-type]


def test_other_end_refuses_a_node_it_does_not_touch():
    with pytest.raises(BadValueError):
        a_segment().other_end("JCT-99")  # type: ignore[arg-type]


def test_a_two_way_segment_prints_a_double_arrow():
    assert str(a_segment()) == "SEG-01 US-12 JCT-12 <-> JCT-13"


def test_a_one_way_segment_prints_a_single_arrow():
    assert "->" in str(a_segment(one_way=True))
    assert "<->" not in str(a_segment(one_way=True))


def test_segments_order_by_code():
    first = a_segment(code="AAA")
    assert sorted([a_segment(), first])[0] is first


def test_a_plain_segment_posts_no_size():
    made = a_segment()
    assert not made.restricted
    assert made.max_width is None
    assert made.max_height is None


def test_a_segment_may_post_a_width():
    made = a_segment(max_width=feet(12))
    assert made.restricted
    assert int(made.max_width or 0) == 144


def test_a_segment_may_post_a_height():
    made = a_segment(max_height=feet(14))
    assert made.restricted
    assert int(made.max_height or 0) == 168


def test_a_posted_width_of_nothing_is_refused():
    with pytest.raises(BadValueError):
        a_segment(max_width=inches(0))


def test_a_posted_height_of_nothing_is_refused():
    with pytest.raises(BadValueError):
        a_segment(max_height=inches(0))


def test_an_unrestricted_stretch_takes_any_width():
    assert a_segment().takes_width(feet(20))


def test_a_restricted_stretch_takes_a_load_at_its_limit():
    assert a_segment(max_width=feet(12)).takes_width(feet(12))


def test_a_restricted_stretch_refuses_one_inch_more():
    assert not a_segment(max_width=feet(12)).takes_width(feet_inches(12, 1))


def test_a_height_restriction_reads_the_same_way():
    made = a_segment(max_height=feet(14))
    assert made.takes_height(feet(14))
    assert not made.takes_height(feet_inches(14, 1))
