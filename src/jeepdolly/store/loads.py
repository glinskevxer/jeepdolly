"""Reading and writing loads.

Loads are the one record here with a machine assigned integer key rather than a
reference somebody types. Nobody looks a load up by number at the counter; it is
always reached through the application that describes it. The key exists so the
application has something to point at.

Nondivisibility is stored as the flag and the reason together, and the reader
puts them back through the same validation the writer used, so a row edited by
hand with a reason on a divisible load fails on the way out rather than silently
becoming permittable.
"""

from __future__ import annotations

import sqlite3

from jeepdolly.errors import NotFoundError
from jeepdolly.rig.load import Load
from jeepdolly.store.sqlite import maybe_one, one, rows, scalar
from jeepdolly.units.length import inches
from jeepdolly.units.mass import pounds

__all__ = ["LoadStore", "load_from_row"]

_COLUMNS = (
    "description",
    "weight",
    "width",
    "height",
    "length",
    "front_overhang",
    "rear_overhang",
    "divisible",
    "reason",
)


def load_from_row(row: sqlite3.Row) -> Load:
    """Build a load out of one row of the load table."""
    return Load(
        description=row["description"],
        weight=pounds(int(row["weight"])),
        width=inches(int(row["width"])),
        height=inches(int(row["height"])),
        length=inches(int(row["length"])),
        front_overhang=inches(int(row["front_overhang"])),
        rear_overhang=inches(int(row["rear_overhang"])),
        divisible=bool(row["divisible"]),
        reason=row["reason"],
    )


class LoadStore:
    """Every load the office has described."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Hold the open connection this store reads and writes."""
        self.connection = connection

    def add(self, load: Load) -> int:
        """Write a load and hand back the key it was given."""
        placeholders = ", ".join("?" for _ in _COLUMNS)
        names = ", ".join(_COLUMNS)
        cursor = self.connection.execute(
            f"INSERT INTO load_item ({names}) VALUES ({placeholders})",
            (
                load.description,
                int(load.weight),
                int(load.width),
                int(load.height),
                int(load.length),
                int(load.front_overhang),
                int(load.rear_overhang),
                int(load.divisible),
                load.reason,
            ),
        )
        key = cursor.lastrowid
        cursor.close()
        if key is None:  # pragma: no cover
            raise NotFoundError("load", "just written")
        return int(key)

    def get(self, key: int) -> Load:
        """One load by key, raising if it is not there."""
        row = one(
            self.connection, "SELECT * FROM load_item WHERE id = ?", (int(key),), kind="load"
        )
        return load_from_row(row)

    def find(self, key: int) -> Load | None:
        """One load by key, or ``None``."""
        row = maybe_one(self.connection, "SELECT * FROM load_item WHERE id = ?", (int(key),))
        return None if row is None else load_from_row(row)

    def save(self, key: int, load: Load) -> Load:
        """Overwrite a load that is already there."""
        self.get(key)
        assignments = ", ".join(f"{name} = ?" for name in _COLUMNS)
        self.connection.execute(
            f"UPDATE load_item SET {assignments} WHERE id = ?",
            (
                load.description,
                int(load.weight),
                int(load.width),
                int(load.height),
                int(load.length),
                int(load.front_overhang),
                int(load.rear_overhang),
                int(load.divisible),
                load.reason,
                int(key),
            ),
        )
        return load

    def all(self) -> list[Load]:
        """Every load, oldest first."""
        return [
            load_from_row(row)
            for row in rows(self.connection, "SELECT * FROM load_item ORDER BY id")
        ]

    def keys(self) -> list[int]:
        """Every load key, oldest first."""
        return [
            int(row["id"])
            for row in rows(self.connection, "SELECT id FROM load_item ORDER BY id")
        ]

    def nondivisible(self) -> list[Load]:
        """Every load that could be permitted overweight."""
        return [
            load_from_row(row)
            for row in rows(
                self.connection, "SELECT * FROM load_item WHERE divisible = 0 ORDER BY id"
            )
        ]

    def remove(self, key: int) -> None:
        """Delete a load, raising if it is not there."""
        self.get(key)
        self.connection.execute("DELETE FROM load_item WHERE id = ?", (int(key),))

    def count(self) -> int:
        """How many loads are on file."""
        return int(scalar(self.connection, "SELECT count(*) FROM load_item") or 0)

    def __len__(self) -> int:
        return self.count()
