"""Reading and writing carriers.

The store is deliberately dull. It converts rows to carriers and carriers to
rows and it does not know anything about permits, limits or fees. Everything it
raises is one of the package's own errors, so a caller never has to catch
``sqlite3.IntegrityError`` and guess which constraint it was.

``add`` and ``save`` are different on purpose. ``add`` refuses to overwrite,
``save`` refuses to create. A single upsert would be shorter and it would also
quietly turn a mistyped code into a second carrier record, which is the bug the
office actually gets.
"""

from __future__ import annotations

import sqlite3
from typing import ClassVar

from jeepdolly.errors import ConflictError
from jeepdolly.ids.reference import Code, code
from jeepdolly.party.carrier import Carrier
from jeepdolly.store.repo import Repository
from jeepdolly.store.sqlite import maybe_one, one

__all__ = ["CarrierStore", "carrier_from_row"]


def carrier_from_row(row: sqlite3.Row) -> Carrier:
    """Build a carrier out of one row of the carrier table."""
    return Carrier(
        code=Code(row["code"]),
        name=row["name"],
        usdot=int(row["usdot"]),
        home_state=row["home_state"],
        active=bool(row["active"]),
    )


class CarrierStore(Repository[Carrier]):
    """Every carrier the office has on file."""

    table: ClassVar[str] = "carrier"
    key_column: ClassVar[str] = "code"
    kind: ClassVar[str] = "carrier"
    order_by: ClassVar[str] = "code"
    columns: ClassVar[tuple[str, ...]] = ("code", "name", "usdot", "home_state", "active")

    def normalise(self, key: str) -> str:
        """Put a typed key into the form this table stores."""
        return str(code(str(key)))

    def from_row(self, row: sqlite3.Row) -> Carrier:
        """Build the record this store owns out of one row."""
        return carrier_from_row(row)

    def to_row(self, item: Carrier) -> tuple[object, ...]:
        """Flatten the record into the values the columns name."""
        return (
            str(item.code),
            item.name,
            item.usdot,
            item.home_state,
            int(item.active),
        )

    def key_of(self, item: Carrier) -> str:
        """The key this record will be stored under."""
        return str(item.code)

    def before_add(self, item: Carrier) -> None:
        """A USDOT number belongs to one carrier."""
        clash = maybe_one(
            self.connection, "SELECT code FROM carrier WHERE usdot = ?", (item.usdot,)
        )
        if clash is not None:
            raise ConflictError("usdot", item.usdot)

    def save(self, carrier: Carrier) -> Carrier:
        """Overwrite a carrier that is already there."""
        self.get(str(carrier.code))
        clash = maybe_one(
            self.connection,
            "SELECT code FROM carrier WHERE usdot = ? AND code <> ?",
            (carrier.usdot, str(carrier.code)),
        )
        if clash is not None:
            raise ConflictError("usdot", carrier.usdot)
        self.connection.execute(
            "UPDATE carrier SET name = ?, usdot = ?, home_state = ?, active = ? WHERE code = ?",
            (
                carrier.name,
                carrier.usdot,
                carrier.home_state,
                int(carrier.active),
                str(carrier.code),
            ),
        )
        return carrier

    def by_usdot(self, usdot: int) -> Carrier:
        """One carrier by its federal number."""
        row = one(
            self.connection,
            "SELECT * FROM carrier WHERE usdot = ?",
            (usdot,),
            kind="carrier",
        )
        return carrier_from_row(row)

    def active(self) -> list[Carrier]:
        """Every carrier that may still be issued a permit."""
        return self.select("active = 1")

    def search(self, text: str) -> list[Carrier]:
        """Every carrier whose name or code contains this text."""
        needle = f"%{text.strip().lower()}%"
        return self.select("lower(name) LIKE ? OR lower(code) LIKE ?", (needle, needle))
