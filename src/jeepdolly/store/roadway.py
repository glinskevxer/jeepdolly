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

from jeepdolly.errors import ConflictError, NotFoundError
from jeepdolly.ids.reference import STRUCTURE, Code, Serial, code, serial
from jeepdolly.roadway.network import Network, build
from jeepdolly.roadway.node import Node
from jeepdolly.roadway.segment import RoadClass, Segment
from jeepdolly.roadway.structure import Structure, StructureKind
from jeepdolly.store.sqlite import maybe_one, one, rows, scalar
from jeepdolly.units.distance import hundredths
from jeepdolly.units.length import inches
from jeepdolly.units.mass import pounds

__all__ = ["RoadwayStore", "node_from_row", "segment_from_row", "structure_from_row"]


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


class RoadwayStore:
    """The junctions, stretches and structures the office has mapped."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def add_node(self, node: Node) -> Node:
        """Put a junction on the map."""
        if self.find_node(str(node.code)) is not None:
            raise ConflictError("node", node.code)
        self.connection.execute(
            "INSERT INTO node (code, name, county) VALUES (?, ?, ?)",
            (str(node.code), node.name, node.county),
        )
        return node

    def find_node(self, key: str) -> Node | None:
        """One junction by code, or ``None``."""
        row = maybe_one(
            self.connection, "SELECT * FROM node WHERE code = ?", (str(code(str(key))),)
        )
        return None if row is None else node_from_row(row)

    def get_node(self, key: str) -> Node:
        """One junction by code, raising if it is not there."""
        row = one(
            self.connection,
            "SELECT * FROM node WHERE code = ?",
            (str(code(str(key))),),
            kind="node",
        )
        return node_from_row(row)

    def nodes(self) -> list[Node]:
        """Every junction, in code order."""
        return [
            node_from_row(row)
            for row in rows(self.connection, "SELECT * FROM node ORDER BY code")
        ]

    def add_segment(self, segment: Segment) -> Segment:
        """Put a stretch on the map."""
        if self.find_segment(str(segment.code)) is not None:
            raise ConflictError("segment", segment.code)
        for end in (segment.start, segment.end):
            if self.find_node(str(end)) is None:
                raise NotFoundError("node", str(end))
        self.connection.execute(
            "INSERT INTO segment (code, start_node, end_node, route, distance,"
            " road_class, one_way, posted_gross) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(segment.code),
                str(segment.start),
                str(segment.end),
                segment.route,
                int(segment.distance),
                str(segment.road_class),
                int(segment.one_way),
                None if segment.posted_gross is None else int(segment.posted_gross),
            ),
        )
        return segment

    def find_segment(self, key: str) -> Segment | None:
        """One stretch by code, or ``None``."""
        row = maybe_one(
            self.connection, "SELECT * FROM segment WHERE code = ?", (str(code(str(key))),)
        )
        return None if row is None else segment_from_row(row)

    def get_segment(self, key: str) -> Segment:
        """One stretch by code, raising if it is not there."""
        row = one(
            self.connection,
            "SELECT * FROM segment WHERE code = ?",
            (str(code(str(key))),),
            kind="segment",
        )
        return segment_from_row(row)

    def segments(self) -> list[Segment]:
        """Every stretch, in code order."""
        return [
            segment_from_row(row)
            for row in rows(self.connection, "SELECT * FROM segment ORDER BY code")
        ]

    def next_structure(self) -> Serial:
        """The reference the next structure will be filed under."""
        highest = scalar(self.connection, "SELECT max(reference) FROM structure")
        if highest is None:
            return STRUCTURE.format(1)
        return STRUCTURE.format(STRUCTURE.number(str(highest)) + 1)

    def add_structure(self, structure: Structure) -> Structure:
        """Put something in the way on a stretch."""
        if self.find_structure(str(structure.reference)) is not None:
            raise ConflictError("structure", structure.reference)
        if self.find_segment(str(structure.segment)) is None:
            raise NotFoundError("segment", str(structure.segment))
        self.connection.execute(
            "INSERT INTO structure (reference, segment_code, name, kind, milepost,"
            " clearance, rating) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(structure.reference),
                str(structure.segment),
                structure.name,
                str(structure.kind),
                int(structure.milepost),
                None if structure.clearance is None else int(structure.clearance),
                None if structure.rating is None else int(structure.rating),
            ),
        )
        return structure

    def find_structure(self, key: str) -> Structure | None:
        """One structure by reference, or ``None``."""
        row = maybe_one(
            self.connection,
            "SELECT * FROM structure WHERE reference = ?",
            (str(serial(str(key))),),
        )
        return None if row is None else structure_from_row(row)

    def get_structure(self, key: str) -> Structure:
        """One structure by reference, raising if it is not there."""
        row = one(
            self.connection,
            "SELECT * FROM structure WHERE reference = ?",
            (str(serial(str(key))),),
            kind="structure",
        )
        return structure_from_row(row)

    def structures(self) -> list[Structure]:
        """Every structure, in reference order."""
        return [
            structure_from_row(row)
            for row in rows(self.connection, "SELECT * FROM structure ORDER BY reference")
        ]

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
        self.get_segment(key)
        self.connection.execute("DELETE FROM segment WHERE code = ?", (str(code(str(key))),))

    def network(self) -> Network:
        """Read the whole map and check it on the way out."""
        return build(self.nodes(), self.segments(), self.structures())

    def counts(self) -> tuple[int, int, int]:
        """How many junctions, stretches and structures are on file."""
        return (
            int(scalar(self.connection, "SELECT count(*) FROM node") or 0),
            int(scalar(self.connection, "SELECT count(*) FROM segment") or 0),
            int(scalar(self.connection, "SELECT count(*) FROM structure") or 0),
        )
