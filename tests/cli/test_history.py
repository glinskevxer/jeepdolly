from collections.abc import Callable

import pytest
from click.testing import Result

from .test_permit import apply_one


@pytest.fixture
def worked(stocked: Callable[..., Result]) -> Callable[..., Result]:
    """A stocked office that has issued and voided one permit."""
    apply_one(stocked)
    stocked("permit", "issue", "1", "--on", "2025-06-17")
    stocked("permit", "void", "P-000001", "--cause", "carrier cancelled", "--on", "2025-06-18")
    return stocked


def test_the_journal_says_when_it_is_empty(run):
    assert "nothing in the journal" in run("history", "show").output


def test_the_journal_lists_what_happened(worked):
    output = worked("history", "show").output
    assert "office journal" in output
    assert "filed" in output
    assert "issued" in output
    assert "voided" in output


def test_the_journal_narrows_to_one_subject(worked):
    output = worked("history", "show", "--about", "P-000001").output
    assert "issued" in output
    assert "filed" not in output


def test_the_journal_narrows_to_one_kind(worked):
    output = worked("history", "show", "--kind", "issued").output
    assert "issued" in output
    assert "voided" not in output


def test_the_journal_narrows_to_a_span(worked):
    output = worked("history", "show", "--first", "2025-06-18", "--last", "2025-06-18").output
    assert "voided" in output
    assert "filed" not in output


def test_the_journal_says_when_a_subject_has_nothing(worked):
    assert "nothing in the journal" in worked("history", "show", "--about", "P-000099").output


def test_an_unknown_kind_is_refused(worked):
    assert worked("history", "show", "--kind", "grumbled").exit_code != 0


def test_the_kinds_command_lists_them_all(run):
    output = run("history", "kinds").output
    for word in ("filed", "issued", "voided", "refunded", "referred", "approved"):
        assert word in output


def test_the_journal_shows_the_detail(worked):
    assert "carrier cancelled" in worked("history", "show", "--about", "P-000001").output


def test_the_journal_numbers_its_entries(worked):
    output = worked("history", "show").output
    assert " 1 " in output or output.strip().splitlines()[2].strip().startswith("1")
