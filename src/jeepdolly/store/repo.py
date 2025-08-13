"""One base class for the stores that are a table with a text key.

Four of them were the same forty lines with the table name changed: carriers,
junctions, stretches and structures. Each had its own copy of "look it up, raise
if it is not there", its own copy of "refuse a key that is taken", and its own
copy of the count. Three of the four had drifted: one normalised the key on
``find`` and not on ``remove``, one raised the wrong error class, and one had
quietly stopped ordering its listing.

Subclasses say what the table is called, how to turn a row into a record and a
record into a row, and nothing else. Anything a subclass genuinely needs on top,
like the carrier's second unique column, goes in ``before_add`` rather than in a
reimplementation of ``add``.
"""

from __future__ import annotations

import sqlite3
from typing import ClassVar, Generic, TypeVar

from jeepdolly.errors import ConflictError
from jeepdolly.store.sqlite import maybe_one, one, rows, scalar

__all__ = ["Repository"]

T = TypeVar("T")


class Repository(Generic[T]):
    """A table keyed by one text column, read and written as records."""

    #: The table this store owns.
    table: ClassVar[str]

    #: The column holding the key a clerk types.
    key_column: ClassVar[str]

    #: What to call the record in an error message.
    kind: ClassVar[str]

    #: What to order a listing by.
    order_by: ClassVar[str]

    #: Every column written, in the order ``to_row`` returns them.
    columns: ClassVar[tuple[str, ...]]

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Hold the open connection every query runs on."""
        self.connection = connection

    def normalise(self, key: str) -> str:
        """Put a typed key into the form the table stores."""
        raise NotImplementedError

    def from_row(self, row: sqlite3.Row) -> T:
        """Build a record out of one row."""
        raise NotImplementedError

    def to_row(self, item: T) -> tuple[object, ...]:
        """Flatten a record into the values ``columns`` names."""
        raise NotImplementedError

    def key_of(self, item: T) -> str:
        """The key a record will be stored under."""
        raise NotImplementedError

    def before_add(self, item: T) -> None:
        """Anything else that has to be true before a record is written."""

    def add(self, item: T) -> T:
        """Write a record that is not there yet."""
        key = self.key_of(item)
        if self.find(key) is not None:
            raise ConflictError(self.kind, key)
        self.before_add(item)
        names = ", ".join(self.columns)
        placeholders = ", ".join("?" for _ in self.columns)
        self.connection.execute(
            f"INSERT INTO {self.table} ({names}) VALUES ({placeholders})", self.to_row(item)
        )
        return item

    def find(self, key: str) -> T | None:
        """One record by key, or ``None``."""
        row = maybe_one(
            self.connection,
            f"SELECT * FROM {self.table} WHERE {self.key_column} = ?",
            (self.normalise(str(key)),),
        )
        return None if row is None else self.from_row(row)

    def get(self, key: str) -> T:
        """One record by key, raising if it is not there."""
        row = one(
            self.connection,
            f"SELECT * FROM {self.table} WHERE {self.key_column} = ?",
            (self.normalise(str(key)),),
            kind=self.kind,
        )
        return self.from_row(row)

    def all(self) -> list[T]:
        """Every record, in the store's own order."""
        return self.select("")

    def select(self, where: str, parameters: tuple[object, ...] = ()) -> list[T]:
        """Every record matching a clause, in the store's own order."""
        clause = f" WHERE {where}" if where else ""
        return [
            self.from_row(row)
            for row in rows(
                self.connection,
                f"SELECT * FROM {self.table}{clause} ORDER BY {self.order_by}",
                parameters,
            )
        ]

    def remove(self, key: str) -> None:
        """Delete a record, raising if it is not there."""
        self.get(key)
        self.connection.execute(
            f"DELETE FROM {self.table} WHERE {self.key_column} = ?",
            (self.normalise(str(key)),),
        )

    def count(self) -> int:
        """How many records are on file."""
        return int(scalar(self.connection, f"SELECT count(*) FROM {self.table}") or 0)

    def __len__(self) -> int:
        return self.count()

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        try:
            return self.find(key) is not None
        except Exception:  # noqa: BLE001
            return False
