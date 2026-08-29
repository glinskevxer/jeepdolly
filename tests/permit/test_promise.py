import datetime as dt

import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.permit.application import Kind
from jeepdolly.permit.promise import (
    MAX_SPAN_DAYS,
    TARGET_DAYS,
    Standing,
    holidays_between,
    promised_by,
    standing_of,
    working_days,
)
from tests.permit.conftest import an_application

MONDAY = dt.date(2025, 6, 16)
FRIDAY = dt.date(2025, 6, 20)
JULY = dt.date(2025, 7, 3)


def a_standing(**over: object) -> Standing:
    kw: dict[str, object] = {
        "over": 0,
        "key": 1,
        "carrier": "VANCE",
        "kind": Kind.TRIP,
        "filed_on": MONDAY,
        "due": dt.date(2025, 6, 17),
    }
    kw.update(over)
    return Standing(**kw)  # type: ignore[arg-type]


def test_every_kind_of_permit_has_a_promise():
    for kind in Kind:
        assert TARGET_DAYS[kind] >= 1


def test_a_superload_is_promised_the_longest():
    assert TARGET_DAYS[Kind.SUPERLOAD] == max(TARGET_DAYS.values())


def test_one_working_day_is_the_next_day_midweek():
    assert working_days(MONDAY, dt.date(2025, 6, 17)) == 1


def test_a_weekend_counts_for_nothing():
    assert working_days(FRIDAY, dt.date(2025, 6, 22)) == 0


def test_the_monday_after_a_weekend_counts_as_one():
    assert working_days(FRIDAY, dt.date(2025, 6, 23)) == 1


def test_a_day_on_or_before_the_first_counts_for_nothing():
    assert working_days(MONDAY, MONDAY) == 0
    assert working_days(MONDAY, MONDAY - dt.timedelta(days=3)) == 0


def test_a_holiday_counts_for_nothing():
    assert working_days(JULY, dt.date(2025, 7, 5)) == 0


def test_a_span_longer_than_the_cap_is_refused():
    with pytest.raises(BadValueError):
        working_days(MONDAY, MONDAY + dt.timedelta(days=MAX_SPAN_DAYS + 1))


def test_a_datetime_is_refused_by_the_working_day_count():
    with pytest.raises(BadValueError):
        working_days(dt.datetime(2025, 6, 16, tzinfo=dt.UTC), FRIDAY)


def test_independence_day_is_a_day_the_office_is_shut():
    assert dt.date(2025, 7, 4) in holidays_between(JULY, dt.date(2025, 7, 6))


def test_an_ordinary_week_holds_no_holidays():
    assert holidays_between(dt.date(2025, 9, 8), dt.date(2025, 9, 12)) == frozenset()


def test_juneteenth_and_its_shoulder_are_days_the_office_is_shut():
    found = holidays_between(MONDAY, FRIDAY)
    assert dt.date(2025, 6, 19) in found
    assert len(found) > 1


def test_a_span_across_new_year_reads_both_years():
    found = holidays_between(dt.date(2025, 12, 20), dt.date(2026, 1, 5))
    assert any(day.year == 2025 for day in found)
    assert any(day.year == 2026 for day in found)


def test_a_datetime_is_refused_by_the_holiday_lookup():
    with pytest.raises(BadValueError):
        holidays_between(dt.datetime(2025, 6, 16, tzinfo=dt.UTC), FRIDAY)


def test_a_trip_filed_midweek_is_promised_the_next_day():
    assert promised_by(MONDAY, Kind.TRIP) == dt.date(2025, 6, 17)


def test_a_trip_filed_on_a_friday_is_promised_the_monday():
    assert promised_by(FRIDAY, Kind.TRIP) == dt.date(2025, 6, 23)


def test_a_promise_steps_over_a_holiday():
    assert promised_by(dt.date(2025, 7, 3), Kind.TRIP) == dt.date(2025, 7, 7)


def test_an_annual_is_promised_three_working_days():
    assert promised_by(MONDAY, Kind.ANNUAL) == dt.date(2025, 6, 24)


def test_the_annual_promise_steps_over_a_whole_holiday_week():
    plain = promised_by(dt.date(2025, 9, 8), Kind.ANNUAL)
    assert plain == dt.date(2025, 9, 11)


def test_a_superload_is_promised_two_weeks_of_working_days():
    assert promised_by(MONDAY, Kind.SUPERLOAD) == dt.date(2025, 7, 7)


def test_a_datetime_filing_day_is_refused():
    with pytest.raises(BadValueError):
        promised_by(dt.datetime(2025, 6, 16, tzinfo=dt.UTC), Kind.TRIP)


def test_an_application_answered_on_time_is_not_late():
    found = standing_of(1, an_application(), dt.date(2025, 6, 17))
    assert not found.late


def test_an_application_left_a_week_is_late():
    found = standing_of(1, an_application(), dt.date(2025, 6, 25))
    assert found.late
    assert found.over > 0


def test_the_lateness_is_counted_in_working_days():
    found = standing_of(1, an_application(), dt.date(2025, 6, 23))
    assert found.over == 1


def test_a_standing_carries_the_day_it_was_promised():
    assert standing_of(1, an_application(), MONDAY).due == dt.date(2025, 6, 17)


def test_something_that_is_not_an_application_is_refused():
    with pytest.raises(BadValueError):
        standing_of(1, "a trip permit", MONDAY)  # type: ignore[arg-type]


def test_a_standing_on_key_zero_is_refused():
    with pytest.raises(BadValueError):
        a_standing(key=0)


def test_a_standing_with_no_carrier_is_refused():
    with pytest.raises(BadValueError):
        a_standing(carrier="   ")


def test_a_standing_upper_cases_the_carrier():
    assert a_standing(carrier="vance").carrier == "VANCE"


def test_a_late_standing_says_how_far_over():
    assert "3 days over" in str(a_standing(over=3))


def test_one_day_over_reads_in_the_singular():
    assert "1 day over" in str(a_standing(over=1))


def test_a_standing_on_time_says_when_it_is_due():
    assert "due 2025-06-17" in str(a_standing())


def test_the_worst_overdue_sorts_first():
    late = [a_standing(over=1), a_standing(over=5, key=2)]
    assert max(late).over == 5
