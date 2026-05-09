"""The package carries the files it reads at runtime, not only its modules.

One file in this package is read at runtime and is not a ``.py``: the migration
fingerprints. Hatchling ships the whole package directory, so it comes across,
and nothing in the ordinary suite would notice if that stopped being true because
every test runs from the source tree where the file is there either way.

So this asserts the shape the wheel has to have, from the source tree, and the
build asserts the same thing about the wheel it actually made.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from jeepdolly.store.migrations import MIGRATIONS
from jeepdolly.tools.check_migrations import lock_path, read_lock
from jeepdolly.tools.walk import package_root, repo_root


def test_the_lock_file_sits_inside_the_package():
    assert lock_path().is_relative_to(package_root())


def test_the_lock_file_is_read_from_beside_the_migrations():
    assert lock_path().parent == package_root() / "store"


def test_the_lock_file_covers_every_migration():
    assert set(read_lock()) == {m.number for m in MIGRATIONS}


def test_the_only_data_file_in_the_package_is_the_lock():
    found = [
        path
        for path in package_root().rglob("*")
        if path.is_file() and path.suffix not in {".py", ".pyc"}
    ]
    assert [path.name for path in found] == ["migrations.lock"]


def test_the_build_ships_the_whole_package_directory():
    data = tomllib.loads((repo_root() / "pyproject.toml").read_text(encoding="utf-8"))
    wheel = data["tool"]["hatch"]["build"]["targets"]["wheel"]
    assert wheel["packages"] == ["src/jeepdolly"]


def test_the_console_script_points_at_the_command_line():
    data = tomllib.loads((repo_root() / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["scripts"]["jeepdolly"] == "jeepdolly.cli.main:main"


def test_the_package_declares_one_runtime_dependency():
    data = tomllib.loads((repo_root() / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["dependencies"] == ["click==8.1.8"]


def test_the_package_needs_at_least_this_interpreter():
    data = tomllib.loads((repo_root() / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["requires-python"] == ">=3.12"


def test_the_walk_script_is_not_inside_the_package():
    assert not (package_root() / "scripts").exists()
    assert (repo_root() / "scripts" / "walk.sh").exists()


def test_the_tests_are_beside_the_package_and_not_in_it():
    assert (repo_root() / "tests").is_dir()
    assert not (package_root() / "tests").exists()


def test_every_package_directory_has_an_init():
    for path in package_root().rglob("*"):
        if path.is_dir() and any(child.suffix == ".py" for child in path.iterdir()):
            assert (path / "__init__.py").exists(), path


def test_the_source_tree_carries_the_four_files_it_should():
    top = {path.name for path in Path(repo_root()).iterdir() if path.is_file()}
    assert {"README.md", "pyproject.toml", "constraints.txt", ".gitignore"} <= top


def test_no_module_sits_loose_at_the_top_of_the_tree():
    """A runtime artefact like ``.coverage`` is fine; a stray module is not."""
    loose = [
        path.name
        for path in Path(repo_root()).iterdir()
        if path.is_file() and path.suffix == ".py"
    ]
    assert loose == []
