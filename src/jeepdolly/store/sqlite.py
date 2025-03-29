"""Opening the file, and the four pragmas that make it behave.

Two things about sqlite catch people out and both are handled here rather than
in every caller.

The first is that ``with connection:`` is a *transaction* manager and not a
resource manager. Leaving the block commits and leaves the connection wide open.
Python 3.13 started reporting the leak as a ``ResourceWarning`` and the office's
own test suite turned red on code that had been fine for a year, which is why
``opened`` exists and why nothing in this package calls ``sqlite3.connect``
directly.

The second is that foreign keys are off by default. Every connection turns them
on, and there is a check that walks the package looking for a connect that
forgot.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any

from jeepdolly.errors import BadValueError, NotFoundError

__all__ = [
    "MEMORY",
    "column_names",
    "connect",
    "maybe_one",
    "one",
    "opened",
    "rows",
    "scalar",
    "table_names",
    "writing",
]

#: The path that means an unnamed database held in memory.
MEMORY = ":memory:"

_PRAGMAS = (
    "PRAGMA foreign_keys = ON",
    "PRAGMA journal_mode = WAL",
    "PRAGMA synchronous = NORMAL",
    "PRAGMA busy_timeout = 5000",
)


def connect(path: str | Path) -> sqlite3.Connection:
    """Open a connection with the office's settings applied.

    The caller owns the connection and has to close it. Prefer ``opened``, which
    does that for you; this is here for the few places that hand a live
    connection around.
    """
    if not isinstance(path, str | Path):
        raise BadValueError("path", path, "want a path or a string")
    target = str(path)
    connection = sqlite3.connect(target)
    connection.row_factory = sqlite3.Row
    for pragma in _PRAGMAS:
        if target == MEMORY and pragma.startswith("PRAGMA journal_mode"):
            # An in memory database has no journal to put in write ahead mode
            # and answers "memory" rather than "wal", which is not a failure.
            continue
        connection.execute(pragma)
    return connection


@contextmanager
def opened(path: str | Path) -> Iterator[sqlite3.Connection]:
    """Open a connection and close it when the block ends.

    This is what a ``with`` around a connection ought to mean and does not.
    """
    with closing(connect(path)) as connection:
        yield connection


@contextmanager
def writing(connection: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Run a block inside one immediate transaction.

    ``BEGIN IMMEDIATE`` takes the write lock up front rather than on the first
    write, so two clerks saving at the same moment collide at the start of the
    block instead of halfway through it.
    """
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield connection
    except BaseException:
        connection.rollback()
        raise
    else:
        connection.commit()


def rows(
    connection: sqlite3.Connection, sql: str, parameters: tuple[Any, ...] = ()
) -> list[sqlite3.Row]:
    """Every row a query returns."""
    with closing(connection.execute(sql, parameters)) as cursor:
        return cursor.fetchall()


def maybe_one(
    connection: sqlite3.Connection, sql: str, parameters: tuple[Any, ...] = ()
) -> sqlite3.Row | None:
    """The single row a query returns, or ``None``.

    More than one row is a programming error and raises, because a query written
    to find one record and finding two has already gone wrong.
    """
    found = rows(connection, sql, parameters)
    if len(found) > 1:
        raise BadValueError("query", sql, f"returned {len(found)} rows")
    return found[0] if found else None


def one(
    connection: sqlite3.Connection,
    sql: str,
    parameters: tuple[Any, ...] = (),
    kind: str = "record",
) -> sqlite3.Row:
    """The single row a query returns, raising ``NotFoundError`` if there is none."""
    found = maybe_one(connection, sql, parameters)
    if found is None:
        raise NotFoundError(kind, parameters)
    return found


def scalar(connection: sqlite3.Connection, sql: str, parameters: tuple[Any, ...] = ()) -> Any:
    """The first column of the first row, or ``None`` for no rows."""
    found = maybe_one(connection, sql, parameters)
    return None if found is None else found[0]


def table_names(connection: sqlite3.Connection) -> list[str]:
    """Every table in the file, in name order, sqlite's own left out."""
    found = rows(
        connection,
        "SELECT name FROM sqlite_master WHERE type = 'table'"
        " AND name NOT LIKE 'sqlite_%' ORDER BY name",
    )
    return [row["name"] for row in found]


def column_names(connection: sqlite3.Connection, table: str) -> list[str]:
    """Every column of a table, in declared order."""
    if table not in table_names(connection):
        raise NotFoundError("table", table)
    found = rows(connection, f"PRAGMA table_info({table})")
    return [row["name"] for row in found]
