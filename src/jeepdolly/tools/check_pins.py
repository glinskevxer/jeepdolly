"""The constraints file is complete, exact and actually used.

Pinning the direct dependencies is the easy half and it does not work. Pip is
free to walk forward on anything they pull in, and it does: installing this
package without the constraints file brings a newer ``packaging`` and a newer
``pluggy``, and the 3.13 leg of the build starts reporting warnings that have
nothing to do with this code.

So three things are checked. Every requirement is pinned with ``==`` rather than
a floor. Every direct dependency of the package and of the build appears in the
constraints file. And every place the build installs anything passes
``-c constraints.txt``, because a pinned file nobody points at is decoration.

Sorting is checked too, so that adding a line produces a one line diff.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

from jeepdolly.tools.walk import repo_root

__all__ = ["CONSTRAINTS", "PYPROJECT", "WORKFLOW", "declared", "main", "pins", "problems"]

CONSTRAINTS = "constraints.txt"
PYPROJECT = "pyproject.toml"
WORKFLOW = ".github/workflows/ci.yml"

_PIN = re.compile(r"^([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+-]+)$")
_NAME = re.compile(r"^([A-Za-z0-9_.-]+)")


def _normal(name: str) -> str:
    """A package name the way pip compares them."""
    return re.sub(r"[-_.]+", "-", name).lower()


def pins(root: Path | None = None) -> dict[str, str]:
    """Every pin in the constraints file, by normalised package name."""
    path = (root or repo_root()) / CONSTRAINTS
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        hit = _PIN.match(text)
        if hit is not None:
            out[_normal(hit.group(1))] = hit.group(2)
            continue
        loose = _NAME.match(text)
        # A requirement that is not an exact pin is still recorded, with an
        # empty version, so the check below can name it rather than miss it.
        out[_normal(loose.group(1)) if loose else text] = ""
    return out


def declared(root: Path | None = None) -> set[str]:
    """Every package the project itself names, runtime and build."""
    path = (root or repo_root()) / PYPROJECT
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for requirement in data.get("project", {}).get("dependencies", []):
        hit = _NAME.match(requirement)
        if hit:
            names.add(_normal(hit.group(1)))
    for requirement in data.get("build-system", {}).get("requires", []):
        hit = _NAME.match(requirement)
        if hit:
            names.add(_normal(hit.group(1)))
    return names


def _order(root: Path | None = None) -> list[str]:
    """The package names in the constraints file, in the order they appear."""
    path = (root or repo_root()) / CONSTRAINTS
    found: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if text and not text.startswith("#"):
            hit = _NAME.match(text)
            if hit:
                found.append(_normal(hit.group(1)))
    return found


def problems(root: Path | None = None) -> list[str]:
    """Everything wrong with the pinning, one line each."""
    here = root or repo_root()
    found: list[str] = []
    held = pins(here)
    for name, version in sorted(held.items()):
        if not version:
            found.append(f"{name} is in {CONSTRAINTS} without an exact version")
    for name in sorted(declared(here)):
        if name not in held:
            found.append(f"{name} is a dependency and is not in {CONSTRAINTS}")
    order = _order(here)
    if order != sorted(order):
        found.append(f"{CONSTRAINTS} is not in name order")
    if len(set(order)) != len(order):
        found.append(f"{CONSTRAINTS} names something twice")
    found.extend(_workflow_problems(here))
    return found


def _workflow_problems(here: Path) -> list[str]:
    """Every place the build installs something without the constraints file."""
    workflow = here / WORKFLOW
    if not workflow.exists():
        return [f"{WORKFLOW} is not there"]
    found: list[str] = []
    for number, line in enumerate(workflow.read_text(encoding="utf-8").splitlines(), 1):
        if "pip install" in line and "-c constraints.txt" not in line:
            found.append(f"{WORKFLOW}:{number} installs without the constraints file")
    return found


def main() -> int:
    """Report every loose pin and fail if there is one."""
    found = problems()
    for line in found:
        print(f"check_pins: {line}")
    if found:
        print(f"check_pins: {len(found)} problems with the pinning")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
