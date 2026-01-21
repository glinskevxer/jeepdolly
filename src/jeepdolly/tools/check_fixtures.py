"""A fixture that opens the office has to close it.

This check exists because the 3.13 leg of the build found the same mistake twice.
A sqlite connection is a context manager for its *transaction*, not for itself:
leaving a ``with`` block commits and does not close. A fixture that opens an
office and ``return``s it leaks the connection, which 3.12 says nothing about and
3.13 reports as a ``ResourceWarning`` that the suite turns into an error.

The rule is mechanical with one refinement. A fixture whose body opens something
and hands it back has to be a generator fixture, which means it has to ``yield``.
A fixture that opens something *inside a* ``with`` *block* and closes it before
returning is fine, and so is one that merely takes an already open office as an
argument, which is the shape most of them should be.

The refinement was added after the check called a fixture a leak for opening a
file, writing one row and closing it again. A check that fires on correct code is
a check somebody turns off.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from jeepdolly.tools.walk import parse, suite_files

__all__ = ["OPENERS", "is_fixture", "main", "opens_something", "problems"]

#: Calls that hand back something holding an open file handle.
#:
#: ``create`` is deliberately not one of them. It opens a file, migrates it and
#: closes it again, handing back nothing, so there is nothing for a caller to
#: leak. It was on this list to begin with and the only thing that produced was
#: a finding against a fixture that had done everything right.
OPENERS = frozenset({"opened", "opened_office", "opened_new_office", "connect"})


def is_fixture(node: ast.FunctionDef) -> bool:
    """Is this function decorated as a pytest fixture."""
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        name = target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", "")
        if name == "fixture":
            return True
    return False


def _is_opener(node: ast.AST) -> bool:
    """Is this a call to something that hands back an open handle."""
    if not isinstance(node, ast.Call):
        return False
    target = node.func
    name = target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", "")
    return name in OPENERS


def _managed(node: ast.FunctionDef) -> set[int]:
    """Every opener call that is the subject of a ``with`` in this function."""
    held: set[int] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.With | ast.AsyncWith):
            continue
        for item in child.items:
            for inner in ast.walk(item.context_expr):
                if _is_opener(inner):
                    held.add(id(inner))
    return held


def opens_something(node: ast.FunctionDef) -> bool:
    """Does the body open a connection without a ``with`` to close it."""
    held = _managed(node)
    return any(_is_opener(child) and id(child) not in held for child in ast.walk(node))


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
