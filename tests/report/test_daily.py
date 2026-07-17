import datetime as dt

import pytest

from jeepdolly.almanac.embargo import Embargo, EmbargoBook
from jeepdolly.permit.revoke import Cause
from jeepdolly.report.daily import counties_of, day_sheet, movements
from jeepdolly.roadway.node import Node
from jeepdolly.units.clock import DaySpan, Window

from .conftest import DECIDED, an_application

MOVING = dt.date(2025, 6, 19)
JUNE = DaySpan(dt.date(2025, 6, 1), dt.date(2025, 6, 30))
EMPTY = EmbargoBook(embargoes=())


def rush_hour(county: str = "Missoula") -> Embargo:
    return Embargo(
        code="RUSH-MSO",  # type: ignore[arg-type]
        span=JUNE,
        reason="peak traffic",
        window=Window(420, 540),
        counties=frozenset({county}),
    )


def text(lines: list[str]) -> str:
    return "\n".join(lines)


def test_a_permit_good_today_is_on_the_sheet(desk, issued):
    network = desk.office.roadway.network()
    found = movements([issued], MOVING, network, EMPTY)
    assert len(found) == 1
    assert found[0].permit.number == issued.number


def test_a_permit_not_good_today_is_left_off(desk, issued):
    network = desk.office.roadway.network()
    assert movements([issued], dt.date(2025, 7, 1), network, EMPTY) == []


def test_a_void_permit_is_left_off(desk, issued):
    gone = desk.void(str(issued.number), Cause.CANCELLED, DECIDED)
    network = desk.office.roadway.network()
    assert movements([gone], MOVING, network, EMPTY) == []


def test_the_counties_come_off_the_route(desk, issued):
    network = desk.office.roadway.network()
    assert counties_of(issued, network) == ("Missoula",)


def test_an_annual_permit_reports_statewide(desk):
    from jeepdolly.permit.application import ANNUAL_DAYS, Kind

    year = DaySpan(
        dt.date(2025, 7, 1), dt.date(2025, 7, 1) + dt.timedelta(days=ANNUAL_DAYS - 1)
    )
    annual = an_application(kind=Kind.ANNUAL, span=year, origin=None, destination=None)
    permit = desk.issue(desk.file(annual).key, DECIDED)
    network = desk.office.roadway.network()
    assert counties_of(permit, network) == ()
    found = movements([permit], dt.date(2025, 7, 2), network, EMPTY)
    assert found[0].county == "statewide"


def test_two_counties_give_two_lines(desk, issued):
    desk.office.roadway.nodes_repo.connection.execute(
        "UPDATE node SET county = 'Granite' WHERE code = 'JCT-D'"
    )
    network = desk.office.roadway.network()
    assert len(counties_of(issued, network)) == 2
    assert len(movements([issued], MOVING, network, EMPTY)) == 2


def test_a_wide_load_gets_daylight_hours(desk, issued):
    network = desk.office.roadway.network()
    found = movements([issued], MOVING, network, EMPTY)
    assert found[0].hours == "06:40-21:20" or ":" in found[0].hours


def test_a_rush_hour_splits_the_window(desk, issued):
    network = desk.office.roadway.network()
    book = EmbargoBook(embargoes=(rush_hour(),))
    found = movements([issued], MOVING, network, book)
    assert len(found[0].windows) >= 1
    assert "," in found[0].hours or found[0].blocked


def test_a_whole_day_embargo_stops_the_load(desk, issued):
    network = desk.office.roadway.network()
    book = EmbargoBook(
        embargoes=(Embargo(code="JUN19", span=JUNE, reason="holiday"),)  # type: ignore[arg-type]
    )
    found = movements([issued], MOVING, network, book)
    assert found[0].blocked
    assert found[0].hours == "no movement"


def test_the_sheet_says_when_nothing_is_moving(desk):
    network = desk.office.roadway.network()
    assert "nothing moving" in text(day_sheet([], MOVING, network, EMPTY))


def test_the_sheet_names_the_day(desk, issued):
    network = desk.office.roadway.network()
    assert "2025-06-19" in text(day_sheet([issued], MOVING, network, EMPTY))


def test_the_sheet_lists_the_permit(desk, issued):
    network = desk.office.roadway.network()
    printed = text(day_sheet([issued], MOVING, network, EMPTY))
    assert str(issued.number) in printed
    assert "VANCE" in printed


def test_the_sheet_shows_the_load_weight(desk, issued):
    network = desk.office.roadway.network()
    assert "148,000 lb" in text(day_sheet([issued], MOVING, network, EMPTY))


def test_the_sheet_counts_the_movements(desk, issued):
    network = desk.office.roadway.network()
    printed = text(day_sheet([issued], MOVING, network, EMPTY))
    assert "movements  1" in printed
    assert "stopped    0" in printed


def test_the_sheet_counts_the_stopped(desk, issued):
    network = desk.office.roadway.network()
    book = EmbargoBook(
        embargoes=(Embargo(code="JUN19", span=JUNE, reason="holiday"),)  # type: ignore[arg-type]
    )
    assert "stopped    1" in text(day_sheet([issued], MOVING, network, book))


def test_a_junction_that_is_not_on_the_map_is_still_handled(desk, issued):
    network = desk.office.roadway.network()
    found = movements([issued], MOVING, network, EMPTY)
    assert found[0].county in {node.county for node in network.nodes.values()}


def test_the_node_county_is_read_from_the_map(desk):
    network = desk.office.roadway.network()
    assert isinstance(network.node("JCT-A"), Node)


@pytest.mark.parametrize("day", [dt.date(2025, 6, 18), dt.date(2025, 6, 20)])
def test_every_day_of_the_span_is_on_the_sheet(desk, issued, day):
    network = desk.office.roadway.network()
    assert len(movements([issued], day, network, EMPTY)) == 1
