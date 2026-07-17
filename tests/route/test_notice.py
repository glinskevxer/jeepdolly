import datetime as dt

import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.roadway.network import build
from jeepdolly.roadway.node import Node
from jeepdolly.roadway.segment import Segment
from jeepdolly.roadway.structure import Structure, StructureKind
from jeepdolly.route.notice import MARGIN, Notice, notices_for, wants_notice_of
from jeepdolly.route.plan import Route, along_segments
from jeepdolly.units.distance import miles
from jeepdolly.units.length import feet_inches, inches

FIRST = dt.date(2025, 6, 18)
TALL = feet_inches(15, 0)


def a_structure(**over: object) -> Structure:
    """An overhead with an owner and a lead time, overridable field by field."""
    kw: dict[str, object] = {
        "reference": "ST-00001",
        "segment": "SEG-AB",
        "name": "Reserve Street crossing",
        "kind": StructureKind.OVERHEAD,
        "milepost": miles("8.00"),
        "clearance": feet_inches(15, 4),
        "owner": "Missoula Electric",
        "notice_days": 3,
    }
    kw.update(over)
    return Structure(**kw)  # type: ignore[arg-type]


def a_route() -> Route:
    """A two leg route from JCT-A to JCT-C."""
    nodes = [
        Node(code=key, name=key.lower(), county="Missoula")  # type: ignore[arg-type]
        for key in ("JCT-A", "JCT-B", "JCT-C")
    ]
    segments = [
        Segment(
            code="SEG-AB",  # type: ignore[arg-type]
            start="JCT-A",  # type: ignore[arg-type]
            end="JCT-B",  # type: ignore[arg-type]
            route="US-12",
            distance=miles("12.00"),
        ),
        Segment(
            code="SEG-BC",  # type: ignore[arg-type]
            start="JCT-B",  # type: ignore[arg-type]
            end="JCT-C",  # type: ignore[arg-type]
            route="SR-200",
            distance=miles("9.00"),
        ),
    ]
    network = build(nodes, segments)
    return along_segments(network, "JCT-A", ["SEG-AB", "SEG-BC"])


def a_notice(**over: object) -> Notice:
    kw: dict[str, object] = {
        "tell_by": FIRST - dt.timedelta(days=3),
        "owner": "Missoula Electric",
        "lead_days": 3,
        "places": ("Reserve Street crossing on US-12",),
    }
    kw.update(over)
    return Notice(**kw)  # type: ignore[arg-type]


def test_a_load_at_the_margin_wants_a_notice():
    wanted = a_structure()
    assert wants_notice_of(wanted, inches(int(wanted.clearance or 0) - int(MARGIN)))


def test_a_load_well_under_the_wire_wants_nothing():
    assert not wants_notice_of(a_structure(), feet_inches(10, 0))


def test_a_load_that_will_not_fit_still_wants_a_notice():
    assert wants_notice_of(a_structure(), feet_inches(20, 0))


def test_a_structure_with_nobody_on_file_wants_nothing():
    assert not wants_notice_of(a_structure(owner="", notice_days=0), TALL)


def test_a_structure_with_no_lead_time_wants_nothing():
    assert not wants_notice_of(a_structure(notice_days=0), TALL)


def test_a_bridge_wants_no_height_notice():
    bridge = a_structure(
        kind=StructureKind.BRIDGE, clearance=None, rating=None, owner="County", notice_days=2
    )
    assert not wants_notice_of(bridge, TALL)


def test_a_wider_margin_pulls_in_a_shorter_load():
    assert not wants_notice_of(a_structure(), feet_inches(14, 0))
    assert wants_notice_of(a_structure(), feet_inches(14, 0), margin=feet_inches(2, 0))


def test_something_that_is_not_a_structure_is_refused():
    with pytest.raises(BadValueError):
        wants_notice_of("crossing", TALL)  # type: ignore[arg-type]


def test_a_route_with_nothing_overhead_needs_no_calls():
    assert notices_for(a_route(), {}, TALL, FIRST) == []


def test_a_crossing_on_the_route_makes_one_call():
    found = notices_for(a_route(), {"SEG-AB": [a_structure()]}, TALL, FIRST)
    assert [one.owner for one in found] == ["Missoula Electric"]


