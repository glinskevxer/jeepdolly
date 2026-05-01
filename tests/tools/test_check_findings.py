"""Feed each check a broken tree and watch it name what is wrong.

``test_check_failures`` proves each check reports a finding it was handed. This
proves each one *produces* the finding in the first place, which is the half that
actually depends on the code. Every one of these plants a defect of the exact
shape the check exists for, in a temporary tree, and asserts the check names it.

The defects are planted the way the repository would produce them: a real file
with a real mistake in it, not a stubbed return value.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from jeepdolly.tools import (
    check_dataclasses,
    check_docstrings,
    check_exports,
    check_naming,
    check_sql,
    check_todo,
)


def named(path: Path) -> str:
    """Every planted file reports the same module name."""
    assert path.suffix == ".py"
    return "jeepdolly.planted"


def a_tree(tmp_path: Path, name: str, text: str) -> list[Path]:
    """One source file in a temporary tree, as the walker would hand it over."""
    made = tmp_path / name
    made.write_text(text, encoding="utf-8")
    return [made]


@pytest.fixture
def planted(monkeypatch, tmp_path):
    """Point a check's file walker at a temporary tree."""

    def go(module, text: str, name: str = "planted.py", which: str = "source_files"):
        files = a_tree(tmp_path, name, text)
        monkeypatch.setattr(module, which, lambda: files)
        monkeypatch.setattr(module, "module_of", named, raising=False)
        return module.problems()

    return go


def test_an_undocumented_function_is_named(planted):
    found = planted(check_docstrings, '"""A module."""\n\n\ndef go():\n    return 1\n')
    assert any("no docstring" in line for line in found)


def test_a_module_with_no_docstring_is_named(planted):
    found = planted(check_docstrings, 'def go():\n    """Do the thing here."""\n')
    assert any("the module has no docstring" in line for line in found)


def test_a_thin_docstring_is_named(planted):
    text = '"""A module that says something."""\n\n\ndef go():\n    """Go."""\n'
    found = planted(check_docstrings, text)
    assert any("under" in line for line in found)


def test_an_undocumented_class_method_is_named(planted):
    text = (
        '"""A module that says something."""\n\n\n'
        'class Thing:\n    """A thing worth having."""\n\n    def go(self):\n        return 1\n'
    )
    found = planted(check_docstrings, text)
    assert any("Thing.go" in line for line in found)


def test_a_public_name_outside_all_is_named(planted):
    found = planted(check_exports, '"""A module."""\n\n__all__ = []\n\nLIMIT = 5\n')
    assert any("LIMIT is public and not in __all__" in line for line in found)


def test_a_name_in_all_that_is_gone_is_named(planted):
    found = planted(check_exports, '"""A module."""\n\n__all__ = ["gone"]\n')
    assert any("which is not defined here" in line for line in found)


def test_a_module_with_no_all_is_named(planted):
    found = planted(check_exports, '"""A module."""\n\nLIMIT = 5\n')
    assert any("has no __all__" in line for line in found)


def test_a_repeated_name_in_all_is_named(planted):
    text = '"""A module."""\n\n__all__ = ["LIMIT", "LIMIT"]\n\nLIMIT = 5\n'
    found = planted(check_exports, text)
    assert any("repeats a name" in line for line in found)


def test_a_value_formatted_into_a_query_is_named(planted):
    body = 'def go(carrier):\n    return f"SELECT * FROM x WHERE c = {carrier}"\n'
    text = '"""A module."""\n\n\n' + body
    found = planted(check_sql, text)
    assert any("is formatted into a query" in line for line in found)


def test_a_loose_dataclass_is_named(planted):
    text = (
        '"""A module."""\n\nfrom dataclasses import dataclass\n\n\n'
        '@dataclass\nclass Thing:\n    """A thing worth having."""\n\n    a: int\n'
    )
    found = planted(check_dataclasses, text)
    assert any("not frozen" in line for line in found)
    assert any("does not declare slots" in line for line in found)


