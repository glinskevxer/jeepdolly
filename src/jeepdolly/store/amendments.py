"""Reading and writing the amendments made against issued permits.

An amendment row does not hold what the permit used to say. It holds the permit
number and the key of the application that now applies, and the old wording is
read back off whatever the permit was issued against or off the amendment before
it. The office wanted the history to be a chain rather than a set of snapshots,
because a snapshot per amendment is where two clerks amending the same permit
twenty minutes apart stops being detectable.

That makes ordering load bearing. Amendments come back oldest first everywhere in
here, and ``current`` walks to the end of the chain rather than taking a maximum
of anything, because two amendments filed on the same day are ordered by the key
and not by the date.

The charge is stored beside the row. It is worked out at the counter against the
schedule of the day, and recomputing it later against today's schedule would
quietly change what a carrier was billed two years ago.

Filing the new application is the caller's job. The desk files it to assess and
price it, and a store that filed its own copy would leave two of every amended
application behind.
"""

from __future__ import annotations

import sqlite3

from jeepdolly.errors import NotFoundError
from jeepdolly.ids.reference import Serial, serial
from jeepdolly.permit.amendment import Amendment, Change
from jeepdolly.permit.application import Application
from jeepdolly.store.applications import ApplicationStore
from jeepdolly.store.sqlite import maybe_one, one, rows, scalar
from jeepdolly.units.clock import Day, format_day, parse_day
from jeepdolly.units.money import Money, cents

__all__ = ["AmendmentStore", "FiledAmendment"]


class FiledAmendment:
    """An amendment with the key and the charge the office filed it under."""

    __slots__ = ("amendment", "application_key", "charged", "key")

    def __init__(
        self, key: int, amendment: Amendment, application_key: int, charged: Money
    ) -> None:
        """Hold one amendment with everything the office recorded beside it."""
        self.key = key
        self.amendment = amendment
        self.application_key = application_key
        self.charged = charged

    @property
    def number(self) -> Serial:
        """Which permit was amended."""
        return self.amendment.number

    @property
    def changes(self) -> tuple[Change, ...]:
        """What this amendment moved."""
        return self.amendment.changes

    def __repr__(self) -> str:
        return f"<FiledAmendment {self.key} {self.amendment}>"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FiledAmendment):
            return NotImplemented
        return (self.key, self.amendment) == (other.key, other.amendment)

    def __hash__(self) -> int:
        return hash((self.key, self.amendment))


class AmendmentStore:
    """Every amendment the office has written against an issued permit."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Hold the open connection and the application store beside it."""
        self.connection = connection
        self.applications = ApplicationStore(connection)

    def _issued_against(self, number: str) -> Application:
        """What the permit was issued against, before any amendment."""
        row = one(
            self.connection,
            "SELECT application_id FROM permit WHERE number = ?",
            (str(serial(str(number))),),
            kind="permit",
        )
        return self.applications.get(int(row["application_id"])).application

    def add(self, amendment: Amendment, charged: Money, application_key: int) -> FiledAmendment:
        """Write an amendment against an application that is already on file.

        The key is passed in rather than filed here. The desk has to file the
        new application anyway to assess and price it, and having the store file
        a second copy left two identical applications behind every material
        amendment, which the application count found and nothing else would have.
        """
        number = str(amendment.number)
        found = maybe_one(self.connection, "SELECT 1 FROM permit WHERE number = ?", (number,))
        if found is None:
            raise NotFoundError("permit", number)
        filed = self.applications.get(int(application_key))
        cursor = self.connection.execute(
            "INSERT INTO amendment"
            " (permit_number, application_key, filed_on, note, changes, material, charged)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                number,
                filed.key,
                format_day(amendment.filed_on),
                amendment.note,
                ",".join(str(one) for one in amendment.changes),
                int(amendment.material),
                int(cents(int(charged))),
            ),
        )
        key = cursor.lastrowid
        cursor.close()
        assert key is not None
        return FiledAmendment(
            key=int(key),
            amendment=amendment,
            application_key=filed.key,
            charged=cents(int(charged)),
        )

    def _build(self, row: sqlite3.Row, was: Application) -> FiledAmendment:
        """Rebuild one amendment against whatever the permit said before it."""
        now = self.applications.get(int(row["application_key"])).application
        made = Amendment(
            number=Serial(row["permit_number"]),
            was=was,
            now=now,
            filed_on=parse_day(row["filed_on"]),
            note=row["note"],
        )
        return FiledAmendment(
            key=int(row["id"]),
            amendment=made,
            application_key=int(row["application_key"]),
            charged=cents(int(row["charged"])),
        )

    def for_permit(self, number: str) -> list[FiledAmendment]:
        """Every amendment against one permit, oldest first."""
        wanted = str(serial(str(number)))
        was = self._issued_against(wanted)
        found: list[FiledAmendment] = []
        for row in rows(
            self.connection,
            "SELECT * FROM amendment WHERE permit_number = ? ORDER BY filed_on, id",
            (wanted,),
        ):
            made = self._build(row, was)
            found.append(made)
            was = made.amendment.now
        return found

    def current(self, number: str) -> Application:
        """What the permit says now, after every amendment against it."""
        chain = self.for_permit(number)
        if not chain:
            return self._issued_against(number)
        return chain[-1].amendment.now

    def latest(self, number: str) -> FiledAmendment | None:
        """The last amendment against one permit, or ``None``."""
        chain = self.for_permit(number)
        return chain[-1] if chain else None

    def on_day(self, day: Day) -> list[FiledAmendment]:
        """Every amendment filed on one day, across every permit."""
        numbers = rows(
            self.connection,
            "SELECT DISTINCT permit_number FROM amendment WHERE filed_on = ?"
            " ORDER BY permit_number",
            (format_day(day),),
        )
        found: list[FiledAmendment] = []
        for row in numbers:
            found.extend(
                one
                for one in self.for_permit(row["permit_number"])
                if one.amendment.filed_on == day
            )
        return found

    def count(self) -> int:
        """How many amendments are on file."""
        return int(scalar(self.connection, "SELECT count(*) FROM amendment") or 0)

    def __len__(self) -> int:
        return self.count()
