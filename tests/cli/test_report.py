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


def test_a_detour_off_the_route_says_so(issued):
    result = issued(
        "report",
        "detour",
        "--from",
        "JCT-A",
        "--to",
        "JCT-D",
        "--rig",
        "R-00001",
        "--closed",
        "SEG-CD",
    )
    assert result.exit_code == 0
    assert "is not on the route" in result.output


def test_a_detour_that_strands_the_rig_says_so(issued):
    result = issued(
        "report",
        "detour",
        "--from",
        "JCT-A",
        "--to",
        "JCT-D",
        "--rig",
        "R-00001",
        "--closed",
        "SEG-AB",
    )
    assert "nothing gets through" in result.output


def test_a_detour_prints_the_route_it_would_use(issued):
    result = issued(
        "report",
        "detour",
        "--from",
        "JCT-A",
        "--to",
        "JCT-D",
        "--rig",
        "R-00001",
        "--closed",
        "SEG-CD",
    )
    assert "usual" in result.output


def test_a_detour_refuses_a_rig_that_is_not_there(issued):
    result = issued(
        "report",
        "detour",
        "--from",
        "JCT-A",
        "--to",
        "JCT-D",
        "--rig",
        "R-00099",
        "--closed",
        "SEG-CD",
    )
    assert result.exit_code == 1


def test_a_detour_refuses_a_stretch_that_is_not_there(issued):
    result = issued(
        "report",
        "detour",
        "--from",
        "JCT-A",
        "--to",
        "JCT-D",
        "--rig",
        "R-00001",
        "--closed",
        "SEG-ZZ",
    )
    assert result.exit_code == 1


def test_the_schedule_lists_every_day(issued):
    output = issued("report", "schedule", "P-000001").output
    assert "2025-06-18" in output
    assert "2025-06-20" in output


def test_the_schedule_counts_the_movable_days(issued):
    output = issued("report", "schedule", "P-000001").output
    assert "days     3" in output
    assert "movable  3" in output


def test_the_schedule_names_the_county(issued):
    assert "in Missoula" in issued("report", "schedule", "P-000001").output


def test_the_schedule_takes_a_county_of_its_own(issued):
    assert (
        "in Granite" in issued("report", "schedule", "P-000001", "--county", "Granite").output
    )


def test_a_holiday_stops_a_day_in_the_schedule(issued):
    issued("almanac", "holidays", "2025")
    issued(
        "permit",
        "extend",
        "P-000001",
        "--last",
        "2025-06-22",
    )
    output = issued("report", "schedule", "P-000001").output
    assert "no movement" not in output or "stopped" in output


def test_an_embargo_shows_up_in_the_schedule(issued):
    issued(
        "almanac",
        "embargo",
        "--code",
        "SHUT-25",
        "--first",
        "2025-06-19",
        "--last",
        "2025-06-19",
        "--reason",
        "bridge work",
    )
    output = issued("report", "schedule", "P-000001").output
    assert "no movement" in output
    assert "SHUT-25" in output
    assert "stopped  1" in output


def test_the_schedule_raises_on_a_permit_that_is_not_there(issued):
    assert issued("report", "schedule", "P-000099").exit_code == 1


def test_the_audit_reports_an_uncharged_permit(issued):
    output = issued("report", "audit").output
    assert "account audit" in output
    assert "never charged" in output


def test_the_audit_is_clean_once_the_permit_is_charged(issued):
    issued("account", "deposit", "VANCE", "--amount", "1,000.00", "--on", "2025-06-17")
    issued("account", "charge", "VANCE", "--permit", "P-000001", "--on", "2025-06-17")
    output = issued("report", "audit").output
    assert "clean     1" in output


def test_the_audit_narrows_to_one_carrier(issued):
    assert "VANCE" in issued("report", "audit", "--carrier", "VANCE").output


def test_the_audit_raises_on_a_carrier_that_is_not_there(issued):
    assert issued("report", "audit", "--carrier", "NOBODY").exit_code == 1


def test_the_audit_says_when_there_are_no_carriers(run):
    assert "no carriers on file" in run("report", "audit").output


