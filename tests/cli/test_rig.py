from collections.abc import Callable

import pytest
from click.testing import Result


@pytest.fixture
def with_carrier(run: Callable[..., Result]) -> Callable[..., Result]:
    """An office file with one carrier on it."""
    run(
        "carrier",
        "add",
        "--code",
        "VANCE",
        "--name",
        "Vance Heavy Haul",
        "--usdot",
        "1184062",
        "--state",
        "MT",
    )
    return run


def test_build_records_the_default_rig(with_carrier):
    result = with_carrier("rig", "build", "--carrier", "VANCE", "--name", "3S2")
    assert result.exit_code == 0
    assert "R-00001" in result.output
    assert "5 axles" in result.output


def test_build_refuses_a_carrier_that_is_not_there(run):
    result = run("rig", "build", "--carrier", "NOBODY", "--name", "3S2")
    assert result.exit_code == 1


def test_build_takes_the_axles_one_at_a_time(with_carrier):
    result = with_carrier(
        "rig",
        "build",
        "--carrier",
        "VANCE",
        "--name",
        "3AXLE",
        "--axle",
        "12000,2,11,0",
        "--axle",
        "17000,4,11,15",
        "--axle",
        "17000,4,11,4",
    )
    assert result.exit_code == 0
    assert "3 axles" in result.output


def test_build_refuses_an_axle_with_too_few_fields(with_carrier):
    result = with_carrier(
        "rig", "build", "--carrier", "VANCE", "--name", "BAD", "--axle", "12000,2,11"
    )
    assert result.exit_code == 2


def test_build_refuses_an_axle_field_that_is_not_a_number(with_carrier):
    result = with_carrier(
        "rig", "build", "--carrier", "VANCE", "--name", "BAD", "--axle", "heavy,2,11,0"
    )
    assert result.exit_code == 2


def test_build_takes_a_recorded_day(with_carrier):
    result = with_carrier(
        "rig", "build", "--carrier", "VANCE", "--name", "3S2", "--on", "2025-07-01"
    )
    assert result.exit_code == 0


def test_show_prints_every_axle(with_carrier):
    with_carrier("rig", "build", "--carrier", "VANCE", "--name", "3S2")
    result = with_carrier("rig", "show", "R-00001")
    assert "axle 1: steer" in result.output
    assert "axle 5: fixed" in result.output


def test_show_prints_the_gross_and_wheelbase(with_carrier):
    with_carrier("rig", "build", "--carrier", "VANCE", "--name", "3S2")
    result = with_carrier("rig", "show", "R-00001")
    assert "gross 80,000 lb" in result.output
    assert "wheelbase 53'" in result.output


def test_show_prints_the_spacing_ahead_of_each_axle(with_carrier):
    with_carrier("rig", "build", "--carrier", "VANCE", "--name", "3S2")
    assert "15' ahead" in with_carrier("rig", "show", "R-00001").output


def test_show_raises_on_a_rig_that_is_not_there(with_carrier):
    assert with_carrier("rig", "show", "R-00099").exit_code == 1


def test_list_says_when_there_is_nothing(run):
    assert "no rigs on file" in run("rig", "list").output


def test_list_prints_the_rig(with_carrier):
    with_carrier("rig", "build", "--carrier", "VANCE", "--name", "3S2")
    assert "R-00001" in with_carrier("rig", "list").output


def test_list_filters_by_carrier(with_carrier):
    with_carrier("rig", "build", "--carrier", "VANCE", "--name", "3S2")
    assert "R-00001" in with_carrier("rig", "list", "--carrier", "VANCE").output


def test_list_of_another_carrier_is_empty(with_carrier):
    with_carrier(
        "carrier", "add", "--code", "OTHER", "--name", "Other", "--usdot", "2", "--state", "ID"
    )
    with_carrier("rig", "build", "--carrier", "VANCE", "--name", "3S2")
    assert "no rigs on file" in with_carrier("rig", "list", "--carrier", "OTHER").output


def test_status_counts_the_rigs(with_carrier):
    with_carrier("rig", "build", "--carrier", "VANCE", "--name", "3S2")
    assert "rigs 1" in with_carrier("status").output
