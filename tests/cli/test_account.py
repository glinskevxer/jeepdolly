from collections.abc import Callable

import pytest
from click.testing import Result


@pytest.fixture
def with_carrier(run: Callable[..., Result]) -> Callable[..., Result]:
    """An office file with two carriers on it."""
    run(
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
    run("carrier", "add", "--code", "OTHER", "--name", "Other", "--usdot", "2", "--state", "ID")
    return run


def test_deposit_raises_the_balance(with_carrier):
    result = with_carrier(
        "account", "deposit", "VANCE", "--amount", "1,000.00", "--on", "2025-07-01"
    )
    assert result.exit_code == 0
    assert "balance $1,000.00" in result.output


def test_deposit_refuses_a_carrier_that_is_not_there(with_carrier):
    result = with_carrier("account", "deposit", "NOBODY", "--amount", "100.00")
    assert result.exit_code == 1


def test_deposit_refuses_a_bad_amount(with_carrier):
    result = with_carrier("account", "deposit", "VANCE", "--amount", "lots")
    assert result.exit_code == 1


def test_charge_needs_a_permit(with_carrier):
    result = with_carrier("account", "charge", "VANCE", "--permit", "P-000001")
    assert result.exit_code == 1


def test_charge_with_an_override_amount(with_carrier):
    with_carrier("account", "deposit", "VANCE", "--amount", "1,000.00", "--on", "2025-07-01")
    result = with_carrier(
        "account",
        "charge",
        "VANCE",
        "--permit",
        "P-000001",
        "--amount",
        "97.52",
        "--on",
        "2025-07-02",
    )
    assert result.exit_code == 0
    assert "balance $902.48" in result.output


def test_charge_past_the_floor_is_refused(with_carrier):
    result = with_carrier(
        "account", "charge", "VANCE", "--permit", "P-000001", "--amount", "600.00"
    )
    assert result.exit_code == 1


def test_the_floor_may_be_widened(with_carrier):
    with_carrier("account", "floor", "VANCE", "--amount", "-2000.00")
    result = with_carrier(
        "account", "charge", "VANCE", "--permit", "P-000001", "--amount", "600.00"
    )
    assert result.exit_code == 0


def test_floor_prints_what_it_set(with_carrier):
    result = with_carrier("account", "floor", "VANCE", "--amount", "-2000.00")
    assert "-$2,000.00" in result.output


def test_statement_says_when_there_is_nothing(with_carrier):
    assert "no entries" in with_carrier("account", "statement", "VANCE").output


def test_statement_lists_the_entries(with_carrier):
    with_carrier("account", "deposit", "VANCE", "--amount", "1,000.00", "--on", "2025-07-01")
    output = with_carrier("account", "statement", "VANCE").output
    assert "deposit" in output
    assert "$1,000.00" in output


def test_statement_runs_a_balance(with_carrier):
    with_carrier("account", "deposit", "VANCE", "--amount", "1,000.00", "--on", "2025-07-01")
    with_carrier(
        "account",
        "charge",
        "VANCE",
        "--permit",
        "P-000001",
        "--amount",
        "100.00",
        "--on",
        "2025-07-02",
    )
    output = with_carrier("account", "statement", "VANCE").output
    assert "$900.00" in output


def test_statement_shows_the_headroom(with_carrier):
    assert "headroom" in with_carrier("account", "statement", "VANCE").output


def test_statement_filters_by_span(with_carrier):
    with_carrier("account", "deposit", "VANCE", "--amount", "1,000.00", "--on", "2025-07-01")
    output = with_carrier(
        "account", "statement", "VANCE", "--first", "2025-08-01", "--last", "2025-08-31"
    ).output
    assert "no entries" in output


def test_owing_says_when_nobody_owes(with_carrier):
    assert "nobody owes anything" in with_carrier("account", "owing").output


def test_owing_lists_the_overdrawn(with_carrier):
    with_carrier("account", "charge", "VANCE", "--permit", "P-000001", "--amount", "100.00")
    assert "VANCE" in with_carrier("account", "owing").output
