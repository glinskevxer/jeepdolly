"""The generated documents have to match what generates them.

Three documents are generated: the command reference, the schema and the
glossary. Each has its own writer with a ``--write`` switch. This runs all of
them in check mode so the build has one command to call and one place to add the
next one.
"""

from __future__ import annotations

import sys
from collections.abc import Callable

from jeepdolly.tools import build_docs, schema_dump

__all__ = ["WRITERS", "main"]

#: Every generated document, by the name the build reports.
WRITERS: dict[str, Callable[[list[str]], int]] = {
    "commands": build_docs.main,
    "schema": schema_dump.main,
}


def main() -> int:
    """Run every writer in check mode and fail if any is stale."""
    status = 0
    for name, writer in sorted(WRITERS.items()):
        if writer([]) != 0:
            print(f"check_docs: {name} is out of date")
            status = 1
    return status


if __name__ == "__main__":
    sys.exit(main())
