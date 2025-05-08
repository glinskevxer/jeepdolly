import pytest

from jeepdolly.errors import BadValueError, NotFoundError
from jeepdolly.roadway.network import build
from jeepdolly.roadway.structure import Structure, StructureKind
from jeepdolly.units.distance import miles
from jeepdolly.units.mass import pounds

from .conftest import node, segment


def test_the_map_counts_its_parts(small_map):
    assert small_map.node_count == 4
    assert small_map.segment_count == 4


def test_the_map_is_its_segments(small_map):
    assert len(small_map) == 4
    assert [s.code for s in small_map] == ["SEG-AB", "SEG-BC", "SEG-BD", "SEG-CD"]


def test_node_finds_a_junction(small_map):
    assert small_map.node("JCT-A").code == "JCT-A"


def test_node_normalises_the_key(small_map):
    assert small_map.node("jct-a").code == "JCT-A"


def test_node_raises_on_one_that_is_not_there(small_map):
    with pytest.raises(NotFoundError):
        small_map.node("JCT-Z")


def test_segment_finds_a_stretch(small_map):
    assert small_map.segment("SEG-AB").route == "US-12"


def test_segment_raises_on_one_that_is_not_there(small_map):
    with pytest.raises(NotFoundError):
        small_map.segment("SEG-ZZ")


def test_links_out_of_an_end_node(small_map):
    assert [str(link.segment.code) for link in small_map.links("JCT-A")] == ["SEG-AB"]


def test_links_out_of_a_middle_node(small_map):
    assert [str(link.segment.code) for link in small_map.links("JCT-B")] == [
        "SEG-AB",
        "SEG-BC",
        "SEG-BD",
    ]


def test_a_link_says_where_it_lands(small_map):
    landed = {link.to_node for link in small_map.links("JCT-B")}
    assert landed == {"JCT-A", "JCT-C", "JCT-D"}


def test_links_raises_on_a_node_that_is_not_there(small_map):
    with pytest.raises(NotFoundError):
        small_map.links("JCT-Z")


def test_a_one_way_segment_only_links_forward():
    made = build(
        nodes=[node("JCT-A"), node("JCT-B")],
        segments=[segment("SEG-AB", "JCT-A", "JCT-B", one_way=True)],
    )
    assert len(made.links("JCT-A")) == 1
    assert made.links("JCT-B") == ()


def test_between_finds_the_segment(small_map):
    assert [s.code for s in small_map.between("JCT-B", "JCT-D")] == ["SEG-BD"]


def test_between_finds_nothing_where_there_is_no_link(small_map):
    assert small_map.between("JCT-A", "JCT-D") == ()


def test_between_works_backwards_on_a_two_way(small_map):
    assert [s.code for s in small_map.between("JCT-B", "JCT-A")] == ["SEG-AB"]


def test_structures_on_a_segment_are_in_milepost_order(small_map):
    found = small_map.structures_on("SEG-BC")
    assert [s.reference for s in found] == ["STR-00002", "STR-00001"]


def test_structures_on_a_clear_segment_is_empty(small_map):
    assert small_map.structures_on("SEG-AB") == ()


def test_structures_on_raises_for_a_segment_that_is_not_there(small_map):
    with pytest.raises(NotFoundError):
        small_map.structures_on("SEG-ZZ")


def test_reachable_from_an_end_covers_the_map(small_map):
    assert small_map.reachable("JCT-A") == {"JCT-A", "JCT-B", "JCT-C", "JCT-D"}


def test_reachable_raises_on_a_node_that_is_not_there(small_map):
    with pytest.raises(NotFoundError):
        small_map.reachable("JCT-Z")


def test_a_joined_up_map_is_connected(small_map):
    assert small_map.connected


def test_an_empty_map_is_connected():
    assert build(nodes=[], segments=[]).connected


def test_an_island_makes_the_map_disconnected():
    made = build(
        nodes=[node("JCT-A"), node("JCT-B"), node("JCT-X")],
        segments=[segment("SEG-AB", "JCT-A", "JCT-B")],
    )
    assert not made.connected


def test_build_refuses_a_repeated_node():
    with pytest.raises(BadValueError):
        build(nodes=[node("JCT-A"), node("JCT-A")], segments=[])


def test_build_refuses_a_repeated_segment():
    with pytest.raises(BadValueError):
        build(
            nodes=[node("JCT-A"), node("JCT-B")],
            segments=[
                segment("SEG-AB", "JCT-A", "JCT-B"),
                segment("SEG-AB", "JCT-B", "JCT-A"),
            ],
        )


def test_build_refuses_a_segment_pointing_at_no_node():
    with pytest.raises(BadValueError):
        build(nodes=[node("JCT-A")], segments=[segment("SEG-AB", "JCT-A", "JCT-B")])


def test_build_refuses_a_structure_on_no_segment():
    stray = Structure(
        reference="STR-00009",  # type: ignore[arg-type]
        segment="SEG-ZZ",  # type: ignore[arg-type]
        name="nowhere",
        kind=StructureKind.BRIDGE,
        milepost=miles("1.00"),
        rating=pounds(50000),
    )
    with pytest.raises(BadValueError):
        build(
            nodes=[node("JCT-A"), node("JCT-B")],
            segments=[segment("SEG-AB", "JCT-A", "JCT-B")],
            structures=[stray],
        )


def test_build_refuses_a_repeated_structure(small_map):
    first = small_map.structures[0]
    with pytest.raises(BadValueError):
        build(
            nodes=list(small_map.nodes.values()),
            segments=list(small_map.segments.values()),
            structures=[first, first],
        )


def test_a_link_prints_where_it_goes(small_map):
    assert str(small_map.links("JCT-A")[0]) == "SEG-AB to JCT-B"


def test_the_map_holds_every_structure(small_map):
    assert len(small_map.structures) == 2
