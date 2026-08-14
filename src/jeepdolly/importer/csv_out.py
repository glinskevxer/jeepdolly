"""Writing the map and the carrier list back out as comma separated files.

The point of this is not backup. The office has a backup and it is the sqlite
file. The point is that the highway department sends the map as spreadsheets,
the office edits it at the counter for a year, and then somebody has to send
back a corrected map. Doing that by hand out of a database viewer is how three
of the mileposts ended up wrong.

So the columns written are the importer's own columns, taken from its table
rather than repeated here. A round trip through both has to come back the same,
and there is a test that does exactly that. That coupling is deliberate: adding a
column to the loader and forgetting it here would produce an export that looks
complete and quietly drops a field.

Blank rather than the word None for anything not set, because the loader treats
a blank cell as absent and would take "None" as a value and fail on it.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from jeepdolly.errors import BadValueError
from jeepdolly.importer.csv_in import COLUMNS, FILES
from jeepdolly.party.carrier import Carrier
from jeepdolly.roadway.node import Node
from jeepdolly.roadway.segment import Segment
from jeepdolly.roadway.structure import Structure
from jeepdolly.store.office import Office

__all__ = [
    "Written",
    "row_of_carrier",
    "row_of_node",
    "row_of_segment",
    "row_of_structure",
    "write_all",
    "write_rows",
]


def _text(value: object) -> str:
    """One cell, with nothing written for anything not set."""
    return "" if value is None else str(value)


@dataclass(frozen=True, slots=True)
class Written:
    """How many of each kind of record went out."""

    carriers: int = 0
    nodes: int = 0
    segments: int = 0
    structures: int = 0

    @property
    def total(self) -> int:
        """Every record written."""
        return self.carriers + self.nodes + self.segments + self.structures

    def __str__(self) -> str:
        return (
            f"{self.carriers} carriers, {self.nodes} junctions,"
            f" {self.segments} stretches, {self.structures} structures"
        )


def write_rows(path: Path, columns: Sequence[str], body: Iterable[Sequence[str]]) -> int:
    """Write one file with its header row, returning how many rows went in."""
    if not columns:
        raise BadValueError("columns", columns, "want at least one column")
    count = 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        for row in body:
            if len(row) != len(columns):
                raise BadValueError("row", list(row), f"want {len(columns)} cells")
            writer.writerow(row)
            count += 1
    return count


def row_of_carrier(carrier: Carrier) -> tuple[str, ...]:
    """One carrier as the loader's columns expect it."""
    return (
        str(carrier.code),
        carrier.name,
        str(carrier.usdot),
        carrier.home_state,
        "yes" if carrier.active else "no",
    )


def row_of_node(node: Node) -> tuple[str, ...]:
    """One junction as the loader's columns expect it."""
    return (str(node.code), node.name, node.county)


def row_of_segment(segment: Segment) -> tuple[str, ...]:
    """One stretch as the loader's columns expect it."""
    return (
        str(segment.code),
        str(segment.start),
        str(segment.end),
        segment.route,
        f"{int(segment.distance) / 100:.2f}",
        str(segment.road_class),
        "yes" if segment.one_way else "no",
        _text(None if segment.posted_gross is None else int(segment.posted_gross)),
        _text(None if segment.max_width is None else int(segment.max_width)),
        _text(None if segment.max_height is None else int(segment.max_height)),
    )


def row_of_structure(structure: Structure) -> tuple[str, ...]:
    """One structure as the loader's columns expect it.

    The reference is not written. The loader hands out its own on the way in,
    so exporting one and loading it back would leave the office with two
    structures under different references and the same milepost.
    """
    return (
        str(structure.segment),
        structure.name,
        str(structure.kind),
        f"{int(structure.milepost) / 100:.2f}",
        _text(None if structure.clearance is None else int(structure.clearance)),
        _text(None if structure.rating is None else int(structure.rating)),
        structure.owner,
        str(structure.notice_days) if structure.notice_days else "",
    )


def write_all(office: Office, folder: Path) -> Written:
    """Write every file into a folder, creating it if it is not there."""
    folder.mkdir(parents=True, exist_ok=True)
    if not folder.is_dir():
        raise BadValueError("folder", str(folder), "is not a directory")
    network = office.roadway.network()
    counts = {
        "carriers": write_rows(
            folder / FILES["carriers"],
            COLUMNS["carriers"],
            [row_of_carrier(one) for one in office.carriers.all()],
        ),
        "nodes": write_rows(
            folder / FILES["nodes"],
            COLUMNS["nodes"],
            [row_of_node(one) for one in network.nodes.values()],
        ),
        "segments": write_rows(
            folder / FILES["segments"],
            COLUMNS["segments"],
            [row_of_segment(one) for one in network.segments.values()],
        ),
        "structures": write_rows(
            folder / FILES["structures"],
            COLUMNS["structures"],
            [row_of_structure(one) for one in office.roadway.structures()],
        ),
    }
    return Written(**counts)
