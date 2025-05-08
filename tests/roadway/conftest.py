"""A small map the roadway and route suites share."""

import pytest

from jeepdolly.roadway.network import Network, build
from jeepdolly.roadway.node import Node
from jeepdolly.roadway.segment import Segment
from jeepdolly.roadway.structure import Structure, StructureKind
from jeepdolly.units.distance import miles
from jeepdolly.units.length import feet_inches
from jeepdolly.units.mass import pounds


def node(key: str, name: str = "", county: str = "Missoula") -> Node:
    return Node(code=key, name=name or f"junction {key}", county=county)  # type: ignore[arg-type]


def segment(key: str, start: str, end: str, **over: object) -> Segment:
    kw: dict[str, object] = {
        "code": key,
        "start": start,
        "end": end,
        "route": "US-12",
        "distance": miles("10.00"),
    }
    kw.update(over)
    return Segment(**kw)  # type: ignore[arg-type]


@pytest.fixture
def small_map() -> Network:
    """Four junctions in a line with a parallel loop, and two structures.

    A --SEG-AB-- B --SEG-BC-- C --SEG-CD-- D
                 \\--------SEG-BD---------/
    """
    return build(
        nodes=[node("JCT-A"), node("JCT-B"), node("JCT-C"), node("JCT-D")],
        segments=[
            segment("SEG-AB", "JCT-A", "JCT-B", distance=miles("12.00")),
            segment("SEG-BC", "JCT-B", "JCT-C", distance=miles("8.50")),
            segment("SEG-CD", "JCT-C", "JCT-D", distance=miles("6.00")),
            segment("SEG-BD", "JCT-B", "JCT-D", route="SR-200", distance=miles("31.00")),
        ],
        structures=[
            Structure(
                reference="STR-00001",  # type: ignore[arg-type]
                segment="SEG-BC",  # type: ignore[arg-type]
                name="Sixmile Creek",
                kind=StructureKind.BRIDGE,
                milepost=miles("4.20"),
                rating=pounds(64000),
            ),
            Structure(
                reference="STR-00002",  # type: ignore[arg-type]
                segment="SEG-BC",  # type: ignore[arg-type]
                name="MRL overhead",
                kind=StructureKind.OVERHEAD,
                milepost=miles("1.10"),
                clearance=feet_inches(15, 2),
            ),
        ],
    )
