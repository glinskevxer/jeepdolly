from collections.abc import Iterator
from pathlib import Path

import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.importer.csv_in import (
    FILES,
    Loaded,
    load_all,
    load_carriers,
    load_nodes,
    load_segments,
    load_structures,
    read_rows,
)
from jeepdolly.store.office import Office, opened_new_office

CARRIERS = """code,name,usdot,home_state,active
VANCE,Vance Heavy Haul,1184062,MT,1
SUMMIT,Summit Rigging,2277431,ID,1
OLDCO,Oldco Transport,3311902,WY,0
"""

NODES = """code,name,county
JCT-A,US 12 at Lolo,Missoula
JCT-B,US 12 at Sixmile,Missoula
JCT-C,SR 200 junction,Granite
"""

SEGMENTS = """code,start,end,route,miles,class,one_way,posted
SEG-AB,JCT-A,JCT-B,US-12,12.00,state,,
SEG-BC,JCT-B,JCT-C,US-12,8.50,interstate,,48000
"""

STRUCTURES = """segment,name,kind,milepost,clearance,rating
SEG-BC,Sixmile Creek,bridge,4.20,,64000
SEG-BC,MRL overhead,overhead,1.10,15'2",
"""


@pytest.fixture
def office() -> Iterator[Office]:
    """A fresh office to load into."""
    with opened_new_office() as made:
        yield made


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    """A directory holding all four files."""
    (tmp_path / FILES["carriers"]).write_text(CARRIERS, encoding="utf-8")
    (tmp_path / FILES["nodes"]).write_text(NODES, encoding="utf-8")
    (tmp_path / FILES["segments"]).write_text(SEGMENTS, encoding="utf-8")
    (tmp_path / FILES["structures"]).write_text(STRUCTURES, encoding="utf-8")
    return tmp_path


def test_read_rows_starts_at_line_two(tmp_path):
    path = tmp_path / "x.csv"
    path.write_text("a,b\n1,2\n", encoding="utf-8")
    assert list(read_rows(path)) == [(2, {"a": "1", "b": "2"})]


def test_read_rows_trims_the_fields(tmp_path):
    path = tmp_path / "x.csv"
    path.write_text("a\n  spaced  \n", encoding="utf-8")
    assert next(iter(read_rows(path)))[1]["a"] == "spaced"


def test_read_rows_refuses_a_file_with_no_header(tmp_path):
    path = tmp_path / "x.csv"
    path.write_text("", encoding="utf-8")
    with pytest.raises(BadValueError):
        list(read_rows(path))


def test_the_carrier_file_loads_every_row(office, folder):
    assert load_carriers(office, folder / FILES["carriers"]) == 3
    assert office.carriers.count() == 3


def test_the_inactive_flag_is_read(office, folder):
    load_carriers(office, folder / FILES["carriers"])
    assert not office.carriers.get("OLDCO").active


def test_a_bad_carrier_row_names_its_line(office, tmp_path):
    path = tmp_path / "carriers.csv"
    path.write_text("code,name,usdot,home_state\nVANCE,Vance,1,ZZ\n", encoding="utf-8")
    with pytest.raises(BadValueError, match="carriers.csv:2"):
        load_carriers(office, path)


def test_a_carrier_row_with_a_bad_number_names_its_line(office, tmp_path):
    path = tmp_path / "carriers.csv"
    path.write_text("code,name,usdot,home_state\nVANCE,Vance,lots,MT\n", encoding="utf-8")
    with pytest.raises(BadValueError, match="carriers.csv:2"):
        load_carriers(office, path)


def test_a_carrier_row_missing_a_column_names_its_line(office, tmp_path):
    path = tmp_path / "carriers.csv"
    path.write_text("code,name\nVANCE,Vance\n", encoding="utf-8")
    with pytest.raises(BadValueError, match="carriers.csv:2"):
        load_carriers(office, path)


def test_the_junction_file_loads_every_row(office, folder):
    assert load_nodes(office, folder / FILES["nodes"]) == 3
    assert office.roadway.get_node("JCT-A").county == "Missoula"


