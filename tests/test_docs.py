"""The design document keeps up with what it describes.

Three of its claims are countable, so they are counted. A document that says
there are twelve checks when there are eighteen is worse than one that does not
say, because a reader believes the number.
"""

from __future__ import annotations

import re

from jeepdolly.tools.check_links import DESIGN, referenced
from jeepdolly.tools.walk import package_root, repo_root

WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}


def design() -> str:
    """The design document, as text."""
    return (repo_root() / DESIGN).read_text(encoding="utf-8")


def checks_on_disk() -> list[str]:
    """Every check module in the package."""
    return sorted(path.stem for path in (package_root() / "tools").glob("check_*.py"))


def test_the_document_is_there():
    assert (repo_root() / DESIGN).exists()


def test_the_document_counts_the_checks_correctly():
    hit = re.search(r"^(\w+) of them, run by the build", design(), re.MULTILINE)
    assert hit is not None
    assert WORDS[hit.group(1).lower()] == len(checks_on_disk())


def test_the_document_names_every_check():
    text = design()
    for name in checks_on_disk():
        assert f"`{name}`" in text, name


def test_the_document_names_no_check_that_is_gone():
    named = set(re.findall(r"`(check_\w+)`", design()))
    assert named <= set(checks_on_disk())


def test_the_layer_table_names_every_package():
    text = design()
    for path in package_root().iterdir():
        if (path / "__init__.py").exists():
            assert path.name in text, path.name


def test_the_document_points_at_modules_that_exist():
    assert referenced(design())


def test_the_document_names_the_two_suites_it_claims():
    text = design()
    assert "tests/tools/test_check_failures" in text
    assert "tests/test_season.py" in text
    assert (repo_root() / "tests" / "test_season.py").exists()
    assert (repo_root() / "tests" / "tools" / "test_check_failures.py").exists()


def test_the_document_names_the_walk_script():
    assert "scripts/walk.sh" in design()
    assert (repo_root() / "scripts" / "walk.sh").exists()


def test_every_generated_document_is_beside_the_design():
    docs = repo_root() / "docs"
    names = {path.name for path in docs.glob("*.md")}
    assert names == {"design.md", "commands.md", "schema.md", "glossary.md"}
