"""The build file says what the build actually does.

A workflow is the one file in the repository nothing else reads, so nothing else
notices when it stops matching the project. These are the four things about it
that have been wrong at some point and would not have failed anything.

The checks are read out of the workflow rather than counted from the directory,
because the loop over ``check_*.py`` is a glob and a glob that matches nothing
exits zero. The build asserts a floor on how many it ran; this asserts that the
floor is not above what exists.
"""

from __future__ import annotations

import re

from jeepdolly.tools.walk import package_root, repo_root

WORKFLOW = ".github/workflows/ci.yml"


def workflow() -> str:
    """The build file, as text."""
    return (repo_root() / WORKFLOW).read_text(encoding="utf-8")


def checks_on_disk() -> list[str]:
    """Every check the loop would find."""
    return sorted(path.name for path in (package_root() / "tools").glob("check_*.py"))


def test_the_build_file_is_there():
    assert (repo_root() / WORKFLOW).exists()


def test_the_build_runs_both_interpreters():
    text = workflow()
    assert '"3.12"' in text
    assert '"3.13"' in text


def test_the_build_lints_on_both_interpreters():
    text = workflow()
    lint = text[text.index("  lint:") : text.index("  tests:")]
    assert '["3.12", "3.13"]' in lint


def test_the_build_walks_on_both_interpreters():
    text = workflow()
    walk = text[text.index("  walk_on:") :]
    assert '["3.12", "3.13"]' in walk


def test_the_check_floor_is_not_above_what_exists():
    hit = re.search(r'test "\$ran" -ge (\d+)', workflow())
    assert hit is not None
    assert int(hit.group(1)) <= len(checks_on_disk())


def test_the_check_floor_is_worth_having():
    hit = re.search(r'test "\$ran" -ge (\d+)', workflow())
    assert hit is not None
    assert int(hit.group(1)) >= len(checks_on_disk()) - 2


def test_there_are_more_checks_than_the_floor_was_written_for():
    assert len(checks_on_disk()) >= 14


def test_every_install_in_the_build_uses_the_constraints():
    for line in workflow().splitlines():
        if "pip install" in line:
            assert "-c constraints.txt" in line, line


def test_the_build_gates_on_coverage():
    text = workflow()
    assert "coverage_gate.py" in text
    assert "--floor 96" in text


def test_the_build_checks_the_generated_documents():
    assert "check_docs.py" in workflow()


def test_the_build_builds_from_a_clean_export():
    assert "git archive HEAD" in workflow()


def test_the_build_asserts_the_walk_said_something():
    assert 'test "$lines" -ge 400' in workflow()


def test_the_build_names_every_job_it_runs():
    text = workflow()
    for job in ("lint:", "tests:", "coverage:", "installed:", "package:", "walk_on:"):
        assert f"  {job}" in text


def test_the_lint_job_installs_the_tools_the_checks_import():
    from jeepdolly.tools.check_pins import imported

    text = workflow()
    lint = text[text.index("  lint:") : text.index("  tests:")]
    installs = "\n".join(line for line in lint.splitlines() if "pip install" in line)
    for name in sorted(imported()):
        assert name in installs, name


def test_the_lint_job_installs_coverage():
    text = workflow()
    lint = text[text.index("  lint:") : text.index("  tests:")]
    assert "coverage" in lint


def test_every_job_that_type_checks_also_installs_the_package():
    text = workflow()
    lint = text[text.index("  lint:") : text.index("  tests:")]
    assert "pip install -e ." in lint
