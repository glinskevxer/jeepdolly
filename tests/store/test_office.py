import sqlite3

import pytest

from jeepdolly.errors import ConflictError, NotFoundError
from jeepdolly.party.carrier import Carrier
from jeepdolly.store.migrations import LATEST
from jeepdolly.store.office import Office, create, opened_new_office, opened_office
from jeepdolly.store.sqlite import MEMORY


def a_carrier(**over: object) -> Carrier:
    kw: dict[str, object] = {
        "code": "VANCE",
        "name": "Vance Heavy Haul",
        "usdot": 1184062,
        "home_state": "MT",
    }
    kw.update(over)
    return Carrier(**kw)  # type: ignore[arg-type]


def test_a_new_office_is_at_the_latest_schema():
    with opened_new_office() as office:
        assert office.version == LATEST
        assert office.current


def test_a_new_office_has_every_store():
    with opened_new_office() as office:
        assert office.carriers.count() == 0
        assert office.rigs.count() == 0
        assert office.loads.count() == 0


def test_create_makes_the_file(tmp_path):
    path = tmp_path / "office.sqlite3"
    create(path)
    assert path.exists()


def test_create_refuses_an_existing_file(tmp_path):
    path = tmp_path / "office.sqlite3"
    create(path)
    with pytest.raises(ConflictError):
        create(path)


def test_opened_office_reads_a_created_file(tmp_path):
    path = tmp_path / "office.sqlite3"
    create(path)
    with opened_office(path) as office:
        assert office.current


def test_opened_office_refuses_a_missing_file(tmp_path):
    with pytest.raises(NotFoundError), opened_office(tmp_path / "nothing.sqlite3"):
        pass


def test_opened_office_refuses_a_file_with_no_schema(tmp_path):
    path = tmp_path / "empty.sqlite3"
    sqlite3.connect(path).close()
    with pytest.raises(NotFoundError), opened_office(path):
        pass


def test_opened_office_closes_the_connection(tmp_path):
    path = tmp_path / "office.sqlite3"
    create(path)
    with opened_office(path) as office:
        held = office.connection
    with pytest.raises(sqlite3.ProgrammingError):
        held.execute("SELECT 1")


def test_a_write_inside_the_block_is_kept(tmp_path):
    path = tmp_path / "office.sqlite3"
    create(path)
    with opened_office(path) as office, office.writing():
        office.carriers.add(a_carrier())
    with opened_office(path) as office:
        assert office.carriers.count() == 1


def test_a_failed_write_block_is_thrown_away(tmp_path):
    path = tmp_path / "office.sqlite3"
    create(path)
    try:
        with opened_office(path) as office, office.writing():
            office.carriers.add(a_carrier())
            raise ZeroDivisionError
    except ZeroDivisionError:
        pass
    with opened_office(path) as office:
        assert office.carriers.count() == 0


def test_writing_hands_back_the_office():
    with opened_new_office() as office, office.writing() as inner:
        assert inner is office


def test_commit_writes_out(tmp_path):
    path = tmp_path / "office.sqlite3"
    create(path)
    with opened_office(path) as office:
        office.carriers.add(a_carrier())
        office.commit()
    with opened_office(path) as office:
        assert "VANCE" in office.carriers


def test_rollback_throws_away(tmp_path):
    path = tmp_path / "office.sqlite3"
    create(path)
    with opened_office(path) as office:
        office.carriers.add(a_carrier())
        office.rollback()
        assert office.carriers.count() == 0


def test_upgrade_on_a_current_office_does_nothing():
    with opened_new_office() as office:
        assert office.upgrade() == []


def test_upgrade_brings_a_bare_file_up(tmp_path):
    path = tmp_path / "office.sqlite3"
    sqlite3.connect(path).close()
    from jeepdolly.store.sqlite import opened

    with opened(path) as connection:
        office = Office(connection)
        assert office.version == 0
        assert office.upgrade() == list(range(1, LATEST + 1))
        assert office.current


def test_office_says_its_schema_when_printed():
    with opened_new_office() as office:
        assert repr(office) == f"<Office at schema {LATEST}>"


def test_an_in_memory_office_is_not_a_file(tmp_path):
    with opened_new_office(MEMORY) as office:
        assert office.current


def test_two_offices_on_one_path_see_the_same_records(tmp_path):
    path = tmp_path / "office.sqlite3"
    create(path)
    with opened_office(path) as first:
        first.carriers.add(a_carrier())
        first.commit()
    with opened_office(path) as second:
        assert second.carriers.get("VANCE").name == "Vance Heavy Haul"
