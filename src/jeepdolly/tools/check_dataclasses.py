"""Every dataclass in this package is frozen and declares slots.

Both for the same reason, and it is not performance.

Frozen is what makes a record safe to hand around. Half this package passes
assessments and permits down through four layers, and a mutable one would let any
of those quietly change a number the layer above had already read.

Slots is what makes frozen mean something. Without it a typo in an attribute name
adds a new attribute instead of raising, so ``permit.numbr = "P-1"`` succeeds and
the permit still has its old number. With slots that is an ``AttributeError`` on
the line that made the mistake.

The exceptions are listed by name. There are two, both of them the counter's own
mutable state, and each says why.
"""

from __future__ import annotations

import ast
import sys

from jeepdolly.tools.walk import module_of, parse, source_files

__all__ = ["MUTABLE", "decorated", "main", "problems"]

#: Dataclasses that are deliberately not frozen, and why.
MUTABLE: dict[str, str] = {
    "jeepdolly.cli.context.Session": (
        "the top level group builds it before the subcommand runs and the"
        " subcommand may set the clerk on it"
    ),
    "jeepdolly.permit.desk.Desk": (
        "the almanac books are read off the file after the desk is built, so"
        " that a caller who forgets is still given a working desk"
    ),
}


def decorated(node: ast.ClassDef) -> dict[str, bool] | None:
    """The dataclass arguments of a class, or ``None`` if it is not one."""
    for item in node.decorator_list:
        target = item.func if isinstance(item, ast.Call) else item
        name = target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", "")
        if name != "dataclass":
            continue
        found: dict[str, bool] = {}
        if isinstance(item, ast.Call):
            for keyword in item.keywords:
                if keyword.arg and isinstance(keyword.value, ast.Constant):
                    found[keyword.arg] = bool(keyword.value.value)
        return found
    return None


def problems() -> list[str]:
    """Every dataclass that is not frozen, or has no slots, without a reason."""
    found: list[str] = []
    for path in source_files():
        module = module_of(path)
        for node in ast.walk(parse(path)):
            if not isinstance(node, ast.ClassDef):
                continue
            args = decorated(node)
            if args is None:
                continue
            name = f"{module}.{node.name}"
            if not args.get("frozen", False) and name not in MUTABLE:
                found.append(f"{name}: not frozen and not on the list of exceptions")
            if not args.get("slots", False):
                found.append(f"{name}: does not declare slots")
    return found


def main() -> int:
    """Report every loose dataclass and fail if there is one."""
    found = problems()
    for line in found:
        print(f"check_dataclasses: {line}")
    if found:
        print(f"check_dataclasses: {len(found)} loose dataclasses")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