def test_a_repeated_node_names_its_line(office, tmp_path):
    path = tmp_path / "nodes.csv"
    path.write_text("code,name,county\nJCT-A,a,c\nJCT-A,a,c\n", encoding="utf-8")
    with pytest.raises(BadValueError, match="nodes.csv:3"):
        load_nodes(office, path)


def test_a_node_row_missing_a_column_names_its_line(office, tmp_path):
    path = tmp_path / "nodes.csv"
    path.write_text("code,name\nJCT-A,a\n", encoding="utf-8")
    with pytest.raises(BadValueError, match="nodes.csv:2"):
        load_nodes(office, path)


def test_the_stretch_file_loads_every_row(office, folder):
    load_nodes(office, folder / FILES["nodes"])
    assert load_segments(office, folder / FILES["segments"]) == 2


def test_a_segment_keeps_its_road_class(office, folder):
    load_nodes(office, folder / FILES["nodes"])
    load_segments(office, folder / FILES["segments"])
    assert str(office.roadway.get_segment("SEG-BC").road_class) == "interstate"


def test_a_blank_posted_column_reads_as_none(office, folder):
    load_nodes(office, folder / FILES["nodes"])
    load_segments(office, folder / FILES["segments"])
    assert office.roadway.get_segment("SEG-AB").posted_gross is None


def test_a_posted_column_is_read(office, folder):
    load_nodes(office, folder / FILES["nodes"])
    load_segments(office, folder / FILES["segments"])
    assert int(office.roadway.get_segment("SEG-BC").posted_gross or 0) == 48000


def test_a_segment_pointing_at_no_node_names_its_line(office, tmp_path):
    path = tmp_path / "segments.csv"
    path.write_text(
        "code,start,end,route,miles\nSEG-AB,JCT-A,JCT-B,US-12,12.00\n", encoding="utf-8"
    )
    with pytest.raises(BadValueError, match="segments.csv:2"):
        load_segments(office, path)


def test_a_segment_with_a_bad_class_names_its_line(office, folder, tmp_path):
    load_nodes(office, folder / FILES["nodes"])
    path = tmp_path / "bad.csv"
    path.write_text(
        "code,start,end,route,miles,class\nSEG-AB,JCT-A,JCT-B,US-12,12.00,gravel\n",
        encoding="utf-8",
    )
    with pytest.raises(BadValueError, match="bad.csv:2"):
        load_segments(office, path)


def test_the_structure_file_loads_every_row(office, folder):
    load_nodes(office, folder / FILES["nodes"])
    load_segments(office, folder / FILES["segments"])
    assert load_structures(office, folder / FILES["structures"]) == 2


def test_an_overhead_keeps_its_clearance(office, folder):
    load_nodes(office, folder / FILES["nodes"])
    load_segments(office, folder / FILES["segments"])
    load_structures(office, folder / FILES["structures"])
    found = office.roadway.get_structure("STR-00002")
    assert int(found.clearance or 0) == 182


def test_a_structure_on_no_segment_names_its_line(office, tmp_path):
    path = tmp_path / "structures.csv"
    path.write_text("segment,name,milepost\nSEG-ZZ,x,1.00\n", encoding="utf-8")
    with pytest.raises(BadValueError, match="structures.csv:2"):
        load_structures(office, path)


def test_load_all_reads_every_file(office, folder):
    got = load_all(office, folder)
    assert got == Loaded(carriers=3, nodes=3, segments=2, structures=2)
    assert got.total == 10


def test_load_all_leaves_a_joined_up_map(office, folder):
    load_all(office, folder)
    assert office.roadway.network().connected


def test_load_all_skips_a_file_that_is_not_there(office, tmp_path):
    (tmp_path / FILES["nodes"]).write_text(NODES, encoding="utf-8")
    got = load_all(office, tmp_path)
    assert got.nodes == 3
    assert got.carriers == 0


def test_load_all_refuses_something_that_is_not_a_folder(office, tmp_path):
    with pytest.raises(BadValueError):
        load_all(office, tmp_path / "nothing")


