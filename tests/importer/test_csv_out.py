import csv

import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.importer.csv_in import COLUMNS, FILES, load_all
from jeepdolly.importer.csv_out import (
    Written,
    row_of_carrier,
    row_of_structure,
    write_all,
    write_rows,
)
from jeepdolly.party.carrier import Carrier
from jeepdolly.roadway.node import Node
from jeepdolly.roadway.segment import Segment
from jeepdolly.roadway.structure import Structure, StructureKind
from jeepdolly.store.office import Office, opened_new_office
from jeepdolly.units.distance import miles
from jeepdolly.units.length import feet_inches
from jeepdolly.units.mass import pounds


def stock(office: Office) -> None:
    """A carrier, three junctions, two stretches and two structures."""
    with office.writing():
        office.carriers.add(
            Carrier(code="VANCE", name="Vance Heavy Haul", usdot=1184062, home_state="MT")  # type: ignore[arg-type]
        )
        for key in ("JCT-A", "JCT-B", "JCT-C"):
            office.roadway.add_node(
                Node(code=key, name=key.lower(), county="Missoula")  # type: ignore[arg-type]
            )
        office.roadway.add_segment(
            Segment(
                code="SEG-AB",  # type: ignore[arg-type]
                start="JCT-A",  # type: ignore[arg-type]
                end="JCT-B",  # type: ignore[arg-type]
                route="US-12",
                distance=miles("12.00"),
            )
        )
        office.roadway.add_segment(
            Segment(
                code="SEG-BC",  # type: ignore[arg-type]
                start="JCT-B",  # type: ignore[arg-type]
                end="JCT-C",  # type: ignore[arg-type]
                route="SR-200",
                distance=miles("8.50"),
                posted_gross=pounds(48000),
            )
        )
        office.roadway.add_structure(
            Structure(
                reference=office.roadway.next_structure(),
                segment="SEG-AB",  # type: ignore[arg-type]
                name="Sixmile Creek",
                kind=StructureKind.BRIDGE,
                milepost=miles("4.20"),
                rating=pounds(64000),
            )
        )
        office.roadway.add_structure(
            Structure(
                reference=office.roadway.next_structure(),
                segment="SEG-BC",  # type: ignore[arg-type]
                name="MRL overhead",
                kind=StructureKind.OVERHEAD,
                milepost=miles("1.10"),
                clearance=feet_inches(15, 2),
                owner="Montana Rail Link",
                notice_days=10,
            )
        )


@pytest.fixture
def stocked(tmp_path):
    """A folder holding a whole office written out as csv."""
    with opened_new_office() as office:
        stock(office)
        write_all(office, tmp_path / "out")
    return tmp_path / "out"


def test_writing_a_file_returns_its_row_count(tmp_path):
    written = write_rows(tmp_path / "x.csv", ("a", "b"), [("1", "2"), ("3", "4")])
    assert written == 2


def test_a_written_file_carries_its_header(tmp_path):
    write_rows(tmp_path / "x.csv", ("a", "b"), [("1", "2")])
    with (tmp_path / "x.csv").open(encoding="utf-8") as handle:
        assert next(csv.reader(handle)) == ["a", "b"]


def test_a_row_of_the_wrong_width_is_refused(tmp_path):
    with pytest.raises(BadValueError):
        write_rows(tmp_path / "x.csv", ("a", "b"), [("1",)])


def test_a_file_with_no_columns_is_refused(tmp_path):
    with pytest.raises(BadValueError):
        write_rows(tmp_path / "x.csv", (), [])


def test_every_file_the_loader_reads_is_written(stocked):
    for name in FILES.values():
        assert (stocked / name).exists()


def test_each_file_carries_the_loaders_own_columns(stocked):
    for key, name in FILES.items():
        with (stocked / name).open(encoding="utf-8") as handle:
            assert next(csv.reader(handle)) == list(COLUMNS[key])


def test_the_counts_come_back_on_the_result(tmp_path):
    with opened_new_office() as office:
        stock(office)
        got = write_all(office, tmp_path / "out")
    assert got.carriers == 1
    assert got.nodes == 3
    assert got.segments == 2
    assert got.structures == 2


def test_the_result_adds_up_its_own_total():
    assert Written(carriers=1, nodes=3, segments=2, structures=2).total == 8


def test_the_result_prints_what_it_wrote():
    assert "3 junctions" in str(Written(nodes=3))


def test_an_export_loads_straight_back_in(stocked):
    with opened_new_office() as office:
        got = load_all(office, stocked)
    assert got.carriers == 1
    assert got.nodes == 3
    assert got.segments == 2
    assert got.structures == 2


def test_a_round_trip_keeps_the_carrier(stocked):
    with opened_new_office() as office:
        load_all(office, stocked)
        assert office.carriers.get("VANCE").usdot == 1184062


def test_a_round_trip_keeps_a_posted_stretch(stocked):
    with opened_new_office() as office:
        load_all(office, stocked)
        found = office.roadway.get_segment("SEG-BC")
        assert found.posted_gross is not None
        assert int(found.posted_gross) == 48000


def test_a_round_trip_keeps_the_mileage(stocked):
    with opened_new_office() as office:
        load_all(office, stocked)
        assert int(office.roadway.get_segment("SEG-AB").distance) == 1200


def test_a_round_trip_keeps_a_clearance(stocked):
    with opened_new_office() as office:
        load_all(office, stocked)
        found = office.roadway.structures_on("SEG-BC")[0]
        assert found.clearance is not None
        assert int(found.clearance) == 182


def test_a_round_trip_keeps_the_owner_and_the_lead_time(stocked):
    with opened_new_office() as office:
        load_all(office, stocked)
        found = office.roadway.structures_on("SEG-BC")[0]
        assert found.owner == "Montana Rail Link"
        assert found.notice_days == 10


def test_a_structure_with_nobody_on_file_round_trips_blank(stocked):
    with opened_new_office() as office:
        load_all(office, stocked)
        found = office.roadway.structures_on("SEG-AB")[0]
        assert found.owner == ""
        assert found.notice_days == 0


def test_a_structure_row_leaves_its_reference_out():
    made = Structure(
        reference="ST-00001",  # type: ignore[arg-type]
        segment="SEG-AB",  # type: ignore[arg-type]
        name="Sixmile Creek",
        kind=StructureKind.BRIDGE,
        milepost=miles("4.20"),
        rating=pounds(64000),
    )
    assert "ST-00001" not in row_of_structure(made)


def test_an_inactive_carrier_writes_as_no():
    made = Carrier(
        code="OLDCO",  # type: ignore[arg-type]
        name="Oldco",
        usdot=1,
        home_state="MT",
        active=False,
    )
    assert row_of_carrier(made)[-1] == "no"


def test_nothing_set_writes_as_a_blank_cell():
    made = Structure(
        reference="ST-00001",  # type: ignore[arg-type]
        segment="SEG-AB",  # type: ignore[arg-type]
        name="Sixmile Creek",
        kind=StructureKind.BRIDGE,
        milepost=miles("4.20"),
    )
    assert row_of_structure(made)[4] == ""


def test_writing_into_a_folder_that_is_not_there_makes_it(tmp_path):
    with opened_new_office() as office:
        stock(office)
        write_all(office, tmp_path / "deep" / "out")
    assert (tmp_path / "deep" / "out" / FILES["nodes"]).exists()
