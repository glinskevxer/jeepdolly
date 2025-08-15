"""Some calls belong in one module and nowhere else.

Four of them, and each one is a boundary that stopped being true at least once.

``sqlite3.connect`` belongs in ``store.sqlite`` because that is where the pragmas
are applied. A connection opened anywhere else has foreign keys off and looks
fine until a delete quietly orphans a hundred axle rows.

``datetime.now`` belongs in the command line. Everything below it takes the day
as an argument, which is what makes a permit recomputable a year later and what
makes the tests free of a clock.

``print`` belongs in the checks. Everything else reports through click or returns
a value.

``open`` belongs in the importer and the checks. The store reads through sqlite
and nothing else in the package touches the filesystem.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass

from jeepdolly.tools.walk import module_of, parse, source_files

__all__ = ["BOUNDARIES", "Boundary", "calls_in", "main", "problems"]


@dataclass(frozen=True, slots=True)
class Boundary:
    """One call and the modules allowed to make it."""

    call: str
    allowed: tuple[str, ...]
    because: str

    def permits(self, module: str) -> bool:
        """May this module make the call."""
        return any(module == name or module.startswith(name + ".") for name in self.allowed)


BOUNDARIES: tuple[Boundary, ...] = (
    Boundary(
        call="sqlite3.connect",
        allowed=("jeepdolly.store.sqlite",),
        because="a connection opened elsewhere has no pragmas applied",
    ),
    Boundary(
        call="datetime.now",
        allowed=("jeepdolly.cli",),
        because="everything below the command line takes the day as an argument",
    ),
    Boundary(
        call="print",
        allowed=("jeepdolly.tools",),
        because="the package reports through click or by returning a value",
    ),
    Boundary(
        call="open",
        allowed=("jeepdolly.tools", "jeepdolly.importer"),
        because="the store reads through sqlite and nothing else touches files",
    ),
)


def _called_name(node: ast.Call) -> str:
    """The dotted name a call names, as far as it can be read statically."""
    target = node.func
    parts: list[str] = []
    while isinstance(target, ast.Attribute):
        parts.append(target.attr)
        target = target.value
    if isinstance(target, ast.Name):
        parts.append(target.id)
    return ".".join(reversed(parts))


def calls_in(tree: ast.Module) -> list[tuple[int, str]]:
    """Every call in a file, with the line it is on."""
    return [
        (node.lineno, _called_name(node))
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    ]


def _matches(called: str, wanted: str) -> bool:
    """Does a call name the boundary, allowing for a module prefix."""
    return called == wanted or called.endswith("." + wanted)


def problems() -> list[str]:
    """Every call made from a module that is not allowed to make it."""
    found: list[str] = []
    for path in source_files():
        module = module_of(path)
        seen = calls_in(parse(path))
        for boundary in BOUNDARIES:
            if boundary.permits(module):
                continue
            for line, called in seen:
                if _matches(called, boundary.call):
                    found.append(f"{module}:{line}: {boundary.call} here, {boundary.because}")
    return found


def main() -> int:
    """Report every crossed boundary and fail if there is one."""
    found = problems()
    for line in found:
        print(f"check_boundaries: {line}")
    if found:
        print(f"check_boundaries: {len(found)} calls in the wrong place")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
