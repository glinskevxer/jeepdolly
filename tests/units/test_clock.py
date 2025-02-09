import datetime as dt

import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.units.clock import (
    MINUTES_PER_DAY,
    WEEKEND,
    DaySpan,
    Window,
    format_clock,
    format_day,
    minute_of_day,
    parse_clock,
    parse_day,
)


def test_parse_day_reads_an_iso_date():
    assert parse_day("2025-03-04") == dt.date(2025, 3, 4)


def test_parse_day_strips_space():
    assert parse_day("  2025-03-04 ") == dt.date(2025, 3, 4)


def test_parse_day_refuses_another_format():
    with pytest.raises(BadValueError):
        parse_day("03/04/2025")


def test_parse_day_refuses_a_date():
    with pytest.raises(BadValueError):
        parse_day(dt.date(2025, 3, 4))  # type: ignore[arg-type]


def test_format_day_round_trips():
    day = dt.date(2026, 1, 1)
    assert parse_day(format_day(day)) == day


def test_minute_of_day_allows_midnight():
    assert minute_of_day(0) == 0


def test_minute_of_day_allows_the_last_minute():
    assert minute_of_day(MINUTES_PER_DAY - 1) == 1439


def test_minute_of_day_refuses_the_whole_day():
    with pytest.raises(BadValueError):
        minute_of_day(MINUTES_PER_DAY)


def test_minute_of_day_refuses_negative():
    with pytest.raises(BadValueError):
        minute_of_day(-1)


def test_minute_of_day_refuses_a_bool():
    with pytest.raises(BadValueError):
        minute_of_day(True)


@pytest.mark.parametrize(
    ("text", "want"), [("07:30", 450), ("0730", 450), ("00:00", 0), ("23:59", 1439)]
)
def test_parse_clock_reads_the_forms(text, want):
    assert parse_clock(text) == want


def test_parse_clock_refuses_twenty_four_hundred():
    with pytest.raises(BadValueError):
        parse_clock("24:00")


def test_parse_clock_refuses_sixty_minutes():
    with pytest.raises(BadValueError):
        parse_clock("07:60")


def test_parse_clock_refuses_junk():
    with pytest.raises(BadValueError):
        parse_clock("half seven")


def test_parse_clock_refuses_a_number():
    with pytest.raises(BadValueError):
        parse_clock(730)  # type: ignore[arg-type]


def test_format_clock_pads():
    assert format_clock(450) == "07:30"


def test_format_clock_round_trips():
    for value in (0, 1, 450, 1439):
        assert parse_clock(format_clock(value)) == value


def test_window_holds_its_ends():
    w = Window(360, 1080)
    assert (w.start, w.end) == (360, 1080)


def test_window_is_half_open_at_the_end():
    w = Window(360, 1080)
    assert w.covers(360)
    assert w.covers(1079)
    assert not w.covers(1080)


def test_window_does_not_cover_before_the_start():
    assert not Window(360, 1080).covers(359)


def test_window_length():
    assert Window(360, 1080).minutes == 720


def test_wrapping_window_says_so():
    assert Window(1260, 360).wraps


def test_plain_window_does_not_wrap():
    assert not Window(360, 1080).wraps


def test_wrapping_window_covers_both_sides_of_midnight():
    w = Window(1260, 360)
    assert w.covers(1260)
    assert w.covers(0)
    assert w.covers(359)
    assert not w.covers(360)
    assert not w.covers(1259)


def test_wrapping_window_length():
    assert Window(1260, 360).minutes == 540


def test_empty_window_covers_nothing():
    w = Window(600, 600)
    assert w.empty
    assert w.minutes == 0
    assert not w.covers(600)


def test_window_refuses_a_minute_outside_the_day():
    with pytest.raises(BadValueError):
        Window(0, MINUTES_PER_DAY)


def test_window_overlap_is_true_when_they_share_a_minute():
    assert Window(360, 1080).overlaps(Window(1000, 1200))


def test_window_overlap_is_false_when_they_touch_at_the_edge():
    assert not Window(360, 600).overlaps(Window(600, 900))


def test_window_overlap_is_symmetric():
    a, b = Window(1260, 360), Window(300, 400)
    assert a.overlaps(b) == b.overlaps(a) is True


def test_window_overlap_with_an_empty_window_is_false():
    assert not Window(360, 1080).overlaps(Window(600, 600))


def test_window_prints_its_ends():
    assert str(Window(360, 1080)) == "06:00-18:00"


def test_window_orders_by_start():
    assert sorted([Window(600, 700), Window(300, 400)])[0].start == 300


def test_day_span_counts_both_ends():
    span = DaySpan(dt.date(2025, 3, 1), dt.date(2025, 3, 5))
    assert span.days == 5


def test_one_day_span_has_one_day():
    day = dt.date(2025, 3, 1)
    assert DaySpan(day, day).days == 1


def test_day_span_covers_its_ends():
    span = DaySpan(dt.date(2025, 3, 1), dt.date(2025, 3, 5))
    assert span.covers(dt.date(2025, 3, 1))
    assert span.covers(dt.date(2025, 3, 5))
    assert not span.covers(dt.date(2025, 2, 28))
    assert not span.covers(dt.date(2025, 3, 6))


def test_day_span_refuses_a_backwards_range():
    with pytest.raises(BadValueError):
        DaySpan(dt.date(2025, 3, 5), dt.date(2025, 3, 1))


def test_day_span_refuses_a_datetime():
    with pytest.raises(BadValueError):
        DaySpan(dt.datetime(2025, 3, 1, 12, 0, tzinfo=dt.UTC), dt.date(2025, 3, 5))


def test_day_span_refuses_text():
    with pytest.raises(BadValueError):
        DaySpan("2025-03-01", dt.date(2025, 3, 5))  # type: ignore[arg-type]


def test_day_span_iterates_every_day():
    span = DaySpan(dt.date(2025, 3, 1), dt.date(2025, 3, 4))
    assert [d.day for d in span] == [1, 2, 3, 4]


def test_day_span_overlap():
    a = DaySpan(dt.date(2025, 3, 1), dt.date(2025, 3, 10))
    b = DaySpan(dt.date(2025, 3, 10), dt.date(2025, 3, 20))
    c = DaySpan(dt.date(2025, 3, 11), dt.date(2025, 3, 20))
    assert a.overlaps(b)
    assert not a.overlaps(c)


def test_day_span_prints_one_day_alone():
    day = dt.date(2025, 3, 1)
    assert str(DaySpan(day, day)) == "2025-03-01"


def test_day_span_prints_a_range():
    assert str(DaySpan(dt.date(2025, 3, 1), dt.date(2025, 3, 5))) == "2025-03-01..2025-03-05"


def test_weekend_is_saturday_and_sunday():
    assert dt.date(2025, 3, 1).weekday() in WEEKEND
    assert dt.date(2025, 3, 2).weekday() in WEEKEND
    assert dt.date(2025, 3, 3).weekday() not in WEEKEND