def test_a_dataclass_without_slots_is_named(planted):
    text = (
        '"""A module."""\n\nfrom dataclasses import dataclass\n\n\n'
        '@dataclass(frozen=True)\nclass Thing:\n    """A thing worth having."""\n\n    a: int\n'
    )
    found = planted(check_dataclasses, text)
    assert any("does not declare slots" in line for line in found)
    assert not any("not frozen" in line for line in found)


def test_a_marker_left_in_the_source_is_named(monkeypatch, tmp_path):
    made = tmp_path / "planted.py"
    made.write_text('"""A module."""\n\n# ' + "TO" + "DO: finish this\n", encoding="utf-8")
    monkeypatch.setattr(check_todo, "source_files", lambda: [made])
    monkeypatch.setattr(check_todo, "suite_files", list)
    monkeypatch.setattr(check_todo, "repo_root", lambda: tmp_path)
    found = check_todo.problems()
    assert any("left in the source" in line for line in found)


def test_a_case_that_was_turned_off_is_named(monkeypatch, tmp_path):
    made = tmp_path / "test_planted.py"
    # The mark is spelled in two halves so that this file does not itself trip
    # the check it is exercising.
    mark = "@pytest.mark." + "skip"
    made.write_text(
        f'"""A module."""\n\nimport pytest\n\n\n{mark}\ndef test_a(): pass\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(check_todo, "source_files", list)
    monkeypatch.setattr(check_todo, "suite_files", lambda: [made])
    monkeypatch.setattr(check_todo, "repo_root", lambda: tmp_path)
    found = check_todo.problems()
    assert any("turns a test off" in line for line in found)


def test_a_thin_name_in_the_suite_is_named(monkeypatch, tmp_path):
    made = tmp_path / "test_planted.py"
    made.write_text("def test_it_works():\n    pass\n", encoding="utf-8")
    monkeypatch.setattr(check_naming, "suite_files", lambda: [made])
    found = check_naming.problems()
    assert any("is under" in line for line in found)


def test_a_vague_name_in_the_suite_is_named(monkeypatch, tmp_path):
    made = tmp_path / "test_planted.py"
    made.write_text("def test_the_basic_thing_still_works():\n    pass\n", encoding="utf-8")
    monkeypatch.setattr(check_naming, "suite_files", lambda: [made])
    found = check_naming.problems()
    assert any("uses" in line for line in found)


def test_an_unindexed_reference_is_named(monkeypatch):
    from jeepdolly.tools import check_indexes

    def broken(connection) -> None:
        """A schema with a foreign key nothing indexes."""
        connection.execute("CREATE TABLE parent (code TEXT PRIMARY KEY)")
        connection.execute(
            "CREATE TABLE child (id INTEGER PRIMARY KEY, parent_code TEXT"
            " REFERENCES parent (code))"
        )

    monkeypatch.setattr(check_indexes, "migrate", broken)
    monkeypatch.setattr(check_indexes, "EXEMPT", frozenset())
    found = check_indexes.problems()
    assert any("child.parent_code" in line for line in found)


def test_an_exemption_for_a_table_that_is_gone_is_named(monkeypatch):
    from jeepdolly.tools import check_indexes

    monkeypatch.setattr(check_indexes, "EXEMPT", frozenset({"nothing_like_this.code"}))
    found = check_indexes.problems()
    assert any("its table is gone" in line for line in found)


def test_an_exemption_that_is_no_longer_a_reference_is_named(monkeypatch):
    from jeepdolly.tools import check_indexes

    monkeypatch.setattr(check_indexes, "EXEMPT", frozenset({"carrier.name"}))
    found = check_indexes.problems()
    assert any("no longer a reference" in line for line in found)


def test_an_edited_migration_is_named(monkeypatch, tmp_path):
    from jeepdolly.store.migrations import MIGRATIONS
    from jeepdolly.tools import check_migrations

    fake = tmp_path / "migrations.lock"
    lines = [f"{m.number} {check_migrations.fingerprint(m)}" for m in MIGRATIONS]
    lines[0] = f"{MIGRATIONS[0].number} 0000000000000000"
    fake.write_text("\n".join(lines) + "\n", encoding="utf-8")
    monkeypatch.setattr(check_migrations, "lock_path", lambda: fake)
    assert any("has been edited" in line for line in check_migrations.problems())
