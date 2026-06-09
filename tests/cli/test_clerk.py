"""The clerk at the counter reaches the journal.

``Desk`` has carried a ``clerk`` since the journal was written, and until this
was wired up nothing ever set it: every line in the journal said the office had
done something and none of them said who. That is the shape of gap a unit test
cannot see, because the layer works perfectly and nobody calls it.
"""

from collections.abc import Callable
from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from jeepdolly.cli.context import MAX_CLERK
from jeepdolly.cli.main import main
from jeepdolly.store.backup import back_up

from .test_permit import apply_one


@pytest.fixture
def signed_on(
    runner: CliRunner, tmp_path: Path, stocked_template: Path
) -> Callable[..., Result]:
    """A stocked office worked by a named clerk."""
    path = tmp_path / "office.sqlite3"
    back_up(stocked_template, path)

    def go(*args: str) -> Result:
        return runner.invoke(main, ["-f", str(path), "--clerk", "jhalloran", *args])

    return go


def test_the_status_says_who_is_at_the_counter(signed_on):
    assert "clerk jhalloran" in signed_on("status").output


def test_the_status_says_when_nobody_is_signed_on(run):
    assert "not signed on" in run("status").output


def test_the_clerk_reaches_the_journal(signed_on):
    apply_one(signed_on)
    assert "jhalloran" in signed_on("history", "show").output


def test_every_line_of_a_run_names_the_clerk(signed_on):
    apply_one(signed_on)
    signed_on("permit", "issue", "1", "--on", "2025-06-17")
    signed_on("permit", "void", "P-000001", "--reason", "cancelled", "--on", "2025-06-18")
    output = signed_on("history", "show").output
    assert output.count("jhalloran") >= 3


def test_an_unsigned_run_leaves_the_clerk_blank(stocked):
    apply_one(stocked)
    output = stocked("history", "show").output
    assert "jhalloran" not in output


def test_the_clerk_reads_the_environment(runner, office_file, monkeypatch):
    monkeypatch.setenv("JEEPDOLLY_CLERK", "dokonkwo")
    result = runner.invoke(main, ["-f", str(office_file), "status"])
    assert "clerk dokonkwo" in result.output


def test_a_clerk_name_is_tidied(runner, office_file):
    result = runner.invoke(
        main, ["-f", str(office_file), "--clerk", "  j   halloran ", "status"]
    )
    assert "clerk j halloran" in result.output


def test_a_clerk_name_that_is_too_long_is_refused(runner, office_file):
    result = runner.invoke(
        main, ["-f", str(office_file), "--clerk", "x" * (MAX_CLERK + 1), "status"]
    )
    assert result.exit_code != 0


def test_the_longest_clerk_name_is_taken(runner, office_file):
    name = "x" * MAX_CLERK
    result = runner.invoke(main, ["-f", str(office_file), "--clerk", name, "status"])
    assert result.exit_code == 0
    assert name in result.output


def test_a_review_decision_names_the_clerk_too(signed_on):
    apply_one(signed_on, **{"--kind": "superload", "--width": "17'0"})
    signed_on("review", "open", "1", "--on", "2025-06-17")
    entries = signed_on("history", "show", "--about", "E-00001").output
    assert "jhalloran" in entries