def test_a_crossing_off_the_route_makes_no_call():
    found = notices_for(a_route(), {"SEG-XY": [a_structure()]}, TALL, FIRST)
    assert found == []


def test_the_deadline_is_the_lead_time_before_the_first_day():
    found = notices_for(a_route(), {"SEG-AB": [a_structure()]}, TALL, FIRST)
    assert found[0].tell_by == FIRST - dt.timedelta(days=3)


def test_one_owner_on_two_segments_is_one_call():
    other = a_structure(reference="ST-00002", segment="SEG-BC", name="Rattlesnake crossing")
    found = notices_for(a_route(), {"SEG-AB": [a_structure()], "SEG-BC": [other]}, TALL, FIRST)
    assert len(found) == 1
    assert len(found[0].places) == 2


def test_the_merged_call_takes_the_longest_lead_time():
    slow = a_structure(
        reference="ST-00002", segment="SEG-BC", name="Rattlesnake", notice_days=10
    )
    found = notices_for(a_route(), {"SEG-AB": [a_structure()], "SEG-BC": [slow]}, TALL, FIRST)
    assert found[0].lead_days == 10
    assert found[0].tell_by == FIRST - dt.timedelta(days=10)


def test_two_owners_make_two_calls():
    railway = a_structure(reference="ST-00002", segment="SEG-BC", owner="MRL", notice_days=10)
    found = notices_for(
        a_route(), {"SEG-AB": [a_structure()], "SEG-BC": [railway]}, TALL, FIRST
    )
    assert {one.owner for one in found} == {"Missoula Electric", "MRL"}


def test_the_call_list_is_earliest_deadline_first():
    railway = a_structure(reference="ST-00002", segment="SEG-BC", owner="MRL", notice_days=10)
    found = notices_for(
        a_route(), {"SEG-AB": [a_structure()], "SEG-BC": [railway]}, TALL, FIRST
    )
    assert [one.owner for one in found] == ["MRL", "Missoula Electric"]


def test_the_places_are_listed_in_the_order_they_are_met():
    second = a_structure(reference="ST-00002", segment="SEG-BC", name="Rattlesnake crossing")
    found = notices_for(a_route(), {"SEG-AB": [a_structure()], "SEG-BC": [second]}, TALL, FIRST)
    assert found[0].places[0].startswith("Reserve Street")


def test_something_that_is_not_a_route_is_refused():
    with pytest.raises(BadValueError):
        notices_for("JCT-A to JCT-C", {}, TALL, FIRST)  # type: ignore[arg-type]


def test_a_datetime_first_day_is_refused():
    when = dt.datetime(2025, 6, 18, tzinfo=dt.UTC)
    with pytest.raises(BadValueError):
        notices_for(a_route(), {}, TALL, when)


def test_a_notice_with_no_places_is_refused():
    with pytest.raises(BadValueError):
        a_notice(places=())


def test_a_notice_with_no_lead_time_is_refused():
    with pytest.raises(BadValueError):
        a_notice(lead_days=0)


def test_a_notice_with_no_owner_is_refused():
    with pytest.raises(BadValueError):
        a_notice(owner="  ")


def test_a_notice_given_after_the_deadline_is_late():
    assert a_notice().late_on(FIRST)


def test_a_notice_given_on_the_deadline_is_not_late():
    assert not a_notice().late_on(FIRST - dt.timedelta(days=3))


def test_asking_lateness_with_a_datetime_is_refused():
    with pytest.raises(BadValueError):
        a_notice().late_on(dt.datetime(2025, 6, 18, tzinfo=dt.UTC))


def test_a_notice_prints_who_to_ring_and_by_when():
    line = str(a_notice())
    assert "Missoula Electric" in line
    assert "Reserve Street" in line


def test_a_structure_with_a_lead_time_and_nobody_is_refused():
    with pytest.raises(BadValueError):
        a_structure(owner="")


def test_a_structure_owner_loses_its_extra_spaces():
    assert a_structure(owner="  Missoula   Electric ").owner == "Missoula Electric"


def test_a_negative_notice_period_is_refused():
    with pytest.raises(BadValueError):
        a_structure(notice_days=-1)