def test_a_failed_load_leaves_nothing_behind(office, folder):
    (folder / FILES["structures"]).write_text(
        "segment,name,milepost\nSEG-ZZ,x,1.00\n", encoding="utf-8"
    )
    with pytest.raises(BadValueError):
        load_all(office, folder)
    assert office.carriers.count() == 0
    assert office.roadway.counts() == (0, 0, 0)


def test_a_loaded_count_prints_itself():
    assert (
        str(Loaded(carriers=1, nodes=2)) == "1 carriers, 2 junctions, 0 stretches, 0 structures"
    )


def test_the_file_names_are_all_csv():
    assert all(name.endswith(".csv") for name in FILES.values())


def test_a_posted_width_is_read(office, tmp_path):
    (tmp_path / FILES["nodes"]).write_text(NODES, encoding="utf-8")
    (tmp_path / FILES["segments"]).write_text(
        "code,start,end,route,miles,max_width\nSEG-AB,JCT-A,JCT-B,US-12,12.00,12'\n",
        encoding="utf-8",
    )
    load_all(office, tmp_path)
    assert int(office.roadway.get_segment("SEG-AB").max_width or 0) == 144


def test_a_posted_height_is_read(office, tmp_path):
    (tmp_path / FILES["nodes"]).write_text(NODES, encoding="utf-8")
    (tmp_path / FILES["segments"]).write_text(
        "code,start,end,route,miles,max_height\nSEG-AB,JCT-A,JCT-B,US-12,12.00,14'\n",
        encoding="utf-8",
    )
    load_all(office, tmp_path)
    assert int(office.roadway.get_segment("SEG-AB").max_height or 0) == 168


def test_a_misspelled_column_stops_the_import(office, tmp_path):
    (tmp_path / FILES["nodes"]).write_text(NODES, encoding="utf-8")
    (tmp_path / FILES["segments"]).write_text(
        "code,start,end,route,miles,max_hieght\nSEG-AB,JCT-A,JCT-B,US-12,12.00,14'\n",
        encoding="utf-8",
    )
    with pytest.raises(BadValueError, match="max_hieght"):
        load_all(office, tmp_path)


def test_a_misspelled_column_leaves_nothing_behind(office, tmp_path):
    (tmp_path / FILES["carriers"]).write_text(CARRIERS, encoding="utf-8")
    (tmp_path / FILES["nodes"]).write_text(
        "code,name,conty\nJCT-A,a,Missoula\n", encoding="utf-8"
    )
    with pytest.raises(BadValueError):
        load_all(office, tmp_path)
    assert office.carriers.count() == 0


def test_every_column_the_office_reads_is_on_the_list():
    from jeepdolly.importer.csv_in import COLUMNS

    assert set(COLUMNS) == set(FILES)
    assert "max_width" in COLUMNS["segments"]
    assert "clearance" in COLUMNS["structures"]


def test_a_file_with_only_the_columns_it_needs_loads(office, tmp_path):
    (tmp_path / FILES["nodes"]).write_text(
        "code,name,county\nJCT-A,a,Missoula\n", encoding="utf-8"
    )
    assert load_all(office, tmp_path).nodes == 1


def test_a_structure_row_missing_a_column_names_its_line(office, tmp_path):
    path = tmp_path / "structures.csv"
    path.write_text("segment,name\nSEG-AB,x\n", encoding="utf-8")
    with pytest.raises(BadValueError, match="structures.csv:2"):
        load_structures(office, path)


def test_a_structure_row_with_a_bad_kind_names_its_line(office, folder):
    load_nodes(office, folder / FILES["nodes"])
    load_segments(office, folder / FILES["segments"])
    path = folder / FILES["structures"]
    path.write_text("segment,name,kind,milepost\nSEG-BC,x,footbridge,1.00\n", encoding="utf-8")
    with pytest.raises(BadValueError, match="structures.csv:2"):
        load_structures(office, path)


def test_a_segment_row_missing_a_column_names_its_line(office, folder):
    load_nodes(office, folder / FILES["nodes"])
    path = folder / FILES["segments"]
    path.write_text("code,start,end\nSEG-AB,JCT-A,JCT-B\n", encoding="utf-8")
    with pytest.raises(BadValueError, match="segments.csv:2"):
        load_segments(office, path)
