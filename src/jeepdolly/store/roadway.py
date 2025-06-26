"""Reading and writing the map.

Three tables and one thing worth knowing: ``network`` reads all three and hands
back a built ``Network``, which runs every consistency check on the way out. So
a map that has drifted out of shape in the file is caught the first time
somebody asks for it rather than the first time somebody routes across the part
that drifted.

That means ``network`` is not cheap. It is called once at the top of a routing
job and the result is passed down, never called inside a loop.
"""

from __future__ import annotations

import sqlite3
from typing import ClassVar

from jeepdolly.errors import NotFoundError
from jeepdolly.ids.reference import STRUCTURE, Code, Serial, code, serial
from jeepdolly.roadway.network import Network, build
from jeepdolly.roadway.node import Node
from jeepdolly.roadway.segment import RoadClass, Segment
from jeepdolly.roadway.structure import Structure, StructureKind
from jeepdolly.store.repo import Repository
from jeepdolly.store.sqlite import rows, scalar
from jeepdolly.units.distance import hundredths
from jeepdolly.units.length import inches
from jeepdolly.units.mass import pounds

__all__ = [
    "NodeStore",
    "RoadwayStore",
    "SegmentStore",
    "StructureStore",
    "node_from_row",
    "segment_from_row",
    "structure_from_row",
]


def node_from_row(row: sqlite3.Row) -> Node:
    """Build a junction out of one row."""
    return Node(code=Code(row["code"]), name=row["name"], county=row["county"])


def segment_from_row(row: sqlite3.Row) -> Segment:
    """Build a stretch out of one row."""
    posted = row["posted_gross"]
    return Segment(
        code=Code(row["code"]),
        start=Code(row["start_node"]),
        end=Code(row["end_node"]),
        route=row["route"],
        distance=hundredths(int(row["distance"])),
        road_class=RoadClass(row["road_class"]),
        one_way=bool(row["one_way"]),
        posted_gross=None if posted is None else pounds(int(posted)),
    )


def structure_from_row(row: sqlite3.Row) -> Structure:
    """Build a structure out of one row."""
    clearance = row["clearance"]
    rating = row["rating"]
    return Structure(
        reference=Serial(row["reference"]),
        segment=Code(row["segment_code"]),
        name=row["name"],
        kind=StructureKind(row["kind"]),
        milepost=hundredths(int(row["milepost"])),
        clearance=None if clearance is None else inches(int(clearance)),
        rating=None if rating is None else pounds(int(rating)),
    )


class NodeStore(Repository[Node]):
    """The junctions on the map."""

    table: ClassVar[str] = "node"
    key_column: ClassVar[str] = "code"
    kind: ClassVar[str] = "node"
    order_by: ClassVar[str] = "code"
    columns: ClassVar[tuple[str, ...]] = ("code", "name", "county")

    def normalise(self, key: str) -> str:
        return str(code(str(key)))

    def from_row(self, row: sqlite3.Row) -> Node:
        return node_from_row(row)

    def to_row(self, item: Node) -> tuple[object, ...]:
        return (str(item.code), item.name, item.county)

    def key_of(self, item: Node) -> str:
        return str(item.code)


class SegmentStore(Repository[Segment]):
    """The stretches between the junctions."""

    table: ClassVar[str] = "segment"
    key_column: ClassVar[str] = "code"
    kind: ClassVar[str] = "segment"
    order_by: ClassVar[str] = "code"
    columns: ClassVar[tuple[str, ...]] = (
        "code",
        "start_node",
        "end_node",
        "route",
        "distance",
        "road_class",
        "one_way",
        "posted_gross",
    )

    def normalise(self, key: str) -> str:
        return str(code(str(key)))

    def from_row(self, row: sqlite3.Row) -> Segment:
        return segment_from_row(row)

    def to_row(self, item: Segment) -> tuple[object, ...]:
        return (
            str(item.code),
            str(item.start),
            str(item.end),
            item.route,
            int(item.distance),
            str(item.road_class),
            int(item.one_way),
            None if item.posted_gross is None else int(item.posted_gross),
        )

    def key_of(self, item: Segment) -> str:
        return str(item.code)

    def before_add(self, item: Segment) -> None:
        """Both ends have to be junctions the map already knows."""
        for end in (item.start, item.end):
            if NodeStore(self.connection).find(str(end)) is None:
                raise NotFoundError("node", str(end))