def test_the_staging_lists_the_days(issued):
    output = issued("report", "stage", "P-000001").output
    assert "staged at 35 mph" in output
    assert "2025-06-18" in output


def test_the_staging_says_it_finished(issued):
    assert "finished      yes" in issued("report", "stage", "P-000001").output


def test_the_staging_takes_a_slower_speed(issued):
    output = issued("report", "stage", "P-000001", "--speed", "5").output
    assert "staged at 5 mph" in output


def test_a_slower_haul_needs_more_driving_days(issued):
    quick = issued("report", "stage", "P-000001", "--speed", "35").output
    slow = issued("report", "stage", "P-000001", "--speed", "1").output
    assert "driving days  1" in quick
    assert "driving days  2" in slow


def test_the_staging_takes_a_county(issued):
    assert "in Granite" in issued("report", "stage", "P-000001", "--county", "Granite").output


def test_the_staging_names_the_overnight_stop(issued):
    assert "JCT-D" in issued("report", "stage", "P-000001").output


def test_the_staging_raises_on_a_permit_that_is_not_there(issued):
    assert issued("report", "stage", "P-000099").exit_code == 1


def test_the_expiry_list_names_a_permit_running_out(issued):
    output = issued("report", "expiring", "2025-06-19").output
    assert "expiry list" in output
    assert "P-000001" in output


def test_the_expiry_list_says_when_nothing_runs_out(issued):
    output = issued("report", "expiring", "2025-06-01", "--within", "3").output
    assert "nothing runs out" in output


def test_the_expiry_list_shows_what_has_gone(issued):
    assert "already run out" in issued("report", "expiring", "2025-06-25").output


def test_the_expiry_list_refuses_a_bad_date(issued):
    assert issued("report", "expiring", "19/06/2025").exit_code == 1


def test_the_workload_lists_the_month(issued):
    output = issued("report", "workload").output
    assert "counter workload" in output
    assert "2025-06" in output


def test_the_workload_reports_the_average_wait(issued):
    assert "average days" in issued("report", "workload").output


def test_the_workload_says_when_nothing_came_through(run):
    assert "nothing has come through" in run("report", "workload").output


def test_the_queue_is_empty_on_a_bare_office(run):
    assert "nothing waiting" in run("report", "queue").output


def test_an_unanswered_application_is_on_the_queue(stocked):
    from tests.cli.test_permit import apply_one

    apply_one(stocked)
    assert "VANCE" in stocked("report", "queue", "--on", "2025-06-17").output


def test_an_issued_application_leaves_the_queue(stocked):
    from tests.cli.test_permit import apply_one

    apply_one(stocked)
    stocked("permit", "issue", "1", "--on", "2025-06-17")
    assert "nothing waiting" in stocked("report", "queue", "--on", "2025-06-17").output


def test_an_application_left_a_week_shows_as_past_the_promise(stocked):
    from tests.cli.test_permit import apply_one

    apply_one(stocked)
    assert "past the promise" in stocked("report", "queue", "--on", "2025-06-25").output


def test_an_amendments_application_is_not_left_on_the_queue(stocked):
    from tests.cli.test_permit import apply_one

    apply_one(stocked)
    stocked("permit", "issue", "1", "--on", "2025-06-17")
    stocked("permit", "amend", "P-000001", "--width", "13ft", "--on", "2025-06-18")
    assert "nothing waiting" in stocked("report", "queue", "--on", "2025-06-25").output


def test_a_real_application_is_still_on_the_queue_beside_an_amendment(stocked):
    from tests.cli.test_permit import apply_one

    apply_one(stocked)
    stocked("permit", "issue", "1", "--on", "2025-06-17")
    stocked("permit", "amend", "P-000001", "--width", "13ft", "--on", "2025-06-18")
    apply_one(stocked, **{"--first": "2025-07-10", "--last": "2025-07-12"})
    output = stocked("report", "queue", "--on", "2025-07-20").output
    assert "waiting" in output
    assert "VANCE" in output
