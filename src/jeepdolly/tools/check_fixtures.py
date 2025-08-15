"""A fixture that opens the office has to close it.

This check exists because the 3.13 leg of the build found the same mistake twice.
A sqlite connection is a context manager for its *transaction*, not for itself:
leaving a ``with`` block commits and does not close. A fixture that opens an
office and ``return``s it leaks the connection, which 3.12 says nothing about and
3.13 reports as a ``ResourceWarning`` that the suite turns into an error.

The rule is mechanical. A fixture whose body opens anything has to be a generator
fixture, which means it has to ``yield``. A fixture that merely takes an already
open office as an argument is fine and is the shape most of them should be.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from jeepdolly.tools.walk import parse, suite_files

__all__ = ["OPENERS", "is_fixture", "main", "opens_something", "problems"]

#: Calls that hand back something holding an open file handle.
OPENERS = frozenset({"opened", "opened_office", "opened_new_office", "connect", "create"})


def is_fixture(node: ast.FunctionDef) -> bool:
    """Is this function decorated as a pytest fixture."""
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        name = target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", "")
        if name == "fixture":
            return True
    return False


def opens_something(node: ast.FunctionDef) -> bool:
    """Does the body of this function open a connection."""
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        target = child.func
        name = target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", "")
        if name in OPENERS:
            return True
    return False


def _yields(node: ast.FunctionDef) -> bool:
    """Does this function yield, making it a generator fixture."""
    return any(isinstance(child, ast.Yield | ast.YieldFrom) for child in ast.walk(node))


def problems() -> list[str]:
    """Every fixture that opens something and does not yield it."""
    found: list[str] = []
    for path in suite_files():
        for node in ast.walk(parse(Path(path))):
            if not isinstance(node, ast.FunctionDef) or not is_fixture(node):
                continue
            if opens_something(node) and not _yields(node):
                found.append(
                    f"{path.name}:{node.lineno}: fixture {node.name} opens and never closes"
                )
    return found


def main() -> int:
    """Report every leaking fixture and fail if there is one."""
    found = problems()
    for line in found:
        print(f"check_fixtures: {line}")
    if found:
        print(f"check_fixtures: {len(found)} fixtures leak")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
