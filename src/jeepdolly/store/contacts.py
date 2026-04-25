"""Reading and writing carrier contacts.

One row per carrier and role, so a carrier has at most one dispatcher on file.
That is a decision rather than a limitation: a second dispatcher's number in a
free text field is what the office had before, and nobody ever knew which of the
two was current.

Promoting a contact to primary demotes whichever one held it, in the same
transaction. The file has a partial unique index that would refuse two, and doing
the demotion here rather than leaving the caller to trip over the index is the
difference between a clerk seeing "already primary" and seeing a constraint name.
"""

from __future__ import annotations

import sqlite3

from jeepdolly.errors import NotFoundError
from jeepdolly.ids.reference import Code, code
from jeepdolly.party.contact import Contact, Role, digits_of
from jeepdolly.store.sqlite import maybe_one, rows, scalar

__all__ = ["ContactStore", "contact_from_row"]

_COLUMNS = (
    "carrier_code",
    "role",
    "name",
    "number",
    "email",
    "primary_one",
)


def contact_from_row(row: sqlite3.Row) -> Contact:
    """Build a contact out of one row."""
    return Contact(
        carrier=Code(row["carrier_code"]),
        role=Role(row["role"]),
        name=row["name"],
        number=row["number"],
        email=row["email"],
        primary=bool(row["primary_one"]),
    )


class ContactStore:
    """Everyone the office has a number for."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Hold the open connection this store reads and writes."""
        self.connection = connection

    def _known(self, carrier: str) -> Code:
        """Check a carrier is on file and hand back its normalised code."""
        wanted = code(str(carrier))
        found = maybe_one(
            self.connection, "SELECT 1 FROM carrier WHERE code = ?", (str(wanted),)
        )
        if found is None:
            raise NotFoundError("carrier", str(wanted))
        return wanted

    def put(self, contact: Contact) -> Contact:
        """Write a contact, replacing whoever held that role."""
        self._known(str(contact.carrier))
        if contact.primary:
            self.connection.execute(
                "UPDATE contact SET primary_one = 0 WHERE carrier_code = ?",
                (str(contact.carrier),),
            )
        names = ", ".join(_COLUMNS)
        placeholders = ", ".join("?" for _ in _COLUMNS)
        self.connection.execute(
            f"INSERT INTO contact ({names}) VALUES ({placeholders})"
            " ON CONFLICT (carrier_code, role) DO UPDATE SET"
            " name = excluded.name, number = excluded.number,"
            " email = excluded.email, primary_one = excluded.primary_one",
            (
                str(contact.carrier),
                str(contact.role),
                contact.name,
                contact.number,
                contact.email,
                int(contact.primary),
            ),
        )
        return contact

    def get(self, carrier: str, role: Role) -> Contact:
        """One contact by carrier and role, raising if there is none."""
        found = self.find(carrier, role)
        if found is None:
            raise NotFoundError("contact", f"{code(str(carrier))} {Role(role)}")
        return found

    def find(self, carrier: str, role: Role) -> Contact | None:
        """One contact by carrier and role, or ``None``."""
        row = maybe_one(
            self.connection,
            "SELECT * FROM contact WHERE carrier_code = ? AND role = ?",
            (str(code(str(carrier))), str(Role(role))),
        )
        return None if row is None else contact_from_row(row)

    def for_carrier(self, carrier: str) -> list[Contact]:
        """Every contact at one carrier, primary first then by role."""
        wanted = self._known(carrier)
        return [
            contact_from_row(row)
            for row in rows(
                self.connection,
                "SELECT * FROM contact WHERE carrier_code = ? ORDER BY primary_one DESC, role",
                (str(wanted),),
            )
        ]

    def primary(self, carrier: str) -> Contact | None:
        """The one to ring when the office does not know which role it wants."""
        row = maybe_one(
            self.connection,
            "SELECT * FROM contact WHERE carrier_code = ? AND primary_one = 1",
            (str(code(str(carrier))),),
        )
        return None if row is None else contact_from_row(row)

    def promote(self, carrier: str, role: Role) -> Contact:
        """Make one contact the primary, demoting whoever held it."""
        found = self.get(carrier, role)
        return self.put(found.promoted())

    def by_number(self, number: str) -> list[Contact]:
        """Everyone the office has under one phone number, however it was typed."""
        return [
            contact_from_row(row)
            for row in rows(
                self.connection,
                "SELECT * FROM contact WHERE number = ? ORDER BY carrier_code, role",
                (digits_of(number),),
            )
        ]

    def remove(self, carrier: str, role: Role) -> None:
        """Take a contact off the file."""
        self.get(carrier, role)
        self.connection.execute(
            "DELETE FROM contact WHERE carrier_code = ? AND role = ?",
            (str(code(str(carrier))), str(Role(role))),
        )

    def count(self) -> int:
        """How many contacts are on file."""
        return int(scalar(self.connection, "SELECT count(*) FROM contact") or 0)

    def __len__(self) -> int:
        return self.count()
