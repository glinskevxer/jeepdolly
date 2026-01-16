"""A module may only import from a layer below its own.

The layering is the reason any of this is testable. The limits do not know about
the map, the map does not know about the calendar, and the file does not know
about any of them. Every one of those is one import away from not being true,
and an import that breaks it does not fail a test, it just quietly makes the
next refactor harder.

Same layer imports are allowed. Two modules at the same level are peers and
saying otherwise would put every package in its own layer and mean nothing.

When a module genuinely belongs somewhere else, move the module. Adding an entry
to this table to make the check pass is the failure mode it is guarding against,
so the table is short on purpose and every line of it is a claim about the design.
"""

from __future__ import annotations

import sys

from jeepdolly.tools.walk import imports_of, module_of, parse, source_files

__all__ = ["LAYERS", "layer_of", "main", "problems"]

#: Most specific prefix wins, so ``limits.finding`` sits below the rest of the
#: limits and ``permit.desk`` sits above the file it reads.
LAYERS: dict[str, int] = {
    "jeepdolly.errors": 0,
    "jeepdolly.units": 0,
    "jeepdolly.ids": 1,
    "jeepdolly.limits.finding": 2,
    "jeepdolly.rig": 3,
    "jeepdolly.rig.spread": 5,
    "jeepdolly.party": 3,
    "jeepdolly.limits": 4,
    "jeepdolly.roadway": 5,
    "jeepdolly.almanac": 6,
    "jeepdolly.travel": 7,
    "jeepdolly.route": 8,
    "jeepdolly.permit": 9,
    "jeepdolly.permit.application": 9,
    "jeepdolly.billing": 9,
    "jeepdolly.permit.review": 10,
    "jeepdolly.permit.decision": 10,
    "jeepdolly.permit.permit": 11,
    "jeepdolly.store": 12,
    "jeepdolly.permit.desk": 13,
    "jeepdolly.invariants": 14,
    "jeepdolly.report": 14,
    "jeepdolly.importer": 14,
    "jeepdolly.cli": 15,
    "jeepdolly.tools": 15,
}


def layer_of(module: str) -> int | None:
    """Which layer a module sits in, or ``None`` if it is not ours.

    The package's own ``__init__`` holds the version and nothing else, so it
    sits at the bottom by definition rather than by a table entry.
    """
    if module == "jeepdolly":
        return 0
    if not module.startswith("jeepdolly."):
        return None
    best: tuple[int, int] | None = None
    for prefix, layer in LAYERS.items():
        if module == prefix or module.startswith(prefix + "."):
            depth = len(prefix.split("."))
            if best is None or depth > best[0]:
                best = (depth, layer)
    return None if best is None else best[1]


def problems() -> list[str]:
    """Every import that reaches up a layer, one line each.

    Called ``problems`` like every other check's finder, so the build can run
    them through one loop and a test can feed any of them a made up finding.
    """
    found: list[str] = []
    for path in source_files():
        module = module_of(path)
        here = layer_of(module)
        if here is None:
            found.append(f"{module}: no layer is claimed for this module")
            continue
        for imported in imports_of(parse(path)):
            there = layer_of(imported)
            if there is None:
                continue
            if there > here:
                found.append(f"{module} (layer {here}) imports {imported} (layer {there})")
    return found


def main() -> int:
    """Report every violation and fail if there is one."""
    found = problems()
    for line in found:
        print(f"check_layers: {line}")
    if found:
        print(f"check_layers: {len(found)} imports reach up a layer")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
