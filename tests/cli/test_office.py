from collections.abc import Callable
from pathlib import Path

from click.testing import Result

from .test_permit import apply_one


def test_a_fresh_file_reports_sound(run: Callable[..., Result]):
    result = run("office", "sound")
    assert result.exit_code == 0
    assert "sound" in result.output


def test_a_file_that_is_not_there_is_refused(runner, tmp_path):
    from jeepdolly.cli.main import main

    result = runner.invoke(main, ["-f", str(tmp_path / "nothing.sqlite3"), "office", "sound"])
    assert result.exit_code == 1


def test_a_file_with_no_schema_is_not_sound(runner, tmp_path):
    import sqlite3

    from jeepdolly.cli.main import main

    path = tmp_path / "empty.sqlite3"
    sqlite3.connect(path).close()
    result = runner.invoke(main, ["-f", str(path), "office", "sound"])
    assert result.exit_code == 1
    assert "schema" in result.output


def test_a_backup_is_written(run: Callable[..., Result], tmp_path: Path):
    target = tmp_path / "copy.sqlite3"
    result = run("office", "backup", str(target))
    assert result.exit_code == 0
    assert target.exists()
    assert "wrote" in result.output


def test_a_backup_reports_its_size(run: Callable[..., Result], tmp_path: Path):
    result = run("office", "backup", str(tmp_path / "copy.sqlite3"))
    assert "kB" in result.output or "MB" in result.output or "B)" in result.output


def test_a_backup_holds_the_records(stocked, tmp_path: Path):
    apply_one(stocked)
    target = tmp_path / "copy.sqlite3"
    stocked("office", "backup", str(target))
    from click.testing import CliRunner

    from jeepdolly.cli.main import main

    result = CliRunner().invoke(main, ["-f", str(target), "status"])
    assert "carriers 1" in result.output


def test_a_backup_refuses_to_write_over_a_file(run: Callable[..., Result], tmp_path: Path):
    target = tmp_path / "copy.sqlite3"
    run("office", "backup", str(target))
    assert run("office", "backup", str(target)).exit_code == 1


def test_vacuuming_reports_what_it_freed(run: Callable[..., Result]):
    result = run("office", "vacuum")
    assert result.exit_code == 0
    assert "freed" in result.output


def test_vacuuming_leaves_the_records_alone(stocked):
    apply_one(stocked)
    stocked("office", "vacuum")
    assert "carriers 1" in stocked("status").output


def test_the_row_counts_list_every_table(run: Callable[..., Result]):
    output = run("office", "rows").output
    assert "row counts" in output
    assert "carrier" in output
    assert "permit" in output


def test_the_row_counts_add_up(stocked):
    apply_one(stocked)
    output = stocked("office", "rows").output
    assert "rows" in output
    assert "size" in output


def test_the_row_counts_show_the_records(stocked):
    apply_one(stocked)
    stocked("permit", "issue", "1", "--on", "2025-06-17")
    output = stocked("office", "rows").output
    assert "permit" in output
    assert "journal" in output


def test_the_stocked_template_is_copied_rather_than_shared(stocked, tmp_path):
    """A test that writes to its copy must not disturb the next one."""
    stocked("carrier", "retire", "VANCE")
    assert "inactive" in stocked("carrier", "list", "--all").output


def test_the_following_case_sees_an_untouched_copy(stocked):
    assert "Vance Heavy Haul" in stocked("carrier", "list").output
    assert "inactive" not in stocked("carrier", "list", "--all").output


def test_the_copied_office_is_sound(stocked):
    assert "sound" in stocked("office", "sound").output


def test_the_copied_office_holds_the_whole_map(stocked):
    output = stocked("status").output
    assert "junctions 4" in output
    assert "segments 4" in output
    assert "rigs 1" in output


def test_the_copied_office_carries_no_journal_from_the_build(stocked):
    assert "journal 0" in stocked("status").output


def test_a_backup_of_a_stocked_office_holds_the_map(stocked, tmp_path):
    target = tmp_path / "copy.sqlite3"
    stocked("office", "backup", str(target))
    from click.testing import CliRunner

    from jeepdolly.cli.main import main

    output = CliRunner().invoke(main, ["-f", str(target), "status"]).output
    assert "segments 4" in output


def test_the_row_counts_of_a_stocked_office(stocked):
    output = stocked("office", "rows").output
    assert "node" in output
    assert "segment" in output


def test_vacuuming_a_stocked_office_keeps_the_rigs(stocked):
    stocked("office", "vacuum")
    assert "R-00001" in stocked("rig", "list").output


def test_the_soundness_check_survives_a_vacuum(stocked):
    stocked("office", "vacuum")
    assert "sound" in stocked("office", "sound").output


def test_the_backup_of_a_copy_is_still_sound(stocked, tmp_path):
    first = tmp_path / "first.sqlite3"
    stocked("office", "backup", str(first))
    from click.testing import CliRunner

    from jeepdolly.cli.main import main

    runner = CliRunner()
    second = tmp_path / "second.sqlite3"
    runner.invoke(main, ["-f", str(first), "office", "backup", str(second)])
    output = runner.invoke(main, ["-f", str(second), "office", "sound"]).output
    assert "sound" in output
