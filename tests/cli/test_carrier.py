from collections.abc import Callable

from click.testing import Result


def add_vance(run: Callable[..., Result]) -> Result:
    """Put the standard carrier on file through the command line."""
    return run(
        "carrier",
        "add",
        "--code",
        "VANCE",
        "--name",
        "Vance Heavy Haul",
        "--usdot",
        "1184062",
        "--state",
        "MT",
    )


def test_add_puts_a_carrier_on_file(run):
    result = add_vance(run)
    assert result.exit_code == 0
    assert "VANCE" in result.output


def test_an_added_carrier_is_kept_on_file(run):
    add_vance(run)
    assert "carriers 1" in run("status").output


def test_add_refuses_a_duplicate(run):
    add_vance(run)
    result = add_vance(run)
    assert result.exit_code == 1
    assert "already exists" in result.output


def test_add_refuses_a_bad_state(run):
    result = run(
        "carrier", "add", "--code", "X1", "--name", "X", "--usdot", "1", "--state", "ZZ"
    )
    assert result.exit_code == 1
    assert "home state" in result.output


def test_add_refuses_a_bad_code(run):
    result = run(
        "carrier", "add", "--code", "!", "--name", "X", "--usdot", "1", "--state", "MT"
    )
    assert result.exit_code == 1


def test_list_says_when_there_is_nothing(run):
    assert "no carriers on file" in run("carrier", "list").output


def test_list_shows_the_carrier(run):
    add_vance(run)
    assert "Vance Heavy Haul" in run("carrier", "list").output


def test_list_hides_the_retired(run):
    add_vance(run)
    run("carrier", "retire", "VANCE")
    assert "no carriers on file" in run("carrier", "list").output


def test_list_all_shows_the_retired(run):
    add_vance(run)
    run("carrier", "retire", "VANCE")
    assert "inactive" in run("carrier", "list", "--all").output


def test_show_prints_the_home_state(run):
    add_vance(run)
    assert "home state MT" in run("carrier", "show", "VANCE").output


def test_show_says_it_is_issuable(run):
    add_vance(run)
    assert "issuable" in run("carrier", "show", "VANCE").output


def test_show_raises_on_a_carrier_that_is_not_there(run):
    result = run("carrier", "show", "NOBODY")
    assert result.exit_code == 1
    assert "no carrier" in result.output


def test_retire_then_show_says_not_issuable(run):
    add_vance(run)
    run("carrier", "retire", "VANCE")
    assert "not issuable" in run("carrier", "show", "VANCE").output


def test_restore_puts_it_back(run):
    add_vance(run)
    run("carrier", "retire", "VANCE")
    run("carrier", "restore", "VANCE")
    assert "issuable" in run("carrier", "show", "VANCE").output


def test_retire_on_a_carrier_that_is_not_there(run):
    result = run("carrier", "retire", "NOBODY")
    assert result.exit_code == 1


def test_search_finds_by_name(run):
    add_vance(run)
    assert "VANCE" in run("carrier", "search", "heavy").output


def test_search_says_when_nothing_matches(run):
    add_vance(run)
    assert "nothing found" in run("carrier", "search", "zzz").output
