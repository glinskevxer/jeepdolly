from collections.abc import Callable
from pathlib import Path

from click.testing import Result

CARRIERS = """code,name,usdot,home_state
VANCE,Vance Heavy Haul,1184062,MT
SUMMIT,Summit Rigging,2277431,ID
"""

NODES = """code,name,county
JCT-A,US 12 at Lolo,Missoula
JCT-B,US 12 at Sixmile,Missoula
"""

SEGMENTS = """code,start,end,route,miles
SEG-AB,JCT-A,JCT-B,US-12,12.00
"""

STRUCTURES = """segment,name,kind,milepost,rating
SEG-AB,Sixmile Creek,bridge,4.20,64000
"""


def a_folder(tmp_path: Path) -> Path:
    """A directory holding all four import files."""
    folder = tmp_path / "feed"
    folder.mkdir()
    (folder / "carriers.csv").write_text(CARRIERS, encoding="utf-8")
    (folder / "nodes.csv").write_text(NODES, encoding="utf-8")
    (folder / "segments.csv").write_text(SEGMENTS, encoding="utf-8")
    (folder / "structures.csv").write_text(STRUCTURES, encoding="utf-8")
    return folder


def test_load_reads_every_file(run: Callable[..., Result], tmp_path: Path):
    result = run("load", str(a_folder(tmp_path)))
    assert result.exit_code == 0
    assert "2 carriers" in result.output
    assert "1 structures" in result.output


def test_the_loaded_records_are_kept(run: Callable[..., Result], tmp_path: Path):
    run("load", str(a_folder(tmp_path)))
    assert "carriers 2" in run("status").output
    assert "structures 1" in run("status").output


def test_load_refuses_a_folder_that_is_not_there(run: Callable[..., Result], tmp_path: Path):
    assert run("load", str(tmp_path / "nothing")).exit_code == 2


def test_load_refuses_a_file_instead_of_a_folder(run: Callable[..., Result], tmp_path: Path):
    lonely = tmp_path / "one.csv"
    lonely.write_text(CARRIERS, encoding="utf-8")
    assert run("load", str(lonely)).exit_code == 2


def test_a_bad_row_stops_the_whole_load(run: Callable[..., Result], tmp_path: Path):
    folder = a_folder(tmp_path)
    (folder / "structures.csv").write_text(
        "segment,name,milepost\nSEG-ZZ,x,1.00\n", encoding="utf-8"
    )
    result = run("load", str(folder))
    assert result.exit_code == 1
    assert "structures.csv:2" in result.output
    assert "carriers 0" in run("status").output


def test_check_reads_the_whole_file_back(run: Callable[..., Result], tmp_path: Path):
    run("load", str(a_folder(tmp_path)))
    result = run("check")
    assert result.exit_code == 0
    assert "check: clean" in result.output
    assert "read back 2 carriers" in result.output


def test_check_says_when_the_map_is_joined_up(run: Callable[..., Result], tmp_path: Path):
    run("load", str(a_folder(tmp_path)))
    assert "map joined up" in run("check").output


def test_check_notices_an_island(run: Callable[..., Result], tmp_path: Path):
    run("load", str(a_folder(tmp_path)))
    run("road", "node", "--code", "JCT-X", "--name", "island", "--county", "Ravalli")
    assert "map not joined up" in run("check").output


def test_check_reports_the_schema_version(run: Callable[..., Result]):
    from jeepdolly.store.migrations import LATEST

    assert f"schema {LATEST} of {LATEST}" in run("check").output


def test_check_on_a_missing_file_fails(runner, tmp_path):
    from jeepdolly.cli.main import main

    result = runner.invoke(main, ["-f", str(tmp_path / "nothing.sqlite3"), "check"])
    assert result.exit_code == 1


def test_check_says_the_accounts_balance(run: Callable[..., Result], tmp_path: Path):
    run("load", str(a_folder(tmp_path)))
    assert "every account balances" in run("check").output
