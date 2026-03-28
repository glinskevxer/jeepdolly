import datetime as dt

import click
import pytest

from jeepdolly.cli.ask import (
    bytes_of,
    county_list,
    day_or_today,
    length_or,
    today,
    window_of,
)
from jeepdolly.errors import BadValueError
from jeepdolly.units.clock import Window
from jeepdolly.units.length import feet


def test_today_is_a_plain_date():
    made = today()
    assert isinstance(made, dt.date)
    assert not isinstance(made, dt.datetime)


def test_today_is_the_local_date(monkeypatch):
    assert today() == dt.datetime.now().astimezone().date()


def test_a_typed_day_is_read():
    assert day_or_today("2025-06-17") == dt.date(2025, 6, 17)


def test_nothing_typed_gives_today():
    assert day_or_today("") == today()


def test_a_bad_day_is_refused():
    with pytest.raises(BadValueError):
        day_or_today("17/06/2025")


def test_a_county_list_is_split_on_commas():
    assert county_list("Missoula, Ravalli") == {"Missoula", "Ravalli"}


def test_a_county_list_tidies_the_names():
    assert county_list(" Lewis  and   Clark ") == {"Lewis and Clark"}


def test_a_county_list_drops_the_blanks():
    assert county_list("Missoula, ,Ravalli,") == {"Missoula", "Ravalli"}


def test_an_empty_county_list_is_empty():
    assert county_list("  ") == frozenset()


def test_a_window_is_built_from_both_ends():
    assert window_of("07:00", "09:00") == Window(420, 540)


def test_no_window_is_built_from_neither_end():
    assert window_of("", "") is None


def test_half_a_window_is_refused():
    with pytest.raises(click.BadParameter):
        window_of("07:00", "")


def test_the_other_half_of_a_window_is_refused():
    with pytest.raises(click.BadParameter):
        window_of("", "09:00")


def test_a_bad_time_in_a_window_is_refused():
    with pytest.raises(BadValueError):
        window_of("half seven", "09:00")


def test_a_typed_length_is_read():
    assert int(length_or("13'6\"", feet(8))) == 162


def test_nothing_typed_gives_the_fallback():
    assert length_or("", feet(8)) == feet(8)


def test_a_small_byte_count_is_plain():
    assert bytes_of(512) == "512 B"


def test_a_kilobyte_count_says_so():
    assert bytes_of(2048) == "2.0 kB"


def test_a_megabyte_count_says_so():
    assert bytes_of(3 * 1024 * 1024) == "3.0 MB"


def test_the_boundary_between_bytes_and_kilobytes():
    assert bytes_of(1023).endswith(" B")
    assert bytes_of(1024).endswith(" kB")


def test_the_boundary_between_kilobytes_and_megabytes():
    assert bytes_of(1024 * 1024 - 1).endswith(" kB")
    assert bytes_of(1024 * 1024).endswith(" MB")
