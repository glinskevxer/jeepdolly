from collections.abc import Callable

import pytest
from click.testing import Result

from .test_permit import apply_one


@pytest.fixture
def issued(stocked: Callable[..., Result]) -> Callable[..., Result]:
    """A stocked office with one issued permit."""
    apply_one(stocked)
    stocked("permit", "issue", "1", "--on", "2025-06-17")
    return stocked


def test_permit_report_prints_the_sheet(issued):
    output = issued("report", "permit", "P-000001").output
    assert "oversize permit P-000001" in output
    assert "step-up transformer" in output


def test_permit_report_raises_on_one_that_is_not_there(issued):
    assert issued("report", "permit", "P-000099").exit_code == 1


def test_route_report_prints_the_legs(issued):
    output = issued("report", "route", "--from", "JCT-A", "--to", "JCT-D").output
    assert "route sheet JCT-A to JCT-D" in output
    assert "US-12" in output


def test_route_report_says_when_there_is_no_way(issued):
    issued("road", "node", "--code", "JCT-X", "--name", "island", "--county", "Ravalli")
    assert (
        "no way through" in issued("report", "route", "--from", "JCT-A", "--to", "JCT-X").output
    )


def test_day_report_lists_the_movement(issued):
    output = issued("report", "day", "2025-06-19").output
    assert "movement sheet for 2025-06-19" in output
    assert "P-000001" in output


def test_day_report_says_when_nothing_moves(issued):
    assert "nothing moving" in issued("report", "day", "2025-07-01").output


def test_day_report_refuses_a_bad_date(issued):
    assert issued("report", "day", "19/06/2025").exit_code == 1


def test_revenue_report_totals_the_take(issued):
    output = issued("report", "revenue").output
    assert "by month" in output
    assert "2025-06" in output


def test_revenue_report_filters_by_span(issued):
    output = issued("report", "revenue", "--first", "2025-07-01", "--last", "2025-07-31").output
    assert "nothing to report" in output


def test_revenue_report_says_when_there_is_nothing(run):
    assert "nothing to report" in run("report", "revenue").output


def test_the_carrier_sheet_names_the_carrier(issued):
    output = issued("report", "carrier", "VANCE").output
    assert "carrier file VANCE" in output
    assert "Vance Heavy Haul" in output


def test_the_carrier_sheet_lists_the_rig(issued):
    assert "R-00001" in issued("report", "carrier", "VANCE").output


def test_the_carrier_sheet_lists_the_permit(issued):
    assert "P-000001" in issued("report", "carrier", "VANCE").output


def test_the_carrier_sheet_shows_the_activity(issued):
    assert "recent activity" in issued("report", "carrier", "VANCE").output


def test_the_carrier_sheet_raises_on_one_that_is_not_there(issued):
    assert issued("report", "carrier", "NOBODY").exit_code == 1
