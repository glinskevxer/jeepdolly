"""Every check has to be seen failing, not only passing.

A check that has only ever returned an empty list is a check nobody has watched
work. These feed each one a finding it did not produce itself and assert that it
reports the finding and exits non zero, which is the half of the behaviour the
build actually depends on.
"""

from collections.abc import Callable

import pytest

from jeepdolly.tools import (
    check_boundaries,
    check_commands,
    check_dataclasses,
    check_docstrings,
    check_exports,
    check_fixtures,
    check_layers,
    check_links,
    check_naming,
    check_sql,
    check_todo,
)

CHECKS = [
    check_boundaries,
    check_commands,
    check_dataclasses,
    check_docstrings,
    check_exports,
    check_fixtures,
    check_layers,
    check_links,
    check_naming,
    check_sql,
    check_todo,
]

NAMES = [module.__name__.rsplit(".", 1)[-1] for module in CHECKS]


@pytest.mark.parametrize(("module", "name"), zip(CHECKS, NAMES, strict=True))
def test_every_check_passes_over_the_package(module, name):
    assert module.main() == 0, name


@pytest.mark.parametrize(("module", "name"), zip(CHECKS, NAMES, strict=True))
def test_every_check_reports_what_it_finds(module, name, monkeypatch, capsys):
    def one_problem() -> list[str]:
        """A single made up finding."""
        return ["a made up problem"]

    monkeypatch.setattr(module, "problems", one_problem)
    assert module.main() == 1, name
    out = capsys.readouterr().out
    assert "a made up problem" in out
    assert name in out


@pytest.mark.parametrize(("module", "name"), zip(CHECKS, NAMES, strict=True))
def test_every_check_counts_what_it_found(module, name, monkeypatch, capsys):
    def three_problems() -> list[str]:
        """Three made up findings."""
        return ["first", "second", "third"]

    monkeypatch.setattr(module, "problems", three_problems)
    assert module.main() == 1
    assert "3" in capsys.readouterr().out


def test_every_check_module_has_a_problems_function():
    for module in CHECKS:
        finder: Callable[[], list[str]] = module.problems
        assert callable(finder)


def test_every_check_module_has_a_main():
    for module in CHECKS:
        assert callable(module.main)


def test_the_check_list_holds_every_check_in_the_package():
    from jeepdolly.tools.walk import package_root

    on_disk = {
        path.stem
        for path in (package_root() / "tools").glob("check_*.py")
        if path.stem not in {"check_migrations", "check_docs"}
    }
    assert on_disk == set(NAMES)
