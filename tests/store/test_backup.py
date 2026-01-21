import sqlite3

import pytest

from jeepdolly.errors import BadValueError, ConflictError, NotFoundError
from jeepdolly.party.carrier import Carrier
from jeepdolly.store.backup import (
    Soundness,
    back_up,
    check_file,
    file_size,
    row_counts,
    vacuum,
)
from jeepdolly.store.migrations import LATEST
from jeepdolly.store.office import create, opened_office


def a_carrier(code: str = "VANCE", usdot: int = 1184062) -> Carrier:
    """One carrier to put in a file worth backing up."""
    return Carrier(code=code, name="Vance Heavy Haul", usdot=usdot, home_state="MT")  # type: ignore[arg-type]


@pytest.fixture
def live(tmp_path):
    """A created office file with one carrier in it."""
    path = tmp_path / "office.sqlite3"
    create(path)
    with opened_office(path) as office, office.writing():
        office.carriers.add(a_carrier())
    return path


def test_a_fresh_file_is_sound(live):
    got = check_file(live)
    assert got.sound
    assert got.trouble == ()


def test_a_sound_file_reports_its_schema(live):
    assert check_file(live).schema == LATEST


def test_a_sound_file_counts_its_tables(live):
    assert check_file(live).tables > 10


def test_a_sound_file_prints_that_it_is_sound(live):
    assert str(check_file(live)).startswith("sound")


def test_a_file_that_is_not_there_is_refused(tmp_path):
    with pytest.raises(NotFoundError):
        check_file(tmp_path / "nothing.sqlite3")


def test_a_file_with_no_schema_is_not_sound(tmp_path):
    path = tmp_path / "empty.sqlite3"
    sqlite3.connect(path).close()
    got = check_file(path)
    assert not got.sound
    assert any("schema" in line for line in got.trouble)


def test_a_broken_reference_is_reported():
    made = Soundness(integrity="ok", foreign_keys=3, schema=LATEST, tables=20)
    assert not made.sound
    assert "3 rows point at records that are gone" in made.trouble


def test_a_corrupt_file_is_reported():
    made = Soundness(integrity="page 4 is missing", schema=LATEST, foreign_keys=0, tables=20)
    assert not made.sound
    assert "page 4 is missing" in str(made)


def test_an_orphan_row_is_found(live):
    with opened_office(live) as office:
        office.connection.execute("PRAGMA foreign_keys = OFF")
        office.connection.execute(
            "INSERT INTO rig VALUES ('R-00001', 'NOBODY', '3S2', '2025-01-01')"
        )
        office.commit()
    got = check_file(live)
    assert got.foreign_keys == 1
    assert not got.sound


def test_a_backup_is_written(live, tmp_path):
    made = back_up(live, tmp_path / "copy.sqlite3")
    assert made.exists()


def test_a_backup_holds_the_records(live, tmp_path):
    back_up(live, tmp_path / "copy.sqlite3")
    with opened_office(tmp_path / "copy.sqlite3") as office:
        assert office.carriers.get("VANCE").usdot == 1184062


def test_a_backup_is_sound(live, tmp_path):
    made = back_up(live, tmp_path / "copy.sqlite3")
    assert check_file(made).sound


def test_a_backup_makes_the_directory(live, tmp_path):
    made = back_up(live, tmp_path / "nightly" / "copy.sqlite3")
    assert made.parent.name == "nightly"


def test_a_backup_refuses_to_write_over_a_file(live, tmp_path):
    target = tmp_path / "copy.sqlite3"
    back_up(live, target)
    with pytest.raises(ConflictError):
        back_up(live, target)


def test_a_backup_refuses_a_source_that_is_not_there(tmp_path):
    with pytest.raises(NotFoundError):
        back_up(tmp_path / "nothing.sqlite3", tmp_path / "copy.sqlite3")


def test_a_backup_refuses_to_copy_a_file_onto_itself(live):
    with pytest.raises(BadValueError):
        back_up(live, live)


def test_a_backup_does_not_disturb_the_live_file(live, tmp_path):
    back_up(live, tmp_path / "copy.sqlite3")
    with opened_office(live) as office:
        assert office.carriers.count() == 1


def test_vacuuming_leaves_the_records_alone(live):
    vacuum(live)
    with opened_office(live) as office:
        assert office.carriers.count() == 1


def test_vacuuming_reports_a_number_of_bytes(live):
    assert vacuum(live) >= 0


def test_vacuuming_a_file_that_is_not_there_is_refused(tmp_path):
    with pytest.raises(NotFoundError):
        vacuum(tmp_path / "nothing.sqlite3")


def test_a_deleted_year_of_records_frees_pages(live):
    with opened_office(live) as office, office.writing():
        for number in range(2, 400):
            office.carriers.add(a_carrier(code=f"C{number:04d}", usdot=number))
    with opened_office(live) as office, office.writing():
        office.connection.execute("DELETE FROM carrier WHERE code <> 'VANCE'")
    assert vacuum(live) > 0


def test_the_file_size_counts_the_write_ahead_log(live):
    assert file_size(live) >= live.stat().st_size


def test_the_size_of_a_file_that_is_not_there_is_zero(tmp_path):
    assert file_size(tmp_path / "nothing.sqlite3") == 0


def test_the_row_counts_cover_every_table(live):
    with opened_office(live) as office:
        counts = row_counts(office.connection)
    assert counts["carrier"] == 1
    assert counts["permit"] == 0
    assert len(counts) > 10


def test_the_row_counts_are_in_name_order(live):
    with opened_office(live) as office:
        counts = row_counts(office.connection)
    assert list(counts) == sorted(counts)
