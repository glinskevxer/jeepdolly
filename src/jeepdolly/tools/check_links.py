"""Every module the design document names is a module that exists.

The design document is the one piece of prose that names code, and prose that
names code goes stale. A module renamed in a refactor leaves a paragraph pointing
at nothing, and the next reader spends ten minutes deciding whether they have
misunderstood the design or found a typo.

Only names that look like this package's own modules are checked. A backtick
holding a table name, a pragma or an English phrase is left alone, which is why
the pattern insists on a dotted name whose first part is a package directory.
"""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path

from jeepdolly.tools.walk import package_root, repo_root

__all__ = ["DESIGN", "main", "problems", "referenced"]

#: The document that names modules.
DESIGN = "docs/design.md"

#: A backticked dotted name whose head is one of the package's own directories.
_NAME = re.compile(r"`([a-z_]+(?:\.[a-z_]+)+)`")


def _packages() -> set[str]:
    """The package's own top level directory names."""
    root = package_root()
    return {path.name for path in root.iterdir() if (path / "__init__.py").exists()}


def referenced(text: str) -> list[str]:
    """Every dotted name in the text that looks like one of our modules."""
    heads = _packages()
    out: list[str] = []
    for hit in _NAME.finditer(text):
        name = hit.group(1)
        if name.split(".")[0] in heads and name not in out:
            out.append(name)
    return out


def _module(name: str) -> object | None:
    """Import a dotted name as a module, or hand back ``None``."""
    try:
        return importlib.import_module(f"jeepdolly.{name}")
    except ImportError:
        return None


def _exists(name: str) -> bool:
    """Is there a module, or one attribute of a module, with this dotted name.

    The attribute is checked on the module rather than assumed, because a name
    like ``rig.nothing_like_this`` would otherwise pass on the strength of the
    ``rig`` package existing, and that is exactly the reference this check is for.
    """
    if _module(name) is not None:
        return True
    head, _, tail = name.rpartition(".")
    if not head:
        return False
    holder = _module(head)
    return holder is not None and hasattr(holder, tail)


def problems() -> list[str]:
    """Every module the design document names that is not there."""
    path = Path(repo_root() / DESIGN)
    if not path.exists():
        return [f"{DESIGN} is not there"]
    text = path.read_text(encoding="utf-8")
    return [
        f"{DESIGN} names {name}, which is not a module"
        for name in referenced(text)
        if not _exists(name)
    ]


def main() -> int:
    """Report every dead reference and fail if there is one."""
    found = problems()
    for line in found:
        print(f"check_links: {line}")
    if found:
        print(f"check_links: {len(found)} dead references")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
