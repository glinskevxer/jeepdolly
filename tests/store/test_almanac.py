import datetime as dt

import pytest

from jeepdolly.almanac.embargo import Embargo
from jeepdolly.almanac.season import Season
from jeepdolly.errors import ConflictError, NotFoundError
from jeepdolly.limits.statute import STATE_ROUTE
from jeepdolly.store.almanac import AlmanacStore
from jeepdolly.units.clock import DaySpan, Window

THAW = DaySpan(dt.date(2025, 3, 1), dt.date(2025, 4, 15))
SUMMER = DaySpan(dt.date(2025, 6, 1), dt.date(2025, 8, 31))


@pytest.fixture
def store(office):
    """An almanac store over a migrated office."""
    return AlmanacStore(office)


def a_season(**over: object) -> Season:
    kw: dict[str, object] = {
        "code": "THAW-25",
        "span": THAW,
        "percent": 60,
        "counties": frozenset({"Missoula", "Ravalli"}),
        "note": "spring thaw",
    }
    kw.update(over)
    return Season(**kw)  # type: ignore[arg-type]


def a_rush_hour(**over: object) -> Embargo:
    kw: dict[str, object] = {
        "code": "RUSH-MSO",
        "span": SUMMER,
        "reason": "peak traffic",
        "window": Window(420, 540),
        "counties": frozenset({"Missoula"}),
    }
    kw.update(over)
    return Embargo(**kw)  # type: ignore[arg-type]


def test_a_new_almanac_is_empty(store):
    assert store.counts() == (0, 0)


def test_a_seasonal_order_round_trips(store):
    store.add_season(a_season())
    read = store.get_season("THAW-25")
    assert read.percent == 60
    assert read.counties == {"Missoula", "Ravalli"}


def test_the_note_on_a_season_round_trips(store):
    store.add_season(a_season())
    assert store.get_season("THAW-25").note == "spring thaw"


def test_add_season_refuses_a_repeat(store):
    store.add_season(a_season())
    with pytest.raises(ConflictError):
        store.add_season(a_season())


def test_get_season_raises_when_it_is_not_there(store):
    with pytest.raises(NotFoundError):
        store.get_season("THAW-25")


def test_find_season_returns_none_when_it_is_not_there(store):
    assert store.find_season("THAW-25") is None


def test_seasons_come_out_in_code_order(store):
    store.add_season(a_season(code="ZED-25"))
    store.add_season(a_season())
    assert [str(s.code) for s in store.seasons()] == ["THAW-25", "ZED-25"]


def test_the_season_book_applies_the_order(store):
    store.add_season(a_season())
    got = store.season_book().statute_on(STATE_ROUTE, dt.date(2025, 3, 20), "Missoula")
    assert int(got.gross) == 48000


def test_removing_a_season_takes_its_counties(store, office):
    store.add_season(a_season())
    store.remove_season("THAW-25")
    assert office.execute("SELECT count(*) FROM season_county").fetchone()[0] == 0


def test_remove_season_raises_when_it_is_not_there(store):
    with pytest.raises(NotFoundError):
        store.remove_season("THAW-25")


def test_the_table_refuses_a_hundred_percent(store, office):
    with pytest.raises(Exception, match="CHECK"):
        office.execute(
            "INSERT INTO season (code, first_day, last_day, percent)"
            " VALUES ('X', '2025-01-01', '2025-02-01', 100)"
        )


def test_an_embargo_round_trips(store):
    store.add_embargo(a_rush_hour())
    read = store.get_embargo("RUSH-MSO")
    assert read.window == Window(420, 540)
    assert read.counties == {"Missoula"}


def test_a_statewide_embargo_reads_back_statewide(store):
    store.add_embargo(
        Embargo(code="JUL4-25", span=SUMMER, reason="holiday")  # type: ignore[arg-type]
    )
    assert store.get_embargo("JUL4-25").statewide


def test_an_all_day_embargo_reads_back_with_no_window(store):
    store.add_embargo(
        Embargo(code="JUL4-25", span=SUMMER, reason="holiday")  # type: ignore[arg-type]
    )
    assert store.get_embargo("JUL4-25").window is None


def test_a_wrapping_window_round_trips(store):
    store.add_embargo(a_rush_hour(window=Window(1260, 360)))
    assert store.get_embargo("RUSH-MSO").window == Window(1260, 360)


def test_the_weekends_only_flag_round_trips(store):
    store.add_embargo(a_rush_hour(weekends_only=True))
    assert store.get_embargo("RUSH-MSO").weekends_only is True


def test_add_embargo_refuses_a_repeat(store):
    store.add_embargo(a_rush_hour())
    with pytest.raises(ConflictError):
        store.add_embargo(a_rush_hour())


def test_get_embargo_raises_when_it_is_not_there(store):
    with pytest.raises(NotFoundError):
        store.get_embargo("RUSH-MSO")


def test_the_embargo_book_blocks_the_window(store):
    store.add_embargo(a_rush_hour())
    book = store.embargo_book()
    assert not book.free(dt.date(2025, 6, 11), 450, "Missoula")
    assert book.free(dt.date(2025, 6, 11), 600, "Missoula")


def test_removing_an_embargo_takes_its_counties(store, office):
    store.add_embargo(a_rush_hour())
    store.remove_embargo("RUSH-MSO")
    assert office.execute("SELECT count(*) FROM embargo_county").fetchone()[0] == 0


def test_remove_embargo_raises_when_it_is_not_there(store):
    with pytest.raises(NotFoundError):
        store.remove_embargo("RUSH-MSO")


def test_the_table_refuses_half_a_window(store, office):
    with pytest.raises(Exception, match="CHECK"):
        office.execute(
            "INSERT INTO embargo (code, first_day, last_day, reason, window_start)"
            " VALUES ('X', '2025-01-01', '2025-02-01', 'why', 420)"
        )


def test_loading_a_year_writes_eleven_holidays(store):
    assert len(store.load_holidays(2025)) == 11
    assert store.counts()[1] == 11


def test_loading_the_same_year_twice_writes_nothing_more(store):
    store.load_holidays(2025)
    assert store.load_holidays(2025) == []
    assert store.counts()[1] == 11


def test_two_years_of_holidays_both_load(store):
    store.load_holidays(2025)
    store.load_holidays(2026)
    assert store.counts()[1] == 22


def test_a_loaded_holiday_blocks_movement(store):
    store.load_holidays(2025)
    assert not store.embargo_book().free(dt.date(2025, 7, 4), 600, "Missoula")


def test_counts_reports_both_kinds(store):
    store.add_season(a_season())
    store.add_embargo(a_rush_hour())
    assert store.counts() == (1, 1)


def test_the_office_hands_out_an_almanac_store(office):
    from jeepdolly.store.office import Office

    assert isinstance(Office(office).almanac, AlmanacStore)
