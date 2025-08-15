import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.store.migrations import (
    LATEST,
    MIGRATIONS,
    Migration,
    applied,
    check_order,
    migrate,
    pending,
    version,
)
from jeepdolly.store.sqlite import column_names, opened, scalar, table_names


def test_a_fresh_file_is_at_version_zero(raw):
    assert version(raw) == 0


def test_a_fresh_file_has_nothing_applied(raw):
    assert applied(raw) == []


def test_a_fresh_file_has_everything_pending(raw):
    assert len(pending(raw)) == len(MIGRATIONS)


def test_migrate_runs_every_migration(raw):
    assert migrate(raw) == [m.number for m in MIGRATIONS]


def test_migrate_reaches_the_latest_version(office):
    assert version(office) == LATEST


def test_migrating_twice_changes_nothing(office):
    assert migrate(office) == []


def test_a_migrated_file_has_nothing_pending(office):
    assert pending(office) == []


def test_a_migrated_file_records_every_change(office):
    assert applied(office) == [m.number for m in MIGRATIONS]


def test_the_change_table_records_a_name(office):
    got = scalar(office, "SELECT name FROM schema_change WHERE number = 1")
    assert got == "carriers"


def test_the_change_table_records_when_it_ran(office):
    got = scalar(office, "SELECT ran_at FROM schema_change WHERE number = 1")
    assert got is not None


def test_the_carrier_table_is_there(office):
    assert "carrier" in table_names(office)


def test_the_rig_tables_are_there(office):
    assert "rig" in table_names(office)
    assert "rig_axle" in table_names(office)


def test_the_load_table_is_there(office):
    assert "load_item" in table_names(office)


def test_the_carrier_table_has_five_columns(office):
    assert column_names(office, "carrier") == ["code", "name", "usdot", "home_state", "active"]


def test_the_axle_table_has_eight_columns(office):
    assert column_names(office, "rig_axle") == [
        "rig_reference",
        "position",
        "weight",
        "tires",
        "tire_width",
        "liftable",
        "steering",
        "spacing_ahead",
    ]


def test_a_rig_needs_a_carrier_that_exists(office):
    with pytest.raises(Exception, match="FOREIGN KEY"):
        office.execute("INSERT INTO rig VALUES ('R-00001', 'NOBODY', '3S2', '2025-04-01')")


def test_a_carrier_usdot_is_unique(office):
    office.execute("INSERT INTO carrier VALUES ('A', 'A Haul', 1, 'MT', 1)")
    with pytest.raises(Exception, match="UNIQUE"):
        office.execute("INSERT INTO carrier VALUES ('B', 'B Haul', 1, 'MT', 1)")


def test_an_axle_needs_a_positive_tire_count(office):
    office.execute("INSERT INTO carrier VALUES ('A', 'A Haul', 1, 'MT', 1)")
    office.execute("INSERT INTO rig VALUES ('R-00001', 'A', '3S2', '2025-04-01')")
    with pytest.raises(Exception, match="CHECK"):
        office.execute("INSERT INTO rig_axle VALUES ('R-00001', 0, 12000, 0, 11, 0, 1, 0)")


def test_deleting_a_rig_takes_its_axles(office):
    office.execute("INSERT INTO carrier VALUES ('A', 'A Haul', 1, 'MT', 1)")
    office.execute("INSERT INTO rig VALUES ('R-00001', 'A', '3S2', '2025-04-01')")
    office.execute("INSERT INTO rig_axle VALUES ('R-00001', 0, 12000, 2, 11, 0, 1, 0)")
    office.execute("DELETE FROM rig WHERE reference = 'R-00001'")
    assert scalar(office, "SELECT count(*) FROM rig_axle") == 0


def test_the_migration_list_is_in_order():
    check_order()


def test_check_order_catches_a_gap():
    broken = (MIGRATIONS[0], Migration(number=3, name="x", statements=("SELECT 1",)))
    with pytest.raises(BadValueError):
        check_order(broken)


def test_check_order_catches_a_repeated_name():
    twice = (
        Migration(number=1, name="same", statements=("SELECT 1",)),
        Migration(number=2, name="same", statements=("SELECT 1",)),
    )
    with pytest.raises(BadValueError):
        check_order(twice)


def test_a_migration_refuses_number_zero():
    with pytest.raises(BadValueError):
        Migration(number=0, name="x", statements=("SELECT 1",))


def test_a_migration_refuses_a_bool_number():
    with pytest.raises(BadValueError):
        Migration(number=True, name="x", statements=("SELECT 1",))


def test_a_migration_refuses_an_empty_name():
    with pytest.raises(BadValueError):
        Migration(number=1, name=" ", statements=("SELECT 1",))


def test_a_migration_refuses_no_statements():
    with pytest.raises(BadValueError):
        Migration(number=1, name="x", statements=())


def test_migrations_order_by_number():
    later = Migration(number=9, name="z", statements=("SELECT 1",))
    assert sorted([later, MIGRATIONS[0]])[0] is MIGRATIONS[0]


def test_latest_is_the_last_number():
    assert MIGRATIONS[-1].number == LATEST


def test_a_file_on_disk_survives_being_reopened(tmp_path):
    path = tmp_path / "office.sqlite3"
    with opened(path) as connection:
        migrate(connection)
    with opened(path) as connection:
        assert version(connection) == LATEST
        assert migrate(connection) == []


def test_the_road_map_tables_are_there(office):
    for name in ("node", "segment", "structure"):
        assert name in table_names(office)


def test_a_structure_may_not_carry_both_numbers(office):
    office.execute("INSERT INTO node VALUES ('A', 'a', 'c')")
    office.execute("INSERT INTO node VALUES ('B', 'b', 'c')")
    office.execute(
        "INSERT INTO segment (code, start_node, end_node, route, distance, road_class)"
        " VALUES ('S', 'A', 'B', 'US-12', 100, 'state')"
    )
    with pytest.raises(Exception, match="CHECK"):
        office.execute(
            "INSERT INTO structure (reference, segment_code, name, kind, milepost,"
            " clearance, rating) VALUES ('STR-1', 'S', 'x', 'bridge', 10, 100, 100)"
        )


def test_a_segment_may_not_start_and_end_at_one_node(office):
    office.execute("INSERT INTO node VALUES ('A', 'a', 'c')")
    with pytest.raises(Exception, match="CHECK"):
        office.execute(
            "INSERT INTO segment (code, start_node, end_node, route, distance, road_class)"
            " VALUES ('S', 'A', 'A', 'US-12', 100, 'state')"
        )
