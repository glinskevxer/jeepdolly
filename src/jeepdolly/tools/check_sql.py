"""No value is ever formatted into a SQL string.

Every query in this package is a literal with ``?`` placeholders, and every value
goes through the parameter tuple. Interpolating a value is how a carrier code
with an apostrophe in it becomes a syntax error, and on a system that took input
from anywhere but a clerk's keyboard it would be a good deal worse than that.

Identifiers are the exception and they cannot be parameterised: a table name or a
column list has to be formatted in. Those are all read from class attributes the
package itself sets, never from an argument, and the names that may be
interpolated are listed here one by one. Adding to that list is a decision;
having it be a list is what makes it a decision.
"""

from __future__ import annotations

import ast
import sys

from jeepdolly.tools.walk import module_of, parse, source_files

__all__ = ["ALLOWED", "interpolations", "main", "problems"]

#: Names that may be formatted into a query. Every one is an identifier this
#: package chose, never a value that came in from outside.
ALLOWED = frozenset(
    {
        "self.table",
        "self.key_column",
        "self.order_by",
        "clause",
        "names",
        "placeholders",
        "assignments",
        "table",
        "column",
    }
)


def _formatted_names(node: ast.JoinedStr) -> list[str]:
    """The expressions interpolated into one f-string, as source text."""
    out: list[str] = []
    for piece in node.values:
        if isinstance(piece, ast.FormattedValue):
            out.append(ast.unparse(piece.value))
    return out


def interpolations(tree: ast.Module) -> list[tuple[int, str]]:
    """Every name formatted into a string that looks like a query."""
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.JoinedStr):
            continue
        text = "".join(
            piece.value for piece in node.values if isinstance(piece, ast.Constant)
        ).upper()
        if not any(word in text for word in ("SELECT ", "INSERT ", "UPDATE ", "DELETE ")):
            continue
        for name in _formatted_names(node):
            found.append((node.lineno, name))
    return found


def problems() -> list[str]:
    """Every query holding a name that is not an allowed identifier."""
    found: list[str] = []
    for path in source_files():
        module = module_of(path)
        for line, name in interpolations(parse(path)):
            if name not in ALLOWED:
                found.append(f"{module}:{line}: {name} is formatted into a query")
    return found


def main() -> int:
    """Report every interpolated value and fail if there is one."""
    found = problems()
    for line in found:
        print(f"check_sql: {line}")
    if found:
        print(f"check_sql: {len(found)} queries build a string from a name")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
