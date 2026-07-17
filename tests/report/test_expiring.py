import datetime as dt

import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.permit.revoke import Cause
from jeepdolly.report.expiring import SOON, Expiry, expired, expiring, expiry_sheet

from .conftest import DECIDED, an_application

INSIDE = dt.date(2025, 6, 19)
AFTER = dt.date(2025, 6, 25)


def text(lines: list[str]) -> str:
    """The lines joined, for a substring check."""
    return "\n".join(lines)


def test_a_permit_running_out_soon_is_listed(issued):
    found = expiring([issued], INSIDE)
    assert [one.number for one in found] == [str(issued.number)]


def test_a_permit_running_out_today_is_listed(issued):
    found = expiring([issued], dt.date(2025, 6, 20))
    assert found[0].today
    assert found[0].days_left == 0


def test_a_permit_running_out_further_off_is_not_listed(issued):
    assert expiring([issued], dt.date(2025, 6, 1), within=3) == []


def test_a_permit_that_has_run_out_is_not_in_the_soon_list(issued):
    assert expiring([issued], AFTER) == []


def test_a_permit_that_has_run_out_is_in_the_gone_list(issued):
    found = expired([issued], AFTER)
    assert found[0].gone
    assert found[0].days_left == -5


def test_a_void_permit_is_on_neither_list(desk, issued):
    gone = desk.void(str(issued.number), Cause.CANCELLED, DECIDED)
    assert expiring([gone], INSIDE) == []
    assert expired([gone], AFTER) == []


def test_the_soon_list_is_soonest_first(desk, issued):
    second = desk.issue(desk.file(an_application()).key, DECIDED)
    longer = desk.office.permits.save_state(second.extended(dt.date(2025, 6, 23)))
    found = expiring([longer, issued], INSIDE)
    assert [one.number for one in found] == [str(issued.number), str(longer.number)]


def test_the_gone_list_is_longest_gone_first(desk, issued):
    second = desk.issue(desk.file(an_application()).key, DECIDED)
    longer = desk.office.permits.save_state(second.extended(dt.date(2025, 6, 23)))
    found = expired([longer, issued], dt.date(2025, 7, 1))
    assert found[0].number == str(issued.number)


def test_a_within_that_is_not_a_number_is_refused(issued):
    with pytest.raises(BadValueError):
        expiring([issued], INSIDE, within=True)


def test_a_negative_within_is_refused(issued):
    with pytest.raises(BadValueError):
        expiring([issued], INSIDE, within=-1)


def test_a_datetime_is_refused(issued):
    with pytest.raises(BadValueError):
        expiring([issued], dt.datetime(2025, 6, 19, tzinfo=dt.UTC))


def test_an_expiry_prints_the_days_left():
    made = Expiry(
        days_left=3,
        number="P-000001",
        carrier="VANCE",
        last_day=dt.date(2025, 6, 20),
        state="active",
    )
    assert str(made) == "P-000001 VANCE has 3 days left"


def test_an_expiry_prints_that_it_runs_out_today():
    made = Expiry(
        days_left=0,
        number="P-000001",
        carrier="VANCE",
        last_day=dt.date(2025, 6, 20),
        state="active",
    )
    assert "runs out today" in str(made)


def test_an_expiry_prints_how_long_ago_it_went():
    made = Expiry(
        days_left=-4,
        number="P-000001",
        carrier="VANCE",
        last_day=dt.date(2025, 6, 20),
        state="active",
    )
    assert "ran out 4 days ago" in str(made)


def test_the_sheet_says_when_nothing_runs_out(issued):
    assert "nothing runs out" in text(expiry_sheet([issued], dt.date(2025, 6, 1), within=3))


def test_the_sheet_lists_a_permit_running_out(issued):
    printed = text(expiry_sheet([issued], INSIDE))
    assert "running out" in printed
    assert str(issued.number) in printed


def test_the_sheet_lists_a_permit_that_has_gone(issued):
    assert "already run out" in text(expiry_sheet([issued], AFTER))


def test_the_sheet_totals_the_fees_at_risk(issued):
    from jeepdolly.units.money import format_money

    assert format_money(issued.fee) in text(expiry_sheet([issued], INSIDE))


def test_the_sheet_may_leave_the_fee_column_off(issued):
    printed = text(expiry_sheet([issued], INSIDE, fee_column=False))
    assert "running out" in printed


def test_the_default_window_is_a_fortnight():
    assert SOON == 14
