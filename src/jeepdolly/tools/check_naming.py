"""Test names have to say what they check.

A suite this size is read far more often than it is written, and it is read by
somebody looking at a failure line and nothing else. ``test_width`` tells them
nothing. ``test_a_load_one_inch_over_twelve_feet_needs_a_rear_car`` tells them
what broke without opening the file.

Two rules. Four words after ``test_``, and none of the vague ones. Four rather
than five is deliberate and was measured: at five the check produced sixty eight
findings, most of which were names like ``test_add_then_get_round_trips`` that
are perfectly clear, and a check that mostly fires on good names gets turned off.

Three words that look vague are deliberately absent. ``good_on`` is what the
office calls a permit being valid on a day. ``other_end`` is what a segment calls
the junction at the far end. ``case`` is half of ``BridgeCase`` and of "lower
case". A check that argues with the domain's own vocabulary gets turned off.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from jeepdolly.tools.walk import parse, suite_files

__all__ = ["MIN_WORDS", "VAGUE", "main", "named_tests", "problems"]

#: How many words a test name carries after ``test_``.
MIN_WORDS = 4

#: Words that carry no information on their own in a test name.
VAGUE = frozenset(
    {"works", "ok", "basic", "simple", "thing", "stuff", "test", "misc", "various", "handles"}
)


def named_tests(path: Path) -> list[tuple[int, str]]:
    """Every test function in one file, with the line it starts on."""
    return [
        (node.lineno, node.name)
        for node in ast.walk(parse(path))
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ]


def problems() -> list[str]:
    """Every test name that is too short or too vague."""
    found: list[str] = []
    for path in suite_files():
        for line, name in named_tests(path):
            words = [w for w in name[len("test_") :].split("_") if w]
            if len(words) < MIN_WORDS:
                found.append(f"{path.name}:{line}: {name} is under {MIN_WORDS} words")
            vague = sorted(set(words) & VAGUE)
            if vague:
                found.append(f"{path.name}:{line}: {name} uses {', '.join(vague)}")
    return found


def main() -> int:
    """Report every thin test name and fail if there is one."""
    found = problems()
    for line in found:
        print(f"check_naming: {line}")
    if found:
        print(f"check_naming: {len(found)} test names say too little")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
