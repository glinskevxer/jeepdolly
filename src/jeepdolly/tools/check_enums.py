"""A CHECK constraint listing an enum's values has to list all of them.

The schema is full of constraints like ``CHECK (cause IN ('office error', ...))``
and every one of them is a copy of a ``StrEnum`` written out by hand. There is no
way to make sqlite read the enum, so the copy is unavoidable. What is avoidable
is nobody noticing when the two drift.

They drift in one direction almost every time. Somebody adds a member to the
enum, the code that writes the row is fine, the code that reads it is fine, the
tests pass because nothing exercises the new member against a real file, and the
first time it is used in anger sqlite refuses the insert with a constraint name
and no explanation.

So this reads the constraints out of a freshly migrated file, matches each one to
the enum whose values it looks like, and fails when either side has something the
other does not. Matching is by overlap rather than by name: the column is called
``cause`` and the enum is called ``Cause`` in one place and ``EventKind`` in
another, and a naming convention would have to be enforced by yet another check.

A constraint that matches no enum at all is left alone. Plenty of them are lists
of two or three literals that were never an enum, and demanding one for those
would mean writing enums to satisfy a check.

Named subsets count too, and finding that out is the reason the check exists. Its
first run flagged the violation table for listing two of the four discrepancies,
which is correct: that column mirrors ``CHARGEABLE`` rather than the whole enum,
because a rig lighter than its permit is worth recording and is not an offence.
So the candidates are the enums *and* every module level frozenset of strings,
and a constraint that exactly equals either one is right.
"""

from __future__ import annotations

import re
import sys
from enum import StrEnum

from jeepdolly.store.migrations import migrate
from jeepdolly.store.sqlite import MEMORY, opened
from jeepdolly.tools.walk import module_of, package_root, source_files

__all__ = [
    "OVERLAP",
    "constraints_in",
    "drift",
    "enums_in_package",
    "main",
    "problems",
    "schema_text",
]

#: A constraint has to share at least this much with an enum to be one of its
#: copies. Below it the overlap is a coincidence between two short literal lists.
OVERLAP = 2

_IN_LIST = re.compile(r"CHECK\s*\(\s*(\w+)\s+IN\s*\(([^)]*)\)", re.IGNORECASE)
_LITERAL = re.compile(r"'([^']*)'")


def schema_text() -> str:
    """Every CREATE statement in a file that has had every migration."""
    with opened(MEMORY) as connection:
        migrate(connection)
        rows = connection.execute(
            "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL"
        ).fetchall()
    return "\n".join(str(row["sql"]) for row in rows)


def constraints_in(schema: str) -> list[tuple[str, frozenset[str]]]:
    """Every column and the literal list its CHECK constrains it to."""
    found: list[tuple[str, frozenset[str]]] = []
    for hit in _IN_LIST.finditer(schema):
        values = frozenset(_LITERAL.findall(hit.group(2)))
        if values:
            found.append((hit.group(1), values))
    return found


def _strings(value: object) -> frozenset[str] | None:
    """The value as a set of plain strings, or ``None`` if it is not one."""
    if not isinstance(value, frozenset) or not value:
        return None
    if not all(isinstance(one, str) for one in value):
        return None
    return frozenset(str(one) for one in value)


def enums_in_package() -> dict[str, frozenset[str]]:
    """Every set of strings the package names, by its qualified name.

    Both the string enums and the module level frozensets, because a constraint
    may legitimately mirror either. The name is carried through so a failure says
    which of the two the schema has drifted from.
    """
    held: dict[str, frozenset[str]] = {}
    for path in source_files():
        name = module_of(path)
        module = __import__(name, fromlist=["*"])
        for label, attribute in vars(module).items():
            if (
                isinstance(attribute, type)
                and issubclass(attribute, StrEnum)
                and attribute is not StrEnum
                and attribute.__module__ == name
            ):
                held[f"{name}.{attribute.__name__}"] = frozenset(str(one) for one in attribute)
                continue
            if label.isupper():
                members = _strings(attribute)
                if members is not None:
                    held[f"{name}.{label}"] = members
    return held


def drift(
    constraints: list[tuple[str, frozenset[str]]], candidates: dict[str, frozenset[str]]
) -> list[str]:
    """Every constraint that does not exactly match some named set.

    Split out from ``problems`` so it can be handed a drifted schema directly.
    The package's own schema is right, which is the point of the check and also
    the reason the reporting half of it was never once executed by the suite.
    """
    found: list[str] = []
    for column, values in constraints:
        if any(members == values for members in candidates.values()):
            continue
        best: tuple[int, str, frozenset[str]] | None = None
        for name, members in sorted(candidates.items()):
            shared = len(values & members)
            if shared >= OVERLAP and (best is None or shared > best[0]):
                best = (shared, name, members)
        if best is None:
            continue
        _, name, members = best
        missing = members - values
        extra = values - members
        if missing:
            found.append(f"{column}: {name} has {sorted(missing)} and the schema does not")
        if extra:
            found.append(f"{column}: the schema has {sorted(extra)} and {name} does not")
    return sorted(found)


def problems() -> list[str]:
    """Every constraint in the office's own schema that has drifted."""
    return drift(constraints_in(schema_text()), enums_in_package())


def main() -> int:
    """Print every drifted constraint and say how many there were."""
    found = problems()
    for line in found:
        print(f"check_enums: {line}")
    if found:
        print(f"check_enums: {len(found)} constraints do not match their enum")
        return 1
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(package_root().parent))
    raise SystemExit(main())
