"""Finding the package's own source files, once, for every check to share."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

__all__ = [
    "imports_of",
    "module_of",
    "package_root",
    "parse",
    "repo_root",
    "source_files",
    "suite_files",
]


def package_root() -> Path:
    """The directory holding the package."""
    return Path(__file__).resolve().parent.parent


def repo_root() -> Path:
    """The directory holding ``src`` and ``tests``."""
    return package_root().parent.parent


def source_files() -> list[Path]:
    """Every module of the package, in path order, the checks included."""
    return sorted(package_root().rglob("*.py"))


def suite_files() -> list[Path]:
    """Every file of the test suite, in path order."""
    tests = repo_root() / "tests"
    if not tests.is_dir():
        return []
    return sorted(tests.rglob("*.py"))


def parse(path: Path) -> ast.Module:
    """Read and parse one file."""
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def module_of(path: Path) -> str:
    """The dotted module name of a source file."""
    relative = path.resolve().relative_to(package_root().parent)
    parts = list(relative.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def imports_of(tree: ast.Module) -> Iterator[str]:
    """Every module this file imports, absolute names only.

    A relative import cannot cross a package boundary in this codebase, so it
    cannot break the layering and is skipped rather than resolved.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module