class StructureStore(Repository[Structure]):
    """The bridges and overheads built on the stretches."""

    table: ClassVar[str] = "structure"
    key_column: ClassVar[str] = "reference"
    kind: ClassVar[str] = "structure"
    order_by: ClassVar[str] = "reference"
    columns: ClassVar[tuple[str, ...]] = (
        "reference",
        "segment_code",
        "name",
        "kind",
        "milepost",
        "clearance",
        "rating",
    )

    def normalise(self, key: str) -> str:
        return str(serial(str(key)))

    def from_row(self, row: sqlite3.Row) -> Structure:
        return structure_from_row(row)

    def to_row(self, item: Structure) -> tuple[object, ...]:
        return (
            str(item.reference),
            str(item.segment),
            item.name,
            str(item.kind),
            int(item.milepost),
            None if item.clearance is None else int(item.clearance),
            None if item.rating is None else int(item.rating),
        )

    def key_of(self, item: Structure) -> str:
        return str(item.reference)

    def before_add(self, item: Structure) -> None:
        """The stretch it sits on has to be on the map."""
        if SegmentStore(self.connection).find(str(item.segment)) is None:
            raise NotFoundError("segment", str(item.segment))


class RoadwayStore:
    """The junctions, stretches and structures the office has mapped.

    Three repositories behind one handle, because a clerk thinks about the map
    and not about the three tables it happens to live in.
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.nodes_repo = NodeStore(connection)
        self.segments_repo = SegmentStore(connection)
        self.structures_repo = StructureStore(connection)

    def add_node(self, node: Node) -> Node:
        """Put a junction on the map."""
        return self.nodes_repo.add(node)

    def find_node(self, key: str) -> Node | None:
        """One junction by code, or ``None``."""
        return self.nodes_repo.find(key)

    def get_node(self, key: str) -> Node:
        """One junction by code, raising if it is not there."""
        return self.nodes_repo.get(key)

    def nodes(self) -> list[Node]:
        """Every junction, in code order."""
        return self.nodes_repo.all()

    def add_segment(self, segment: Segment) -> Segment:
        """Put a stretch on the map."""
        return self.segments_repo.add(segment)

    def find_segment(self, key: str) -> Segment | None:
        """One stretch by code, or ``None``."""
        return self.segments_repo.find(key)

    def get_segment(self, key: str) -> Segment:
        """One stretch by code, raising if it is not there."""
        return self.segments_repo.get(key)

    def segments(self) -> list[Segment]:
        """Every stretch, in code order."""
        return self.segments_repo.all()

    def next_structure(self) -> Serial:
        """The reference the next structure will be filed under."""
        highest = scalar(self.connection, "SELECT max(reference) FROM structure")
        if highest is None:
            return STRUCTURE.format(1)
        return STRUCTURE.format(STRUCTURE.number(str(highest)) + 1)

    def add_structure(self, structure: Structure) -> Structure:
        """Put something in the way on a stretch."""
        return self.structures_repo.add(structure)

    def find_structure(self, key: str) -> Structure | None:
        """One structure by reference, or ``None``."""
        return self.structures_repo.find(key)

    def get_structure(self, key: str) -> Structure:
        """One structure by reference, raising if it is not there."""
        return self.structures_repo.get(key)

    def structures(self) -> list[Structure]:
        """Every structure, in reference order."""
        return self.structures_repo.all()

    def structures_on(self, key: str) -> list[Structure]:
        """Everything in the way on one stretch, by milepost."""
        return [
            structure_from_row(row)
            for row in rows(
                self.connection,
                "SELECT * FROM structure WHERE segment_code = ? ORDER BY milepost, reference",
                (str(code(str(key))),),
            )
        ]

    def remove_segment(self, key: str) -> None:
        """Take a stretch off the map, and everything on it."""
        self.segments_repo.remove(key)

    def network(self) -> Network:
        """Read the whole map and check it on the way out."""
        return build(self.nodes(), self.segments(), self.structures())

    def counts(self) -> tuple[int, int, int]:
        """How many junctions, stretches and structures are on file."""
        return (
            self.nodes_repo.count(),
            self.segments_repo.count(),
            self.structures_repo.count(),
        )
