"""Bulk loading carriers and the map from comma separated files.

The map came from the highway department as three spreadsheets and it changes a
few times a year, so it is loaded rather than typed. The rules are the same as at
the counter: every row goes through the same model constructor a clerk's typing
would, and a bad row fails the whole import rather than being skipped.

Failing the whole import is the important decision. A partial load leaves the map
in a state where a route exists and the bridge on it does not, and the office has
no way to know that happened. So the import runs inside one transaction, and a
row the office would not accept from a clerk stops it.

Errors carry the file and the line number, because the first thing anybody asks
about a failed import is which row.
"""

from __future__ import annotations

import csv
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from jeepdolly.errors import BadValueError, JeepdollyError
from jeepdolly.party.carrier import Carrier
from jeepdolly.roadway.node import Node
from jeepdolly.roadway.segment import RoadClass, Segment
from jeepdolly.roadway.structure import Structure, StructureKind
from jeepdolly.store.office import Office
from jeepdolly.units.distance import parse_distance
from jeepdolly.units.length import parse_length
from jeepdolly.units.mass import parse_weight

__all__ = [
    "FILES",
    "Loaded",
    "load_all",
    "load_carriers",
    "load_nodes",
    "load_segments",
    "load_structures",
    "read_rows",
]

#: The file each kind of record is read from.
FILES = {
    "carriers": "carriers.csv",
    "nodes": "nodes.csv",
    "segments": "segments.csv",
    "structures": "structures.csv",
}


@dataclass(frozen=True, slots=True)
class Loaded:
    """How many of each kind of record went in."""

    carriers: int = 0
    nodes: int = 0
    segments: int = 0
    structures: int = 0

    @property
    def total(self) -> int:
        """Every record loaded."""
        return self.carriers + self.nodes + self.segments + self.structures

    def __str__(self) -> str:
        return (
            f"{self.carriers} carriers, {self.nodes} junctions,"
            f" {self.segments} stretches, {self.structures} structures"
        )


def read_rows(path: Path) -> Iterator[tuple[int, dict[str, str]]]:
    """Every row of one file, with the line it came from.

    Blank fields come back as empty strings rather than ``None``, which is what
    the model constructors expect for an absent optional.
    """
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise BadValueError("file", path.name, "has no header row")
        for number, row in enumerate(reader, start=2):
            yield number, {key: (value or "").strip() for key, value in row.items()}


def _at(path: Path, line: int, exc: JeepdollyError) -> BadValueError:
    """Wrap a row failure with the file and line it came from."""
    return BadValueError("row", f"{path.name}:{line}", str(exc))


def load_carriers(office: Office, path: Path) -> int:
    """Load the carrier file."""
    count = 0
    for line, row in read_rows(path):
        try:
            office.carriers.add(
                Carrier(
                    code=row["code"],  # type: ignore[arg-type]
                    name=row["name"],
                    usdot=int(row["usdot"]),
                    home_state=row["home_state"],
                    active=row.get("active", "1") not in {"0", "no", "false"},
                )
            )
        except JeepdollyError as exc:
            raise _at(path, line, exc) from exc
        except (KeyError, ValueError) as exc:
            raise BadValueError("row", f"{path.name}:{line}", str(exc)) from exc
        count += 1
    return count


def load_nodes(office: Office, path: Path) -> int:
    """Load the junction file."""
    count = 0
    for line, row in read_rows(path):
        try:
            office.roadway.add_node(
                Node(code=row["code"], name=row["name"], county=row["county"])  # type: ignore[arg-type]
            )
        except JeepdollyError as exc:
            raise _at(path, line, exc) from exc
        except KeyError as exc:
            raise BadValueError("row", f"{path.name}:{line}", str(exc)) from exc
        count += 1
    return count


def load_segments(office: Office, path: Path) -> int:
    """Load the stretch file."""
    count = 0
    for line, row in read_rows(path):
        try:
            office.roadway.add_segment(
                Segment(
                    code=row["code"],  # type: ignore[arg-type]
                    start=row["start"],  # type: ignore[arg-type]
                    end=row["end"],  # type: ignore[arg-type]
                    route=row["route"],
                    distance=parse_distance(row["miles"]),
                    road_class=RoadClass(row.get("class") or "state"),
                    one_way=row.get("one_way", "") in {"1", "yes", "true"},
                    posted_gross=parse_weight(row["posted"]) if row.get("posted") else None,
                    max_width=parse_length(row["max_width"]) if row.get("max_width") else None,
                    max_height=(
                        parse_length(row["max_height"]) if row.get("max_height") else None
                    ),
                )
            )
        except JeepdollyError as exc:
            raise _at(path, line, exc) from exc
        except ValueError as exc:
            raise BadValueError("row", f"{path.name}:{line}", str(exc)) from exc
        except KeyError as exc:
            raise BadValueError("row", f"{path.name}:{line}", str(exc)) from exc
        count += 1
    return count


def load_structures(office: Office, path: Path) -> int:
    """Load the structure file."""
    count = 0
    for line, row in read_rows(path):
        try:
            office.roadway.add_structure(
                Structure(
                    reference=office.roadway.next_structure(),
                    segment=row["segment"],  # type: ignore[arg-type]
                    name=row["name"],
                    kind=StructureKind(row.get("kind") or "bridge"),
                    milepost=parse_distance(row["milepost"]),
                    clearance=parse_length(row["clearance"]) if row.get("clearance") else None,
                    rating=parse_weight(row["rating"]) if row.get("rating") else None,
                )
            )
        except JeepdollyError as exc:
            raise _at(path, line, exc) from exc
        except ValueError as exc:
            raise BadValueError("row", f"{path.name}:{line}", str(exc)) from exc
        except KeyError as exc:
            raise BadValueError("row", f"{path.name}:{line}", str(exc)) from exc
        count += 1
    return count


def load_all(office: Office, folder: Path) -> Loaded:
    """Load every file that is present, in dependency order, in one transaction.

    Junctions before stretches and stretches before structures, because each of
    those refuses a row pointing at something that is not there yet. A file that
    is absent is skipped; a file that is present and bad stops everything.
    """
    if not folder.is_dir():
        raise BadValueError("folder", str(folder), "is not a directory")
    counts: dict[str, int] = {}
    loaders = (
        ("carriers", load_carriers),
        ("nodes", load_nodes),
        ("segments", load_segments),
        ("structures", load_structures),
    )
    with office.writing():
        for name, loader in loaders:
            path = folder / FILES[name]
            counts[name] = loader(office, path) if path.exists() else 0
    return Loaded(**counts)
