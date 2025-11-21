from collections.abc import Callable

from click.testing import Result

from .test_permit import apply_one


def a_thaw(run: Callable[..., Result], **over: str) -> Result:
    """Put a spring thaw order on the books."""
    args = {
        "--code": "THAW-26",
        "--first": "2026-03-01",
        "--last": "2026-04-15",
        "--percent": "60",
        "--counties": "Missoula, Ravalli",
    }
    args.update(over)
    flat: list[str] = []
    for key, value in args.items():
        flat.extend([key, value])
    return run("almanac", "season", *flat)


def test_a_season_goes_on_the_books(run):
    result = a_thaw(run)
    assert result.exit_code == 0
    assert "THAW-26" in result.output
    assert "down to 60%" in result.output


def test_a_season_refuses_a_hundred_percent(run):
    assert a_thaw(run, **{"--percent": "100"}).exit_code == 1


def test_a_season_refuses_no_counties(run):
    assert a_thaw(run, **{"--counties": " "}).exit_code == 1


def test_a_season_refuses_a_repeat(run):
    a_thaw(run)
    assert a_thaw(run).exit_code == 1


def test_an_embargo_goes_on_the_books(run):
    result = run(
        "almanac",
        "embargo",
        "--code",
        "RUSH-MSO",
        "--first",
        "2026-06-01",
        "--last",
        "2026-08-31",
        "--reason",
        "peak traffic",
        "--from-time",
        "07:00",
        "--to-time",
        "09:00",
        "--counties",
        "Missoula",
    )
    assert result.exit_code == 0
    assert "07:00-09:00" in result.output


def test_a_statewide_embargo_says_so(run):
    result = run(
        "almanac",
        "embargo",
        "--code",
        "FAIR-26",
        "--first",
        "2026-08-10",
        "--last",
        "2026-08-16",
        "--reason",
        "county fair traffic",
    )
    assert "statewide" in result.output


def test_an_embargo_refuses_half_a_window(run):
    result = run(
        "almanac",
        "embargo",
        "--code",
        "RUSH-MSO",
        "--first",
        "2026-06-01",
        "--last",
        "2026-08-31",
        "--reason",
        "peak traffic",
        "--from-time",
        "07:00",
    )
    assert result.exit_code == 2


def test_the_holidays_load_for_a_year(run):
    result = run("almanac", "holidays", "2026")
    assert result.exit_code == 0
    assert "11 holiday embargoes for 2026" in result.output


def test_loading_the_holidays_twice_says_so(run):
    run("almanac", "holidays", "2026")
    assert "already on the books" in run("almanac", "holidays", "2026").output


def test_the_list_says_when_the_almanac_is_empty(run):
    assert "the almanac is empty" in run("almanac", "list").output


def test_the_list_shows_both_kinds(run):
    a_thaw(run)
    run("almanac", "holidays", "2026")
    output = run("almanac", "list").output
    assert "seasonal orders" in output
    assert "embargoes" in output


def test_on_a_day_says_what_is_in_force(run):
    a_thaw(run)
    output = run("almanac", "on", "2026-03-20", "--county", "Missoula").output
    assert "season THAW-26" in output


def test_on_a_day_in_another_county_says_nothing(run):
    a_thaw(run)
    assert (
        "nothing in force" in run("almanac", "on", "2026-03-20", "--county", "Granite").output
    )


def test_on_a_holiday_names_the_embargo(run):
    run("almanac", "holidays", "2026")
    output = run("almanac", "on", "2026-07-03", "--county", "Missoula").output
    assert "embargo" in output


def test_status_counts_the_almanac(run):
    a_thaw(run)
    run("almanac", "holidays", "2026")
    output = run("status").output
    assert "seasons 1" in output
    assert "embargoes 11" in output


def test_a_thaw_order_shows_up_in_a_quote(stocked):
    stocked(
        "almanac",
        "season",
        "--code",
        "THAW-25",
        "--first",
        "2025-06-01",
        "--last",
        "2025-06-30",
        "--percent",
        "60",
        "--counties",
        "Missoula",
    )
    apply_one(stocked)
    output = stocked("permit", "quote", "1", "--on", "2025-06-17").output
    assert "48,000 lb gross limit" in output


def test_without_the_order_the_statutory_limit_is_used(stocked):
    apply_one(stocked)
    output = stocked("permit", "quote", "1", "--on", "2025-06-17").output
    assert "48,000 lb gross limit" not in output


def test_a_thaw_order_in_another_county_does_not_bite(stocked):
    stocked(
        "almanac",
        "season",
        "--code",
        "THAW-25",
        "--first",
        "2025-06-01",
        "--last",
        "2025-06-30",
        "--percent",
        "60",
        "--counties",
        "Granite",
    )
    apply_one(stocked)
    output = stocked("permit", "quote", "1", "--on", "2025-06-17").output
    assert "48,000 lb gross limit" not in output
