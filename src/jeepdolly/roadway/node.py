"""Junctions.

A node is somewhere a route can start, end or change. Interchanges, state line
crossings, the gate of a quarry. Nodes are not co-ordinates; the office's map is
a list of what connects to what, and the only geography it holds is the county,
which matters because a county can post its own embargo.

The code is what a clerk types and the name is what gets printed on the permit.
Both are required, because a route sheet reading ``JCT-12 to JCT-31`` tells the
driver nothing.
"""

from __future__ import annotations

from dataclasses import dataclass

from jeepdolly.errors import BadValueError
from jeepdolly.ids.reference import Code, code

__all__ = ["MAX_COUNTY", "MAX_NAME", "Node"]

MAX_NAME = 60
MAX_COUNTY = 40


@dataclass(frozen=True, slots=True, order=True)
class Node:
    """One point on the office's map."""

    code: Code
    name: str
    county: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", code(str(self.code)))
        for field, cap in (("name", MAX_NAME), ("county", MAX_COUNTY)):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise BadValueError(field, value, "want some text")
            tidy = " ".join(value.split())
            if len(tidy) > cap:
                raise BadValueError(field, value, f"over {cap} characters")
            object.__setattr__(self, field, tidy)

    def __str__(self) -> str:
        return f"{self.code} {self.name} ({self.county})"
