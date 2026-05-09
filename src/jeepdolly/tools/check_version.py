"""The version is written in two places and they have to agree.

``pyproject.toml`` is what the wheel is stamped with and ``__init__.py`` is what
``jeepdolly --version`` prints. They are separate on purpose: the build reads one
without importing the package, and the package reports the other without reading
a file that is not in the wheel.

Separate and equal is fine. Separate and different is a support call that starts
"I have 1.0.0 installed" about a wheel that is not 1.0.0, and the office has no
way to tell which of the two the caller means.

The shape is checked as well. Three dot separated numbers, because everything
downstream of this sorts them and a release candidate suffix would sort wrong.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

from jeepdolly import __version__
from jeepdolly.tools.walk import repo_root

__all__ = ["PYPROJECT", "declared_version", "main", "problems", "well_formed"]

PYPROJECT = "pyproject.toml"

_SHAPE = re.compile(r"^\d+\.\d+\.\d+$")


def declared_version(root: Path | None = None) -> str:
    """The version the build stamps the wheel with."""
    path = (root or repo_root()) / PYPROJECT
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return str(data.get("project", {}).get("version", ""))


def well_formed(version: str) -> bool:
    """Is this three dot separated numbers and nothing else."""
    return bool(_SHAPE.match(version))


def problems(root: Path | None = None) -> list[str]:
    """Everything wrong with the version, one line each."""
    found: list[str] = []
    declared = declared_version(root)
    if not declared:
        found.append(f"{PYPROJECT} names no version")
    elif not well_formed(declared):
        found.append(f"{PYPROJECT} says {declared}, which is not three numbers")
    if not well_formed(__version__):
        found.append(f"the package says {__version__}, which is not three numbers")
    if declared and declared != __version__:
        found.append(f"{PYPROJECT} says {declared} and the package says {__version__}")
    return found


def main() -> int:
    """Report every disagreement and fail if there is one."""
    found = problems()
    for line in found:
        print(f"check_version: {line}")
    if found:
        print(f"check_version: {len(found)} problems with the version")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
