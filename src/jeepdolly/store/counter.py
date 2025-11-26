"""Handing out the next reference number, once, for every store that needs one.

Four stores had the same six lines: take the highest reference in the table,
read its counter out, add one, format it back. Four copies of a thing that has to
agree with itself is three copies too many, and two of them had already drifted
in a way nothing would have caught: one read ``max(reference)`` and one read
``max(rowid)``, which are the same number until a reference is inserted by hand.

Taking the maximum of the *text* is safe because every reference is fixed width
and zero padded, so lexical order is numeric order. That stops being true the day
a counter outgrows its width, which is what the generous widths in
``ids.reference`` are for, and there is a test that says so.
"""

from __future__ import annotations

import sqlite3

from jeepdolly.errors import BadValueError
from jeepdolly.ids.reference import Serial, SerialKind
from jeepdolly.store.sqlite import scalar, table_names

__all__ = ["highest", "next_serial"]


def highest(connection: sqlite3.Connection, table: str, column: str) -> str | None:
    """The largest reference in a table, or ``None`` when it is empty."""
    if table not in table_names(connection):
        raise BadValueError("table", table, "is not in this file")
    found = scalar(connection, f"SELECT max({column}) FROM {table}")
    return None if found is None else str(found)


def next_serial(
    connection: sqlite3.Connection, kind: SerialKind, table: str, column: str
) -> Serial:
    """The reference the next record in a table will be filed under.

    The counter is derived rather than stored, so a file restored from a backup
    that is missing its last few records reissues those numbers rather than
    skipping them. That is the office's choice: a gap in the numbering is harder
    to explain to an auditor than a reused number on a record that is not there.
    """
    top = highest(connection, table, column)
    if top is None:
        return kind.format(1)
    return kind.format(kind.number(top) + 1)
