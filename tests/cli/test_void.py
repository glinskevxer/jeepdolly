from collections.abc import Callable

from click.testing import Result

from tests.cli.test_permit import apply_one

ON = ("--on", "2025-06-17")


def issued(stocked: Callable[..., Result]) -> Result:
    """File and issue one permit, so there is something to pull."""
    apply_one(stocked)
    result = stocked("permit", "issue", "1", "--on", "2025-06-17")
    assert result.exit_code == 0, result.output
    return result


def test_pulling_a_permit_names_the_cause(stocked):
    issued(stocked)
    result = stocked("permit", "void", "P-000001", "--cause", "carrier cancelled", *ON)
    assert result.exit_code == 0, result.output
    assert "carrier cancelled" in result.output


def test_pulling_a_permit_says_what_went_back(stocked):
    issued(stocked)
    result = stocked("permit", "void", "P-000001", "--cause", "office error", *ON)
    assert "refunded" in result.output


def test_an_office_error_gives_more_back_than_a_cancellation(stocked):
    issued(stocked)
    full = stocked("permit", "void", "P-000001", "--cause", "office error", *ON).output
    assert "$97.58" in full


def test_a_cancellation_keeps_the_writing_fee(stocked):
    issued(stocked)
    part = stocked("permit", "void", "P-000001", "--cause", "carrier cancelled", *ON).output
    assert "$72.58" in part


def test_an_undeclared_load_gives_nothing_back(stocked):
    issued(stocked)
    result = stocked(
        "permit",
        "void",
        "P-000001",
        "--cause",
        "load was not as declared",
        "--detail",
        "steel",
        *ON,
    )
    assert "$0.00" in result.output


def test_an_at_fault_cause_says_the_carrier_is_blocked(stocked):
    issued(stocked)
    result = stocked(
        "permit",
        "void",
        "P-000001",
        "--cause",
        "load was not as declared",
        "--detail",
        "steel",
        *ON,
    )
    assert "cannot be issued anything" in result.output


def test_an_at_fault_cause_with_no_detail_is_refused(stocked):
    issued(stocked)
    result = stocked("permit", "void", "P-000001", "--cause", "move was unsafe", *ON)
    assert result.exit_code != 0


def test_a_blocked_carrier_cannot_be_issued_anything(stocked):
    issued(stocked)
    stocked(
        "permit",
        "void",
        "P-000001",
        "--cause",
        "load was not as declared",
        "--detail",
        "steel",
        *ON,
    )
    apply_one(stocked)
    result = stocked("permit", "issue", "2", "--on", "2025-06-17")
    assert result.exit_code != 0
    assert "blocked" in result.output


def test_a_cancellation_leaves_the_carrier_able_to_apply(stocked):
    issued(stocked)
    stocked("permit", "void", "P-000001", "--cause", "carrier cancelled", *ON)
    apply_one(stocked)
    assert stocked("permit", "issue", "2", "--on", "2025-06-17").exit_code == 0


def test_a_cause_that_is_not_on_the_list_is_refused(stocked):
    issued(stocked)
    assert stocked("permit", "void", "P-000001", "--cause", "felt like it", *ON).exit_code != 0


def test_pulling_a_permit_twice_is_refused(stocked):
    issued(stocked)
    stocked("permit", "void", "P-000001", "--cause", "carrier cancelled", *ON)
    result = stocked("permit", "void", "P-000001", "--cause", "carrier cancelled", *ON)
    assert result.exit_code != 0
