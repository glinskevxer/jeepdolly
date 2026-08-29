import datetime as dt

import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.permit.application import Application, Kind
from jeepdolly.report.counter import late, queue_sheet, standings, waiting
from jeepdolly.units.clock import DaySpan
from tests.permit.conftest import an_application

MONDAY = dt.date(2025, 6, 16)
LATER = dt.date(2025, 6, 25)


def an_annual() -> Application:
    """An annual application, promised three working days."""
    start = dt.date(2025, 7, 1)
    year = DaySpan(start, start + dt.timedelta(days=364))
    return an_application(kind=Kind.ANNUAL, span=year, origin=None, destination=None)


def test_an_empty_counter_has_nothing_standing():
    assert standings([], MONDAY) == []


def test_one_application_has_one_standing():
    assert len(standings([(1, an_application())], MONDAY)) == 1


def test_an_application_answered_the_next_day_is_not_late():
    assert late([(1, an_application())], dt.date(2025, 6, 17)) == []


def test_an_application_left_a_week_is_late():
    assert len(late([(1, an_application())], LATER)) == 1


def test_an_application_inside_the_promise_is_waiting():
    assert len(waiting([(1, an_application())], MONDAY)) == 1


def test_a_late_application_is_not_counted_as_waiting():
    assert waiting([(1, an_application())], LATER) == []


def test_the_worst_late_one_comes_first():
    old = an_application(filed_on=dt.date(2025, 6, 2))
    found = late([(1, an_application()), (2, old)], LATER)
    assert found[0].key == 2


def test_the_soonest_due_comes_first_among_those_waiting():
    found = waiting([(1, an_annual()), (2, an_application())], MONDAY)
    assert found[0].key == 2


def test_a_datetime_day_is_refused():
    with pytest.raises(BadValueError):
        standings([], dt.datetime(2025, 6, 16, tzinfo=dt.UTC))


def test_an_empty_counter_prints_nothing_waiting():
    assert any("nothing waiting" in line for line in queue_sheet([], MONDAY))


def test_the_sheet_names_the_day_it_was_read():
    assert any("2025-06-16" in line for line in queue_sheet([], MONDAY))


def test_the_sheet_lists_what_is_waiting():
    body = "\n".join(queue_sheet([(1, an_application())], MONDAY))
    assert "VANCE" in body
    assert "still inside it" in body


def test_the_sheet_puts_the_late_ones_first():
    old = an_application(filed_on=dt.date(2025, 6, 2))
    fresh = an_application(
        filed_on=dt.date(2025, 6, 23),
        span=DaySpan(dt.date(2025, 6, 24), dt.date(2025, 6, 26)),
    )
    body = "\n".join(queue_sheet([(1, fresh), (2, old)], dt.date(2025, 6, 24)))
    assert body.index("past the promise") < body.index("still inside it")


def test_a_counter_with_nothing_late_has_no_late_section():
    lines = queue_sheet([(1, an_application())], MONDAY)
    assert [line for line in lines if line.strip() == "past the promise"] == []


def test_the_sheet_counts_what_is_waiting():
    lines = queue_sheet([(1, an_application())], MONDAY)
    assert any("waiting" in line and "1" in line for line in lines)


def test_the_sheet_names_the_worst_case():
    lines = queue_sheet([(1, an_application())], LATER)
    assert any("working days" in line for line in lines)


def test_a_quiet_counter_reports_nothing_as_the_worst():
    lines = queue_sheet([(1, an_application())], MONDAY)
    assert any("0 working days" in line for line in lines)


def test_the_days_over_column_is_blank_for_one_on_time():
    body = "\n".join(queue_sheet([(1, an_application())], MONDAY))
    assert "days over" in body
