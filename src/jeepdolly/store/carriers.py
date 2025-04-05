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

from jeepdolly.errors import ConflictError, NotFoundError
from jeepdolly.ids.reference import Code, code
from jeepdolly.party.carrier import Carrier
from jeepdolly.store.sqlite import maybe_one, one, rows, scalar

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


class CarrierStore:
    """Every carrier the office has on file."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def add(self, carrier: Carrier) -> Carrier:
        """Write a carrier that is not there yet."""
        if self.find(carrier.code) is not None:
            raise ConflictError("carrier", carrier.code)
        clash = maybe_one(
            self.connection, "SELECT code FROM carrier WHERE usdot = ?", (carrier.usdot,)
        )
        if clash is not None:
            raise ConflictError("usdot", carrier.usdot)
        self.connection.execute(
            "INSERT INTO carrier (code, name, usdot, home_state, active)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                str(carrier.code),
                carrier.name,
                carrier.usdot,
                carrier.home_state,
                int(carrier.active),
            ),
        )
        return carrier

    def save(self, carrier: Carrier) -> Carrier:
        """Overwrite a carrier that is already there."""
        self.get(carrier.code)
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

    def get(self, key: str) -> Carrier:
        """One carrier by code, raising if it is not there."""
        wanted = code(str(key))
        row = one(
            self.connection,
            "SELECT * FROM carrier WHERE code = ?",
            (str(wanted),),
            kind="carrier",
        )
        return carrier_from_row(row)

    def find(self, key: str) -> Carrier | None:
        """One carrier by code, or ``None``."""
        wanted = code(str(key))
        row = maybe_one(self.connection, "SELECT * FROM carrier WHERE code = ?", (str(wanted),))
        return None if row is None else carrier_from_row(row)

    def by_usdot(self, usdot: int) -> Carrier:
        """One carrier by its federal number."""
        row = one(
            self.connection,
            "SELECT * FROM carrier WHERE usdot = ?",
            (usdot,),
            kind="carrier",
        )
        return carrier_from_row(row)

    def all(self) -> list[Carrier]:
        """Every carrier, in code order."""
        return [
            carrier_from_row(row)
            for row in rows(self.connection, "SELECT * FROM carrier ORDER BY code")
        ]

    def active(self) -> list[Carrier]:
        """Every carrier that may still be issued a permit."""
        return [
            carrier_from_row(row)
            for row in rows(
                self.connection, "SELECT * FROM carrier WHERE active = 1 ORDER BY code"
            )
        ]

    def search(self, text: str) -> list[Carrier]:
        """Every carrier whose name or code contains this text."""
        needle = f"%{text.strip().lower()}%"
        return [
            carrier_from_row(row)
            for row in rows(
                self.connection,
                "SELECT * FROM carrier WHERE lower(name) LIKE ? OR lower(code) LIKE ?"
                " ORDER BY code",
                (needle, needle),
            )
        ]

    def remove(self, key: str) -> None:
        """Delete a carrier, raising if it is not there."""
        self.get(key)
        self.connection.execute("DELETE FROM carrier WHERE code = ?", (str(code(str(key))),))

    def count(self) -> int:
        """How many carriers are on file."""
        return int(scalar(self.connection, "SELECT count(*) FROM carrier") or 0)

    def __len__(self) -> int:
        return self.count()

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        try:
            return self.find(key) is not None
        except NotFoundError:  # pragma: no cover
            return False
