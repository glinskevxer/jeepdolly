from jeepdolly.store.migrations import migrate
from jeepdolly.store.sqlite import MEMORY, opened
from jeepdolly.tools.check_indexes import (
    EXEMPT,
    first_columns,
    main,
    problems,
    references,
)


def test_every_reference_is_indexed():
    assert problems() == []


def test_main_passes_over_the_schema():
    assert main() == 0


def test_the_references_of_a_table_are_found():
    with opened(MEMORY) as connection:
        migrate(connection)
        assert set(references(connection, "rig")) == {"carrier_code"}


def test_a_table_with_no_references_has_none():
    with opened(MEMORY) as connection:
        migrate(connection)
        assert references(connection, "carrier") == []


def test_the_primary_key_counts_as_indexed():
    with opened(MEMORY) as connection:
        migrate(connection)
        assert "code" in first_columns(connection, "carrier")


def test_a_declared_index_counts_as_indexed():
    with opened(MEMORY) as connection:
        migrate(connection)
        assert "carrier_code" in first_columns(connection, "rig")


def test_only_the_leading_column_of_an_index_counts():
    with opened(MEMORY) as connection:
        connection.execute("CREATE TABLE thing (a TEXT, b TEXT)")
        connection.execute("CREATE INDEX thing_by_a_b ON thing (a, b)")
        leading = first_columns(connection, "thing")
        assert "a" in leading
        assert "b" not in leading


def test_every_exemption_names_a_table_that_is_there():
    from jeepdolly.store.sqlite import table_names

    with opened(MEMORY) as connection:
        migrate(connection)
        present = set(table_names(connection))
        for name in EXEMPT:
            table, _, _ = name.partition(".")
            assert table in present


def test_every_exemption_names_a_real_reference():
    with opened(MEMORY) as connection:
        migrate(connection)
        for name in EXEMPT:
            table, _, column = name.partition(".")
            assert column in references(connection, table), name


def test_the_exemptions_are_all_child_tables():
    assert all("." in name for name in EXEMPT)


def test_the_application_route_ends_are_indexed():
    with opened(MEMORY) as connection:
        migrate(connection)
        leading = first_columns(connection, "application")
        assert "origin" in leading
        assert "destination" in leading


def test_the_permit_successor_is_indexed():
    with opened(MEMORY) as connection:
        migrate(connection)
        assert "replaced_by" in first_columns(connection, "permit")
