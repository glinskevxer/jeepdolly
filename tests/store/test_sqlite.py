import sqlite3

import pytest

from jeepdolly.errors import BadValueError, NotFoundError
from jeepdolly.store.sqlite import (
    MEMORY,
    column_names,
    connect,
    maybe_one,
    one,
    opened,
    rows,
    scalar,
    table_names,
    writing,
)


@pytest.fixture
def book():
    """An open in memory database with one small table in it."""
    with opened(MEMORY) as connection:
        connection.execute(
            "CREATE TABLE thing (code TEXT PRIMARY KEY, weight INTEGER NOT NULL)"
        )
        connection.execute("INSERT INTO thing VALUES ('A', 10)")
        connection.execute("INSERT INTO thing VALUES ('B', 20)")
        yield connection


def test_connect_gives_a_connection():
    with opened(MEMORY) as connection:
        assert isinstance(connection, sqlite3.Connection)


def test_connect_turns_foreign_keys_on():
    with opened(MEMORY) as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_connect_sets_a_busy_timeout():
    with opened(MEMORY) as connection:
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 5000


def test_connect_gives_rows_by_name(book):
    assert book.execute("SELECT code FROM thing WHERE code = 'A'").fetchone()["code"] == "A"


def test_connect_refuses_a_number():
    with pytest.raises(BadValueError):
        connect(12)  # type: ignore[arg-type]


def test_a_file_database_goes_into_write_ahead_mode(tmp_path):
    with opened(tmp_path / "office.sqlite3") as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_opened_closes_the_connection():
    with opened(MEMORY) as connection:
        pass
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")


def test_opened_closes_after_an_error():
    held: list[sqlite3.Connection] = []
    try:
        with opened(MEMORY) as connection:
            held.append(connection)
            raise ZeroDivisionError
    except ZeroDivisionError:
        pass
    with pytest.raises(sqlite3.ProgrammingError):
        held[0].execute("SELECT 1")


def test_writing_commits_on_the_way_out(tmp_path):
    path = tmp_path / "office.sqlite3"
    with opened(path) as connection:
        connection.execute("CREATE TABLE thing (code TEXT PRIMARY KEY)")
        with writing(connection) as write:
            write.execute("INSERT INTO thing VALUES ('A')")
    with opened(path) as connection:
        assert scalar(connection, "SELECT count(*) FROM thing") == 1


def test_writing_rolls_back_on_an_error(tmp_path):
    path = tmp_path / "office.sqlite3"
    with opened(path) as connection:
        connection.execute("CREATE TABLE thing (code TEXT PRIMARY KEY)")
        connection.commit()
        try:
            with writing(connection) as write:
                write.execute("INSERT INTO thing VALUES ('A')")
                raise ZeroDivisionError
        except ZeroDivisionError:
            pass
    with opened(path) as connection:
        assert scalar(connection, "SELECT count(*) FROM thing") == 0


def test_rows_returns_everything(book):
    assert len(rows(book, "SELECT * FROM thing")) == 2


def test_rows_takes_parameters(book):
    assert len(rows(book, "SELECT * FROM thing WHERE code = ?", ("A",))) == 1


def test_rows_of_nothing_is_empty(book):
    assert rows(book, "SELECT * FROM thing WHERE code = ?", ("Z",)) == []


def test_maybe_one_finds_the_row(book):
    found = maybe_one(book, "SELECT * FROM thing WHERE code = ?", ("A",))
    assert found is not None
    assert found["weight"] == 10


def test_maybe_one_of_nothing_is_none(book):
    assert maybe_one(book, "SELECT * FROM thing WHERE code = ?", ("Z",)) is None


def test_maybe_one_refuses_two_rows(book):
    with pytest.raises(BadValueError):
        maybe_one(book, "SELECT * FROM thing")


def test_one_finds_the_row(book):
    assert one(book, "SELECT * FROM thing WHERE code = ?", ("B",))["weight"] == 20


def test_one_raises_when_there_is_nothing(book):
    with pytest.raises(NotFoundError):
        one(book, "SELECT * FROM thing WHERE code = ?", ("Z",))


def test_one_names_the_kind_it_was_looking_for(book):
    with pytest.raises(NotFoundError) as caught:
        one(book, "SELECT * FROM thing WHERE code = ?", ("Z",), kind="thing")
    assert "thing" in str(caught.value)


def test_scalar_takes_the_first_column(book):
    assert scalar(book, "SELECT weight FROM thing WHERE code = ?", ("A",)) == 10


def test_scalar_of_nothing_is_none(book):
    assert scalar(book, "SELECT weight FROM thing WHERE code = ?", ("Z",)) is None


def test_table_names_lists_the_tables(book):
    assert table_names(book) == ["thing"]


def test_table_names_leaves_out_sqlite_internals(book):
    book.execute("CREATE TABLE later (id INTEGER PRIMARY KEY AUTOINCREMENT)")
    assert "sqlite_sequence" not in table_names(book)


def test_table_names_are_sorted(book):
    book.execute("CREATE TABLE another (code TEXT)")
    assert table_names(book) == ["another", "thing"]


def test_column_names_are_in_declared_order(book):
    assert column_names(book, "thing") == ["code", "weight"]


def test_column_names_refuses_a_table_that_is_not_there(book):
    with pytest.raises(NotFoundError):
        column_names(book, "nothing")


def test_memory_is_the_sqlite_spelling():
    assert MEMORY == ":memory:"
