from collections.abc import Callable

from click.testing import Result


def apply_one(run: Callable[..., Result], **over: str) -> Result:
    """File one ordinary transformer application."""
    args = {
        "--carrier": "VANCE",
        "--rig": "R-00001",
        "--description": "step-up transformer",
        "--weight": "148,000",
        "--width": "12'6\"",
        "--height": "14'2\"",
        "--length": "48'",
        "--first": "2025-06-18",
        "--last": "2025-06-20",
        "--origin": "JCT-A",
        "--destination": "JCT-D",
        "--filed": "2025-06-16",
    }
    args.update(over)
    flat: list[str] = []
    for key, value in args.items():
        flat.extend([key, value])
    return run("permit", "apply", *flat)


def test_apply_takes_the_application(stocked):
    result = apply_one(stocked)
    assert result.exit_code == 0
    assert "application 1" in result.output


def test_apply_refuses_a_carrier_that_is_not_there(stocked):
    result = apply_one(stocked, **{"--carrier": "NOBODY"})
    assert result.exit_code == 1


def test_apply_refuses_a_rig_that_is_not_there(stocked):
    result = apply_one(stocked, **{"--rig": "R-00099"})
    assert result.exit_code == 1


def test_apply_refuses_a_backwards_span(stocked):
    result = apply_one(stocked, **{"--first": "2025-06-20", "--last": "2025-06-18"})
    assert result.exit_code == 1


def test_quote_prices_without_issuing(stocked):
    apply_one(stocked)
    result = stocked("permit", "quote", "1", "--on", "2025-06-17")
    assert result.exit_code == 0
    assert "outcome issue" in result.output
    assert "total" in result.output
    assert "permits 0" in stocked("status").output


def test_quote_prints_the_route(stocked):
    apply_one(stocked)
    result = stocked("permit", "quote", "1", "--on", "2025-06-17")
    assert "SEG-AB SEG-BD" in result.output


def test_quote_prints_the_escorts(stocked):
    apply_one(stocked)
    assert "escort rear" in stocked("permit", "quote", "1", "--on", "2025-06-17").output


def test_quote_on_a_blocked_load_says_so(stocked):
    apply_one(stocked, **{"--height": "18'"})
    result = stocked("permit", "quote", "1", "--on", "2025-06-17")
    assert "not priced" in result.output
    assert "findings" in result.output


def test_issue_writes_the_permit(stocked):
    apply_one(stocked)
    result = stocked("permit", "issue", "1", "--on", "2025-06-17")
    assert result.exit_code == 0
    assert "P-000001 issued" in result.output


def test_issue_refuses_a_blocked_load(stocked):
    apply_one(stocked, **{"--height": "18'"})
    result = stocked("permit", "issue", "1", "--on", "2025-06-17")
    assert result.exit_code == 1


def test_show_prints_the_permit(stocked):
    apply_one(stocked)
    stocked("permit", "issue", "1", "--on", "2025-06-17")
    result = stocked("permit", "show", "P-000001")
    assert "carrier VANCE" in result.output
    assert "fee" in result.output


def test_show_raises_on_a_permit_that_is_not_there(stocked):
    assert stocked("permit", "show", "P-000099").exit_code == 1


def test_void_marks_it_void(stocked):
    apply_one(stocked)
    stocked("permit", "issue", "1", "--on", "2025-06-17")
    result = stocked(
        "permit", "void", "P-000001", "--reason", "cancelled", "--on", "2025-06-17"
    )
    assert "void: cancelled" in result.output


def test_void_needs_a_reason(stocked):
    apply_one(stocked)
    stocked("permit", "issue", "1", "--on", "2025-06-17")
    assert stocked("permit", "void", "P-000001").exit_code != 0


def test_extend_moves_the_last_day(stocked):
    apply_one(stocked)
    stocked("permit", "issue", "1", "--on", "2025-06-17")
    result = stocked("permit", "extend", "P-000001", "--last", "2025-06-22")
    assert "good to 2025-06-22" in result.output


def test_extend_refuses_too_far(stocked):
    apply_one(stocked)
    stocked("permit", "issue", "1", "--on", "2025-06-17")
    assert stocked("permit", "extend", "P-000001", "--last", "2025-07-30").exit_code == 1


def test_list_says_when_there_is_nothing(stocked):
    assert "no permits" in stocked("permit", "list").output


def test_list_prints_the_permit(stocked):
    apply_one(stocked)
    stocked("permit", "issue", "1", "--on", "2025-06-17")
    assert "P-000001" in stocked("permit", "list").output


def test_list_filters_by_carrier(stocked):
    apply_one(stocked)
    stocked("permit", "issue", "1", "--on", "2025-06-17")
    assert "P-000001" in stocked("permit", "list", "--carrier", "VANCE").output


def test_list_filters_by_day(stocked):
    apply_one(stocked)
    stocked("permit", "issue", "1", "--on", "2025-06-17")
    assert "no permits" in stocked("permit", "list", "--on", "2025-07-01").output


def test_status_counts_the_applications(stocked):
    apply_one(stocked)
    assert "applications 1" in stocked("status").output


def test_a_divisible_load_is_blocked_at_quote(stocked):
    stocked(
        "permit",
        "apply",
        "--carrier",
        "VANCE",
        "--rig",
        "R-00001",
        "--description",
        "washed gravel",
        "--weight",
        "148,000",
        "--width",
        "8'6\"",
        "--height",
        "12'",
        "--length",
        "40'",
        "--first",
        "2025-06-18",
        "--last",
        "2025-06-20",
        "--origin",
        "JCT-A",
        "--destination",
        "JCT-D",
        "--filed",
        "2025-06-16",
        "--divisible",
    )
    result = stocked("permit", "quote", "1", "--on", "2025-06-17")
    assert "outcome refuse" in result.output
    assert "divisible" in result.output
