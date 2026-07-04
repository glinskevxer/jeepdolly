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


def lodge_bond(run: Callable[..., Result], **over: str) -> Result:
    """Lodge a bond against the standard carrier, field by field overridable."""
    fields = {
        "--cover": "surety bond",
        "--insurer": "Cascade Surety",
        "--policy": "SB-4471",
        "--amount": "100000",
        "--from": "2025-01-01",
        "--to": "2025-12-31",
    }
    fields.update(over)
    flat: list[str] = []
    for name, value in fields.items():
        flat.extend([name, value])
    return run("carrier", "lodge", "VANCE", *flat)


def test_lodging_a_bond_puts_it_on_file(run):
    add_vance(run)
    result = lodge_bond(run)
    assert result.exit_code == 0, result.output
    assert "SB-4471" in result.output


def test_lodging_against_an_unknown_carrier_fails(run):
    result = lodge_bond(run)
    assert result.exit_code != 0


def test_a_lodged_bond_shows_up_in_the_paper_list(run):
    add_vance(run)
    lodge_bond(run)
    assert "SB-4471" in run("carrier", "paper", "VANCE").output


def test_the_paper_list_marks_what_is_good_that_day(run):
    add_vance(run)
    lodge_bond(run)
    assert "[good]" in run("carrier", "paper", "VANCE", "--on", "2025-06-30").output


def test_the_paper_list_marks_what_has_lapsed(run):
    add_vance(run)
    lodge_bond(run)
    assert "[not good]" in run("carrier", "paper", "VANCE", "--on", "2026-06-30").output


def test_a_carrier_with_no_paper_says_so(run):
    add_vance(run)
    assert "nothing on file" in run("carrier", "paper", "VANCE").output


def test_a_carrier_with_no_cover_is_not_clear(run):
    add_vance(run)
    result = run("carrier", "cover", "VANCE", "--on", "2025-06-30")
    assert result.exit_code != 0
    assert "no surety bond on file" in result.output


def test_a_fully_covered_carrier_is_clear(run):
    add_vance(run)
    lodge_bond(run)
    lodge_bond(run, **{"--cover": "public liability", "--policy": "PL-1", "--amount": "750000"})
    result = run("carrier", "cover", "VANCE", "--on", "2025-06-30")
    assert result.exit_code == 0, result.output
    assert "is clear for a trip permit" in result.output


def test_the_cover_check_prints_what_the_permit_needs(run):
    add_vance(run)
    lodge_bond(run)
    assert "needs surety bond" in run("carrier", "cover", "VANCE", "--on", "2025-06-30").output


def test_an_annual_asks_for_more_than_the_carrier_holds(run):
    add_vance(run)
    lodge_bond(run, **{"--amount": "50000"})
    lodge_bond(run, **{"--cover": "public liability", "--policy": "PL-1", "--amount": "750000"})
    result = run("carrier", "cover", "VANCE", "--kind", "annual", "--on", "2025-06-30")
    assert result.exit_code != 0
    assert "short of" in result.output


def test_an_escorted_move_asks_for_escort_cover(run):
    add_vance(run)
    lodge_bond(run)
    lodge_bond(run, **{"--cover": "public liability", "--policy": "PL-1", "--amount": "750000"})
    result = run("carrier", "cover", "VANCE", "--escorted", "--on", "2025-06-30")
    assert result.exit_code != 0
    assert "escort service" in result.output


def test_the_chase_list_names_a_carrier_running_out(run):
    add_vance(run)
    lodge_bond(run)
    assert "VANCE" in run("carrier", "chase", "--on", "2025-12-15").output


def test_the_chase_list_is_quiet_when_nothing_is_due(run):
    add_vance(run)
    lodge_bond(run)
    assert "nothing to chase" in run("carrier", "chase", "--on", "2025-06-30").output


def test_a_wider_chase_window_finds_more(run):
    add_vance(run)
    lodge_bond(run)
    assert "VANCE" in run("carrier", "chase", "--within", "300", "--on", "2025-06-30").output


def test_lodging_the_same_policy_twice_replaces_it(run):
    add_vance(run)
    lodge_bond(run)
    lodge_bond(run, **{"--amount": "250000"})
    assert "$250,000.00" in run("carrier", "paper", "VANCE").output


def test_a_cover_that_is_not_on_the_list_is_refused(run):
    add_vance(run)
    assert lodge_bond(run, **{"--cover": "hull"}).exit_code != 0
