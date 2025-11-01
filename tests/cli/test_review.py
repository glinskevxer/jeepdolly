from collections.abc import Callable

import pytest
from click.testing import Result

from .test_permit import apply_one


def apply_superload(stocked: Callable[..., Result]) -> Result:
    """File an application wide enough to need an engineer."""
    return apply_one(stocked, **{"--kind": "superload", "--width": "17'0"})


@pytest.fixture
def referred(stocked: Callable[..., Result]) -> Callable[..., Result]:
    """A stocked office with one superload on the engineer's list."""
    apply_superload(stocked)
    stocked("review", "open", "1", "--on", "2025-06-17")
    return stocked


def test_open_puts_it_on_the_list(stocked):
    apply_superload(stocked)
    result = stocked("review", "open", "1", "--on", "2025-06-17")
    assert result.exit_code == 0
    assert "E-00001" in result.output


def test_open_refuses_an_application_a_clerk_could_write(stocked):
    apply_one(stocked)
    result = stocked("review", "open", "1", "--on", "2025-06-17")
    assert result.exit_code == 1


def test_the_list_shows_the_open_review(referred):
    output = referred("review", "list").output
    assert "E-00001" in output
    assert "open" in output


def test_the_list_says_when_there_is_nothing(stocked):
    assert "nothing on the list" in stocked("review", "list").output


def test_approving_records_the_engineer(referred):
    result = referred(
        "review", "approve", "E-00001", "--engineer", "R Halloran", "--on", "2025-06-18"
    )
    assert result.exit_code == 0
    assert "R Halloran" in result.output


def test_approving_prints_the_conditions(referred):
    result = referred(
        "review",
        "approve",
        "E-00001",
        "--engineer",
        "R Halloran",
        "--on",
        "2025-06-18",
        "--condition",
        "walking pace over the bridge",
    )
    assert "condition: walking pace over the bridge" in result.output


def test_an_approved_review_leaves_the_open_list(referred):
    referred("review", "approve", "E-00001", "--engineer", "R Halloran", "--on", "2025-06-18")
    assert "nothing on the list" in referred("review", "list").output


def test_a_closed_review_is_still_listed_with_all(referred):
    referred("review", "approve", "E-00001", "--engineer", "R Halloran", "--on", "2025-06-18")
    assert "approved" in referred("review", "list", "--all").output


def test_refusing_records_the_reason(referred):
    result = referred(
        "review",
        "refuse",
        "E-00001",
        "--engineer",
        "R Halloran",
        "--note",
        "the bridge will not take it",
        "--on",
        "2025-06-18",
    )
    assert "because the bridge will not take it" in result.output


def test_a_permit_issues_after_the_approval(referred):
    referred(
        "review",
        "approve",
        "E-00001",
        "--engineer",
        "R Halloran",
        "--on",
        "2025-06-18",
        "--condition",
        "walking pace over the bridge",
    )
    result = referred("permit", "issue", "1", "--on", "2025-06-18")
    assert result.exit_code == 0
    assert "P-000001 issued" in result.output


def test_the_condition_is_printed_on_the_permit(referred):
    referred(
        "review",
        "approve",
        "E-00001",
        "--engineer",
        "R Halloran",
        "--on",
        "2025-06-18",
        "--condition",
        "walking pace over the bridge",
    )
    referred("permit", "issue", "1", "--on", "2025-06-18")
    assert "walking pace over the bridge" in referred("report", "permit", "P-000001").output


def test_a_permit_does_not_issue_after_a_refusal(referred):
    referred(
        "review",
        "refuse",
        "E-00001",
        "--engineer",
        "R Halloran",
        "--note",
        "no",
        "--on",
        "2025-06-18",
    )
    assert referred("permit", "issue", "1", "--on", "2025-06-18").exit_code == 1


def test_approving_a_review_that_is_not_there_fails(stocked):
    assert stocked("review", "approve", "E-00099", "--engineer", "R H").exit_code == 1


def test_approving_twice_is_refused(referred):
    referred("review", "approve", "E-00001", "--engineer", "R Halloran", "--on", "2025-06-18")
    result = referred(
        "review", "approve", "E-00001", "--engineer", "R Halloran", "--on", "2025-06-19"
    )
    assert result.exit_code == 1
