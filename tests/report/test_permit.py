import datetime as dt

from jeepdolly.permit.revoke import Cause
from jeepdolly.report.permit import conditions, fee_table, permit_sheet, route_sheet
from jeepdolly.route.search import clearing
from jeepdolly.units.length import feet

from .conftest import DECIDED, a_load, an_application


def text(lines: list[str]) -> str:
    """The lines joined, for a substring check."""
    return "\n".join(lines)


def test_the_sheet_names_the_permit(issued):
    assert issued.number in text(permit_sheet(issued))


def test_the_sheet_names_the_carrier(issued):
    assert "carrier" in text(permit_sheet(issued))
    assert "VANCE" in text(permit_sheet(issued))


def test_the_sheet_shows_the_span(issued):
    assert "2025-06-18..2025-06-20" in text(permit_sheet(issued))


def test_the_sheet_describes_the_load(issued):
    printed = text(permit_sheet(issued))
    assert "step-up transformer" in printed
    assert "148,000 lb" in printed


def test_the_sheet_says_the_load_is_not_divisible(issued):
    assert "divisible" in text(permit_sheet(issued))
    assert "no" in text(permit_sheet(issued))


def test_the_sheet_shows_the_route_ends(issued):
    printed = text(permit_sheet(issued))
    assert "JCT-A" in printed
    assert "JCT-D" in printed


def test_the_sheet_shows_the_distance(issued):
    assert "43.00 mi" in text(permit_sheet(issued))


def test_the_sheet_lists_the_escort(issued):
    assert "rear escort" in text(permit_sheet(issued))


def test_the_sheet_shows_the_fee_lines(issued):
    printed = text(permit_sheet(issued))
    assert "MILES" in printed
    assert "total" in printed


def test_the_fee_table_ends_with_the_total(issued):
    lines = fee_table(issued)
    assert "total" in lines[-1]


def test_the_fee_table_adds_up(issued):
    from jeepdolly.units.money import format_money

    assert format_money(issued.fee) in fee_table(issued)[-1]


def test_a_void_permit_says_it_is_not_valid(desk, issued):
    gone = desk.void(str(issued.number), Cause.CANCELLED, DECIDED)
    printed = text(permit_sheet(gone))
    assert "NOT VALID" in printed
    assert "carrier cancelled" in printed


def test_an_active_permit_does_not_say_that(issued):
    assert "NOT VALID" not in text(permit_sheet(issued))


def test_conditions_list_the_escorts(issued):
    assert any("rear" in line for line in conditions(issued))


def test_conditions_include_a_note(desk):
    filed = desk.file(an_application(load=a_load(rear_overhang=feet(6), length=feet(40))))
    permit = desk.issue(filed.key, DECIDED)
    assert any("flags" in line for line in conditions(permit))


def test_an_annual_permit_prints_no_route(desk):
    from jeepdolly.permit.application import ANNUAL_DAYS, Kind
    from jeepdolly.units.clock import DaySpan

    year = DaySpan(
        dt.date(2025, 7, 1), dt.date(2025, 7, 1) + dt.timedelta(days=ANNUAL_DAYS - 1)
    )
    annual = an_application(kind=Kind.ANNUAL, span=year, origin=None, destination=None)
    filed = desk.file(annual)
    permit = desk.issue(filed.key, DECIDED)
    printed = text(permit_sheet(permit))
    assert "route" not in printed


def test_the_route_sheet_has_a_line_per_leg(desk):
    network = desk.office.roadway.network()
    seen = desk.assess(desk.file(an_application()).key)
    assert seen.route is not None
    lines = route_sheet(seen.route, network)
    assert "SEG" not in lines[0]
    assert any("US-12" in line for line in lines)
    assert any("SR-200" in line for line in lines)


def test_the_route_sheet_runs_a_total(desk):
    network = desk.office.roadway.network()
    seen = desk.assess(desk.file(an_application()).key)
    assert seen.route is not None
    assert "43.00 mi" in text(route_sheet(seen.route, network))


def test_the_route_sheet_calls_out_the_structures(desk):
    network = desk.office.roadway.network()
    seen = desk.assess(desk.file(an_application()).key)
    assert seen.route is not None
    printed = text(route_sheet(seen.route, network))
    assert "Clark Fork bridge" in printed
    assert "96,000 lb" in printed


def test_a_route_with_no_structures_prints_no_section(desk):
    network = desk.office.roadway.network()
    route = clearing(
        network,
        "JCT-A",
        "JCT-B",
        desk.office.rigs.get("R-00001").config,
        a_load(),
    )
    assert route is not None
    assert "structures on the route" not in text(route_sheet(route, network))


def test_the_route_sheet_numbers_its_legs(desk):
    network = desk.office.roadway.network()
    seen = desk.assess(desk.file(an_application()).key)
    assert seen.route is not None
    lines = route_sheet(seen.route, network)
    assert lines[4].strip().startswith("1")
