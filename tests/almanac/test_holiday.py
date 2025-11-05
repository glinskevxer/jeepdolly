import datetime as dt

import pytest

from jeepdolly.almanac.embargo import EmbargoBook
from jeepdolly.almanac.holiday import (
    FIXED,
    FLOATING,
    SHOULDER_AFTER,
    SHOULDER_BEFORE,
    Holiday,
    embargoes_in,
    holidays_in,
    last_weekday,
    nth_weekday,
    observed,
)
from jeepdolly.errors import BadValueError


def named(year: int) -> dict[str, dt.date]:
    """The year's holidays keyed by name."""
    return {h.name: h.day for h in holidays_in(year)}


def test_the_third_monday_of_january_2025():
    assert nth_weekday(2025, 1, 0, 3) == dt.date(2025, 1, 20)


def test_the_first_monday_of_september_2025():
    assert nth_weekday(2025, 9, 0, 1) == dt.date(2025, 9, 1)


def test_the_fourth_thursday_of_november_2025():
    assert nth_weekday(2025, 11, 3, 4) == dt.date(2025, 11, 27)


def test_nth_weekday_refuses_a_count_of_zero():
    with pytest.raises(BadValueError):
        nth_weekday(2025, 1, 0, 0)


def test_nth_weekday_refuses_a_count_that_runs_past_the_month():
    with pytest.raises(BadValueError):
        nth_weekday(2025, 2, 0, 5)


def test_the_last_monday_of_may_2025():
    assert last_weekday(2025, 5, 0) == dt.date(2025, 5, 26)


def test_the_last_friday_of_december_2025():
    assert last_weekday(2025, 12, 4) == dt.date(2025, 12, 26)


def test_a_weekday_holiday_is_kept_on_the_day():
    assert observed(dt.date(2025, 7, 4)) == dt.date(2025, 7, 4)


def test_a_saturday_holiday_moves_back_to_friday():
    assert observed(dt.date(2026, 7, 4)) == dt.date(2026, 7, 3)


def test_a_sunday_holiday_moves_forward_to_monday():
    assert observed(dt.date(2027, 7, 4)) == dt.date(2027, 7, 5)


def test_the_year_has_eleven_holidays():
    assert len(holidays_in(2025)) == len(FIXED) + len(FLOATING)


def test_the_holidays_come_out_in_order():
    days = [h.day for h in holidays_in(2025)]
    assert days == sorted(days)


def test_independence_day_2025_is_a_friday():
    assert named(2025)["independence"] == dt.date(2025, 7, 4)


def test_thanksgiving_2025_is_the_twenty_seventh():
    assert named(2025)["thanksgiving"] == dt.date(2025, 11, 27)


def test_memorial_day_2025_is_the_twenty_sixth():
    assert named(2025)["memorial"] == dt.date(2025, 5, 26)


def test_christmas_2027_is_observed_on_the_monday():
    assert named(2027)["christmas"] == dt.date(2027, 12, 24)


def test_every_holiday_falls_on_a_weekday():
    for year in range(2024, 2035):
        for holiday in holidays_in(year):
            assert holiday.day.weekday() < 5, holiday


def test_holidays_in_refuses_a_bool():
    with pytest.raises(BadValueError):
        holidays_in(True)


def test_holidays_in_refuses_a_two_digit_year():
    with pytest.raises(BadValueError):
        holidays_in(25)


def test_the_span_covers_the_day_before_and_after():
    holiday = Holiday(day=dt.date(2025, 7, 4), name="independence")
    assert holiday.span.first == dt.date(2025, 7, 4) - dt.timedelta(days=SHOULDER_BEFORE)
    assert holiday.span.last == dt.date(2025, 7, 4) + dt.timedelta(days=SHOULDER_AFTER)


def test_a_holiday_refuses_a_datetime():
    with pytest.raises(BadValueError):
        Holiday(day=dt.datetime(2025, 7, 4, tzinfo=dt.UTC), name="independence")


def test_a_holiday_refuses_an_empty_name():
    with pytest.raises(BadValueError):
        Holiday(day=dt.date(2025, 7, 4), name="  ")


def test_a_holiday_dashes_a_two_word_name():
    assert Holiday(day=dt.date(2025, 7, 4), name="new year").name == "new-year"


def test_a_holiday_code_carries_the_year():
    holiday = Holiday(day=dt.date(2025, 7, 4), name="independence", short="JULY4")
    assert holiday.code == "JULY4-25"


def test_a_holiday_without_a_short_code_takes_one_from_its_name():
    assert Holiday(day=dt.date(2025, 7, 4), name="independence").short == "INDEPEND"


def test_every_holiday_code_fits_in_a_code():
    for year in range(2024, 2035):
        for holiday in holidays_in(year):
            assert len(str(holiday.code)) <= 16


def test_a_holiday_prints_its_day():
    assert (
        str(Holiday(day=dt.date(2025, 7, 4), name="independence")) == "independence 2025-07-04"
    )


def test_the_embargoes_are_statewide():
    assert all(e.statewide for e in embargoes_in(2025))


def test_the_embargoes_run_all_day():
    assert all(e.all_day for e in embargoes_in(2025))


def test_every_embargo_says_which_holiday_it_is():
    assert all("holiday" in e.reason for e in embargoes_in(2025))


def test_the_embargoes_make_a_book_without_a_clash():
    book = EmbargoBook(embargoes=tuple(embargoes_in(2025)))
    assert len(book) == 11


def test_a_load_may_not_move_on_independence_day():
    book = EmbargoBook(embargoes=tuple(embargoes_in(2025)))
    assert not book.free(dt.date(2025, 7, 4), 600, "Missoula")


def test_a_load_may_move_the_week_after():
    book = EmbargoBook(embargoes=tuple(embargoes_in(2025)))
    assert book.free(dt.date(2025, 7, 14), 600, "Missoula")


def test_two_years_of_embargoes_do_not_clash():
    both = tuple(embargoes_in(2025)) + tuple(embargoes_in(2026))
    assert len(EmbargoBook(embargoes=both)) == 22
