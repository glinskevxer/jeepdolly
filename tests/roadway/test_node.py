import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.roadway.node import MAX_COUNTY, MAX_NAME, Node


def a_node(**over: object) -> Node:
    """A junction on the map, with any part of it swapped out."""
    kw: dict[str, object] = {
        "code": "JCT-12",
        "name": "US 12 at Sixmile Road",
        "county": "Missoula",
    }
    kw.update(over)
    return Node(**kw)  # type: ignore[arg-type]


def test_node_normalises_the_code():
    assert a_node(code="jct-12").code == "JCT-12"


def test_node_collapses_whitespace_in_the_name():
    assert a_node(name="US 12   at  Sixmile").name == "US 12 at Sixmile"


def test_node_refuses_an_empty_name():
    with pytest.raises(BadValueError):
        a_node(name="  ")


def test_node_refuses_an_empty_county():
    with pytest.raises(BadValueError):
        a_node(county="")


def test_node_refuses_a_name_that_is_too_long():
    with pytest.raises(BadValueError):
        a_node(name="x" * (MAX_NAME + 1))


def test_node_refuses_a_county_that_is_too_long():
    with pytest.raises(BadValueError):
        a_node(county="x" * (MAX_COUNTY + 1))


def test_node_takes_the_longest_name():
    assert len(a_node(name="x" * MAX_NAME).name) == MAX_NAME


def test_node_refuses_a_county_that_is_not_text():
    with pytest.raises(BadValueError):
        a_node(county=12)


def test_node_prints_its_county():
    assert str(a_node()) == "JCT-12 US 12 at Sixmile Road (Missoula)"


def test_nodes_order_by_code():
    first = a_node(code="AAA")
    assert sorted([a_node(), first])[0] is first


def test_nodes_with_the_same_parts_are_equal():
    assert a_node() == a_node()


def test_a_node_cannot_be_written_to():
    with pytest.raises(AttributeError):
        a_node().name = "Other"  # type: ignore[misc]
