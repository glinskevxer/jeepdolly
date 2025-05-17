from collections.abc import Callable

from click.testing import Result


def two_junctions(run: Callable[..., Result]) -> None:
    """Put the two ends of a stretch on the map."""
    run("road", "node", "--code", "JCT-A", "--name", "Sixmile", "--county", "Missoula")
    run("road", "node", "--code", "JCT-B", "--name", "Lolo", "--county", "Missoula")


def a_stretch(run: Callable[..., Result], **over: str) -> Result:
    """Put one stretch of US 12 on the map."""
    args = {
        "--code": "SEG-AB",
        "--start": "JCT-A",
        "--end": "JCT-B",
        "--route": "US-12",
        "--miles": "14.20",
    }
    args.update(over)
    flat: list[str] = []
    for key, value in args.items():
        flat.extend([key, value])
    return run("road", "segment", *flat)


def test_node_goes_on_the_map(run):
    result = run("road", "node", "--code", "JCT-A", "--name", "Sixmile", "--county", "Missoula")
    assert result.exit_code == 0
    assert "JCT-A" in result.output


def test_node_refuses_a_repeat(run):
    two_junctions(run)
    result = run("road", "node", "--code", "JCT-A", "--name", "x", "--county", "y")
    assert result.exit_code == 1
    assert "already exists" in result.output


def test_segment_goes_on_the_map(run):
    two_junctions(run)
    result = a_stretch(run)
    assert result.exit_code == 0
    assert "14.20 mi" in result.output


def test_segment_refuses_a_junction_that_is_not_there(run):
    result = a_stretch(run)
    assert result.exit_code == 1
    assert "no node" in result.output


def test_segment_refuses_a_route_that_is_not_a_designation(run):
    two_junctions(run)
    result = a_stretch(run, **{"--route": "Sixmile Road"})
    assert result.exit_code == 1


def test_segment_takes_a_road_class(run):
    two_junctions(run)
    assert a_stretch(run, **{"--class": "interstate"}).exit_code == 0


def test_segment_takes_a_posted_gross(run):
    two_junctions(run)
    assert a_stretch(run, **{"--posted": "48,000"}).exit_code == 0


def test_a_one_way_segment_prints_a_single_arrow(run):
    two_junctions(run)
    result = run(
        "road",
        "segment",
        "--code",
        "SEG-AB",
        "--start",
        "JCT-A",
        "--end",
        "JCT-B",
        "--route",
        "US-12",
        "--miles",
        "3.00",
        "--one-way",
    )
    assert "<->" not in result.output


def test_structure_goes_on_a_stretch(run):
    two_junctions(run)
    a_stretch(run)
    result = run(
        "road",
        "structure",
        "--segment",
        "SEG-AB",
        "--name",
        "Sixmile Creek",
        "--milepost",
        "4.20",
        "--rating",
        "64,000",
    )
    assert result.exit_code == 0
    assert "STR-00001" in result.output


def test_an_overhead_takes_a_clearance(run):
    two_junctions(run)
    a_stretch(run)
    result = run(
        "road",
        "structure",
        "--segment",
        "SEG-AB",
        "--name",
        "MRL overhead",
        "--kind",
        "overhead",
        "--milepost",
        "1.10",
        "--clearance",
        "15'2\"",
    )
    assert result.exit_code == 0
    assert "15'2\"" in result.output


def test_a_bridge_refuses_a_clearance(run):
    two_junctions(run)
    a_stretch(run)
    result = run(
        "road",
        "structure",
        "--segment",
        "SEG-AB",
        "--name",
        "x",
        "--milepost",
        "1.00",
        "--clearance",
        "15'",
    )
    assert result.exit_code == 1


def test_structure_refuses_a_stretch_that_is_not_there(run):
    result = run(
        "road", "structure", "--segment", "SEG-ZZ", "--name", "x", "--milepost", "1.00"
    )
    assert result.exit_code == 1


def test_map_says_when_there_is_nothing(run):
    assert "nothing on the map" in run("road", "map").output


def test_map_prints_the_stretches(run):
    two_junctions(run)
    a_stretch(run)
    output = run("road", "map").output
    assert "SEG-AB" in output
    assert "2 junctions, 1 stretches, 0 structures" in output


def test_map_says_the_map_is_joined_up(run):
    two_junctions(run)
    a_stretch(run)
    assert "joined up" in run("road", "map").output


def test_map_notices_an_island(run):
    two_junctions(run)
    a_stretch(run)
    run("road", "node", "--code", "JCT-X", "--name", "island", "--county", "Ravalli")
    assert "not joined up" in run("road", "map").output


def test_map_lists_the_structures(run):
    two_junctions(run)
    a_stretch(run)
    run(
        "road",
        "structure",
        "--segment",
        "SEG-AB",
        "--name",
        "Sixmile Creek",
        "--milepost",
        "4.20",
        "--rating",
        "64,000",
    )
    output = run("road", "map").output
    assert "Sixmile Creek" in output
    assert "64,000 lb" in output


def test_status_counts_the_map(run):
    two_junctions(run)
    a_stretch(run)
    output = run("status").output
    assert "junctions 2" in output
    assert "segments 1" in output
