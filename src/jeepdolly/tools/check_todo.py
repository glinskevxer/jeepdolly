"""Nothing goes in with a note saying it is not finished.

A ``TODO`` in a shipped file is a promise nobody made a date for. The office's
rule is that unfinished work is either finished, or it is not committed, or the
gap is written into the docstring as what the code deliberately does not do.
That last one is why this check looks for markers and not for the word "not".

The same rule covers skipped tests. A ``skip`` with no reason is a test somebody
turned off, and a suite with three of those is a suite nobody trusts.
"""

from __future__ import annotations

import re
import sys

from jeepdolly.tools.walk import repo_root, source_files, suite_files

__all__ = ["MARKERS", "SKIP_MARKS", "main", "problems"]

#: Words that mean the work is not done.
MARKERS = ("TODO", "FIXME", "XXX", "HACK", "WIP")

#: Pytest marks that turn a test off.
SKIP_MARKS = ("pytest.mark.skip", "pytest.mark.xfail", "pytest.skip(")

_MARKER = re.compile(r"\b(" + "|".join(MARKERS) + r")\b")


def problems() -> list[str]:
    """Every marker left in the source and every silently skipped test."""
    found: list[str] = []
    root = repo_root()
    for path in (*source_files(), *suite_files()):
        if "check_todo" in path.name:
            # This check and its own tests have to name the markers to look for
            # them, so they are the one place the words are allowed.
            continue
        where = path.relative_to(root)
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            hit = _MARKER.search(line)
            if hit is not None:
                found.append(f"{where}:{number}: {hit.group(1)} left in the source")
            for mark in SKIP_MARKS:
                if mark in line:
                    found.append(f"{where}:{number}: {mark} turns a test off")
    return found


def main() -> int:
    """Report every marker and fail if there is one."""
    found = problems()
    for line in found:
        print(f"check_todo: {line}")
    if found:
        print(f"check_todo: {len(found)} unfinished notes")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
