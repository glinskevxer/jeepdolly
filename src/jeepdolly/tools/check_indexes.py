"""Every foreign key column has an index behind it.

Sqlite indexes the parent side of a reference and not the child side. That is the
right default for a small table and it is wrong for this office: deleting a rig
scans every row of ``rig_axle`` looking for children, and so does every foreign
key check on the file. On a two year old file that is the difference between a
report that returns and one a clerk gives up on.

So this reads the schema out of a freshly migrated file, finds every column that
references another table, and looks for an index whose *first* column is that
one. First rather than any, because an index on ``(day, permit_number)`` does not
help a lookup by permit number, which is the mistake this check was written after.

The exceptions are the columns where the reference is one to one with a primary
key that is already indexed.
"""

from __future__ import annotations

import sqlite3
import sys

from jeepdolly.store.migrations import migrate
from jeepdolly.store.sqlite import MEMORY, opened, rows, table_names

__all__ = ["EXEMPT", "first_columns", "main", "problems", "references"]

#: Columns whose reference is covered by the table's own primary key.
EXEMPT = frozenset(
    {
        "account_terms.carrier_code",
        "account_entry.carrier_code",
        "review_condition.review_reference",
        "permit_finding.permit_number",
        "permit_fee_line.permit_number",
        "permit_escort.permit_number",
        "rig_axle.rig_reference",
        "season_county.season_code",
        "embargo_county.embargo_code",
    }
)


def references(connection: sqlite3.Connection, table: str) -> list[str]:
    """Every column of a table that points at another table."""
    return [row["from"] for row in rows(connection, f"PRAGMA foreign_key_list({table})")]


def first_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    """The leading column of every index on a table, its primary key included."""
    found: set[str] = set()
    for index in rows(connection, f"PRAGMA index_list({table})"):
        columns = rows(connection, f"PRAGMA index_info({index['name']})")
        if columns:
            found.add(columns[0]["name"])
    for column in rows(connection, f"PRAGMA table_info({table})"):
        if column["pk"] == 1:
            found.add(column["name"])
    return found


def problems() -> list[str]:
    """Every foreign key column with nothing indexing it."""
    found: list[str] = []
    with opened(MEMORY) as connection:
        migrate(connection)
        for table in table_names(connection):
            leading = first_columns(connection, table)
            for column in references(connection, table):
                name = f"{table}.{column}"
                if column not in leading and name not in EXEMPT:
                    found.append(f"{name} points at another table and nothing indexes it")
        for name in sorted(EXEMPT):
            table, _, column = name.partition(".")
            if table not in table_names(connection):
                found.append(f"{name} is exempt and its table is gone")
            elif column not in references(connection, table):
                found.append(f"{name} is exempt and is no longer a reference")
    return found


def main() -> int:
    """Report every unindexed reference and fail if there is one."""
    found = problems()
    for line in found:
        print(f"check_indexes: {line}")
    if found:
        print(f"check_indexes: {len(found)} references have no index")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
