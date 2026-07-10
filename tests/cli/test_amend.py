from collections.abc import Callable

from click.testing import Result

from tests.cli.test_permit import apply_one

AMEND = ("permit", "amend", "P-000001")
ON = ("--on", "2025-06-18")


def issued(stocked: Callable[..., Result]) -> Result:
    """File and issue one permit, so there is something to amend."""
    apply_one(stocked)
    result = stocked("permit", "issue", "1", "--on", "2025-06-17")
    assert result.exit_code == 0, result.output
    return result


def test_a_fresh_permit_has_not_been_amended(stocked):
    issued(stocked)
    assert "has not been amended" in stocked("permit", "amendments", "P-000001").output


def test_amending_the_destination_keeps_the_number(stocked):
    issued(stocked)
    result = stocked(
        "permit", "amend", "P-000001", "--destination", "JCT-C", "--on", "2025-06-18"
    )
    assert result.exit_code == 0, result.output
    assert "P-000001" in result.output


def test_an_amendment_says_what_moved(stocked):
    issued(stocked)
    result = stocked(
        "permit", "amend", "P-000001", "--destination", "JCT-C", "--on", "2025-06-18"
    )
    assert "route" in result.output


def test_an_amendment_says_what_it_cost(stocked):
    issued(stocked)
    result = stocked(
        "permit", "amend", "P-000001", "--destination", "JCT-C", "--on", "2025-06-18"
    )
    assert "charged" in result.output or "refund" in result.output


def test_an_amended_permit_lists_its_amendment(stocked):
    issued(stocked)
    stocked(*AMEND, "--destination", "JCT-C", *ON)
    assert "route" in stocked("permit", "amendments", "P-000001").output


def test_the_note_shows_up_in_the_listing(stocked):
    issued(stocked)
    stocked(*AMEND, "--destination", "JCT-C", "--note", "shipper moved it", *ON)
    assert "shipper moved it" in stocked("permit", "amendments", "P-000001").output


def test_amending_the_width_reads_as_a_load_change(stocked):
    issued(stocked)
    stocked(*AMEND, "--width", "13ft", *ON)
    assert "load" in stocked("permit", "amendments", "P-000001").output


def test_an_amendment_that_changes_nothing_is_refused(stocked):
    issued(stocked)
    result = stocked(*AMEND, *ON)
    assert result.exit_code != 0


def test_two_amendments_both_show_up(stocked):
    issued(stocked)
    stocked(*AMEND, "--destination", "JCT-C", *ON)
    stocked(*AMEND, "--width", "13ft", *ON)
    listing = stocked("permit", "amendments", "P-000001").output
    assert listing.count("amended") == 2


def test_amending_an_unknown_permit_fails(stocked):
    issued(stocked)
    assert stocked("permit", "amend", "P-999999", "--width", "13ft").exit_code != 0


def test_amending_a_void_permit_fails(stocked):
    issued(stocked)
    stocked("permit", "void", "P-000001", "--reason", "cancelled", "--on", "2025-06-18")
    result = stocked(*AMEND, "--width", "13ft", *ON)
    assert result.exit_code != 0


def test_moving_the_last_day_moves_the_permit(stocked):
    issued(stocked)
    stocked(*AMEND, "--last", "2025-06-22", *ON)
    assert "2025-06-22" in stocked("permit", "show", "P-000001").output


def test_a_date_only_amendment_charges_the_handling_fee(stocked):
    issued(stocked)
    stocked(*AMEND, "--last", "2025-06-22", *ON)
    assert "$35.00" in stocked("permit", "amendments", "P-000001").output


def test_the_amendment_lands_on_the_carriers_account(stocked):
    issued(stocked)
    stocked(*AMEND, "--last", "2025-06-22", *ON)
    statement = stocked("account", "statement", "VANCE").output
    assert "P-000001" in statement
    assert "$35.00" in statement
