import pytest

from jeepdolly.errors import BadValueError, ConflictError, NotFoundError
from jeepdolly.roadway.node import Node
from jeepdolly.roadway.segment import Segment
from jeepdolly.roadway.structure import Structure, StructureKind
from jeepdolly.store.roadway import RoadwayStore
from jeepdolly.units.distance import miles
from jeepdolly.units.length import feet_inches
from jeepdolly.units.mass import pounds


def node(key: str) -> Node:
    return Node(code=key, name=f"junction {key}", county="Missoula")  # type: ignore[arg-type]


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
def store(office):
    """A roadway store with two junctions and one stretch on file."""
    made = RoadwayStore(office)
    made.add_node(node("JCT-A"))
    made.add_node(node("JCT-B"))
    made.add_segment(segment("SEG-AB", "JCT-A", "JCT-B"))
    return made


def test_a_node_round_trips(store):
    assert store.get_node("JCT-A").name == "junction JCT-A"


def test_a_node_is_found_by_a_lower_case_key(store):
    assert store.find_node("jct-a") is not None


def test_add_node_refuses_a_repeat(store):
    with pytest.raises(ConflictError):
        store.add_node(node("JCT-A"))


def test_get_node_raises_on_one_that_is_not_there(store):
    with pytest.raises(NotFoundError):
        store.get_node("JCT-Z")


def test_nodes_are_in_code_order(store):
    store.add_node(node("JCT-0"))
    assert [n.code for n in store.nodes()] == ["JCT-0", "JCT-A", "JCT-B"]


def test_a_segment_round_trips(store):
    read = store.get_segment("SEG-AB")
    assert read.route == "US-12"
    assert int(read.distance) == 1000


def test_a_segment_keeps_its_road_class(store):
    store.add_segment(segment("SEG-IX", "JCT-A", "JCT-B", road_class="interstate"))
    assert str(store.get_segment("SEG-IX").road_class) == "interstate"


def test_a_segment_keeps_its_one_way_flag(store):
    store.add_segment(segment("SEG-OW", "JCT-A", "JCT-B", one_way=True))
    assert store.get_segment("SEG-OW").one_way is True


def test_a_posted_gross_round_trips(store):
    store.add_segment(segment("SEG-PG", "JCT-A", "JCT-B", posted_gross=pounds(48000)))
    assert int(store.get_segment("SEG-PG").posted_gross or 0) == 48000


def test_an_unposted_segment_reads_back_as_none(store):
    assert store.get_segment("SEG-AB").posted_gross is None


def test_add_segment_refuses_a_repeat(store):
    with pytest.raises(ConflictError):
        store.add_segment(segment("SEG-AB", "JCT-A", "JCT-B"))


def test_add_segment_refuses_a_node_that_is_not_there(store):
    with pytest.raises(NotFoundError):
        store.add_segment(segment("SEG-AZ", "JCT-A", "JCT-Z"))


def test_get_segment_raises_on_one_that_is_not_there(store):
    with pytest.raises(NotFoundError):
        store.get_segment("SEG-ZZ")


def test_the_first_structure_reference_is_one(store):
    assert store.next_structure() == "STR-00001"


def test_structure_references_climb(store):
    store.add_structure(
        Structure(
            reference=store.next_structure(),
            segment="SEG-AB",  # type: ignore[arg-type]
            name="Sixmile Creek",
            kind=StructureKind.BRIDGE,
            milepost=miles("4.20"),
            rating=pounds(64000),
        )
    )
    assert store.next_structure() == "STR-00002"


def a_bridge(store, **over: object) -> Structure:
    kw: dict[str, object] = {
        "reference": store.next_structure(),
        "segment": "SEG-AB",
        "name": "Sixmile Creek",
        "kind": StructureKind.BRIDGE,
        "milepost": miles("4.20"),
        "rating": pounds(64000),
    }
    kw.update(over)
    return Structure(**kw)  # type: ignore[arg-type]


def test_a_bridge_round_trips(store):
    made = store.add_structure(a_bridge(store))
    read = store.get_structure(made.reference)
    assert int(read.rating or 0) == 64000
    assert read.clearance is None


def test_an_overhead_round_trips(store):
    made = store.add_structure(
        a_bridge(
            store,
            kind=StructureKind.OVERHEAD,
            rating=None,
            clearance=feet_inches(15, 2),
            name="MRL overhead",
        )
    )
    read = store.get_structure(made.reference)
    assert int(read.clearance or 0) == 182
    assert read.rating is None


def test_add_structure_refuses_a_segment_that_is_not_there(store):
    with pytest.raises(NotFoundError):
        store.add_structure(a_bridge(store, segment="SEG-ZZ"))


def test_add_structure_refuses_a_repeat(store):
    made = store.add_structure(a_bridge(store))
    with pytest.raises(ConflictError):
        store.add_structure(made)


def test_get_structure_raises_on_one_that_is_not_there(store):
    with pytest.raises(NotFoundError):
        store.get_structure("STR-00099")


def test_structures_on_a_segment_are_in_milepost_order(store):
    store.add_structure(a_bridge(store, milepost=miles("9.00")))
    store.add_structure(a_bridge(store, milepost=miles("1.00"), name="Little Creek"))
    assert [s.name for s in store.structures_on("SEG-AB")] == ["Little Creek", "Sixmile Creek"]


def test_structures_on_an_empty_segment(store):
    store.add_segment(segment("SEG-BA", "JCT-B", "JCT-A"))
    assert store.structures_on("SEG-BA") == []


def test_removing_a_segment_takes_its_structures(store):
    store.add_structure(a_bridge(store))
    store.remove_segment("SEG-AB")
    assert store.structures() == []


def test_remove_segment_raises_on_one_that_is_not_there(store):
    with pytest.raises(NotFoundError):
        store.remove_segment("SEG-ZZ")


def test_the_network_comes_back_built(store):
    made = store.network()
    assert made.segment_count == 1
    assert made.connected


def test_the_network_carries_the_structures(store):
    store.add_structure(a_bridge(store))
    assert len(store.network().structures) == 1


def test_a_map_that_drifted_is_caught_on_the_way_out(store, office):
    office.execute("INSERT INTO node (code, name, county) VALUES ('JCT-X', 'x', 'y')")
    office.execute(
        "INSERT INTO segment (code, start_node, end_node, route, distance, road_class)"
        " VALUES ('SEG-XX', 'JCT-X', 'JCT-A', 'US-12', 100, 'state')"
    )
    office.execute("DELETE FROM structure")
    # Sqlite ignores this pragma inside a transaction, so the pending inserts
    # have to be written out before the key check can be turned off.
    office.commit()
    office.execute("PRAGMA foreign_keys = OFF")
    office.execute("DELETE FROM node WHERE code = 'JCT-X'")
    with pytest.raises(BadValueError):
        store.network()


def test_counts_reports_all_three(store):
    store.add_structure(a_bridge(store))
    assert store.counts() == (2, 1, 1)


def test_the_office_hands_out_a_roadway_store(office):
    from jeepdolly.store.office import Office

    assert isinstance(Office(office).roadway, RoadwayStore)
