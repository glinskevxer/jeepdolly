"""Reading and writing weight tickets and what they came to.

The axle weights go in their own table, one row per pad, rather than as a comma
separated column. That was not the first design. The first design was a text
column, and it survived until somebody needed the third axle of every ticket
written in the last year and found there was no way to ask for it.

A ticket and its violations are written together or not at all, because a ticket
in the file with no violations means the rig was legal and that is a thing the
office says out loud. Half a write leaves a legal rig on the record that was not.

Violations are read back oldest first and always for a whole carrier, because
the only question ever asked of them is how many this carrier has, which is what
decides what the next one costs.
"""

from __future__ import annotations

import sqlite3

from jeepdolly.enforce.ticket import Discrepancy, Ticket
from jeepdolly.enforce.violation import Violation
from jeepdolly.errors import ConflictError, NotFoundError
from jeepdolly.ids.reference import Serial, serial
from jeepdolly.store.sqlite import maybe_one, rows, scalar
from jeepdolly.units.clock import Day, format_day, parse_day
from jeepdolly.units.mass import pounds
from jeepdolly.units.money import cents

__all__ = ["EnforcementStore", "violation_from_row"]


def violation_from_row(row: sqlite3.Row) -> Violation:
    """Build a violation out of one row."""
    return Violation(
        on=parse_day(row["found_on"]),
        ticket=Serial(row["ticket_number"]),
        permit=Serial(row["permit_number"]),
        carrier=row["carrier_code"],
        kind=Discrepancy(row["kind"]),
        over=pounds(int(row["over"])),
        penalty=cents(int(row["penalty"])),
    )


class EnforcementStore:
    """Every weight ticket the office has taken in, and what each one cost."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Hold the open connection this store reads and writes."""
        self.connection = connection

    def next_number(self) -> Serial:
        """The reference the next weight ticket will be filed under."""
        held = scalar(self.connection, "SELECT count(*) FROM ticket") or 0
        return serial(f"WT-{int(held) + 1:05d}")

    def add(
        self, ticket: Ticket, violations: list[Violation], forgiven: bool = False
    ) -> Ticket:
        """Write a ticket, its pads and whatever it came to, in one go."""
        number = str(ticket.number)
        if self.find(number) is not None:
            raise ConflictError("ticket", number)
        found = maybe_one(
            self.connection,
            "SELECT 1 FROM permit WHERE number = ?",
            (str(ticket.permit),),
        )
        if found is None:
            raise NotFoundError("permit", str(ticket.permit))
        self.connection.execute(
            "INSERT INTO ticket (number, permit_number, weighed_on, place, officer, forgiven)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                number,
                str(ticket.permit),
                format_day(ticket.weighed_on),
                ticket.place,
                ticket.officer,
                int(forgiven),
            ),
        )
        self.connection.executemany(
            "INSERT INTO ticket_axle (ticket_number, position, weight) VALUES (?, ?, ?)",
            [(number, i, int(w)) for i, w in enumerate(ticket.axles, start=1)],
        )
        self.connection.executemany(
            "INSERT INTO violation"
            " (ticket_number, permit_number, carrier_code, found_on, kind, over, penalty)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    number,
                    str(one.permit),
                    one.carrier,
                    format_day(one.on),
                    str(one.kind),
                    int(one.over),
                    int(one.penalty),
                )
                for one in violations
            ],
        )
        return ticket

    def _axles(self, number: str) -> tuple[int, ...]:
        """The pad weights off one ticket, in the order they were taken."""
        return tuple(
            int(row["weight"])
            for row in rows(
                self.connection,
                "SELECT weight FROM ticket_axle WHERE ticket_number = ? ORDER BY position",
                (number,),
            )
        )

    def _build(self, row: sqlite3.Row) -> Ticket:
        """Rebuild one ticket with the pads that belong to it."""
        number = str(row["number"])
        return Ticket(
            number=Serial(number),
            permit=Serial(row["permit_number"]),
            weighed_on=parse_day(row["weighed_on"]),
            place=row["place"],
            officer=row["officer"],
            axles=tuple(pounds(one) for one in self._axles(number)),
        )

    def find(self, number: str) -> Ticket | None:
        """One ticket by reference, or ``None``."""
        row = maybe_one(
            self.connection,
            "SELECT * FROM ticket WHERE number = ?",
            (str(serial(str(number))),),
        )
        return None if row is None else self._build(row)

    def get(self, number: str) -> Ticket:
        """One ticket by reference, raising if it is not there."""
        found = self.find(number)
        if found is None:
            raise NotFoundError("ticket", str(number))
        return found

    def forgiven(self, number: str) -> bool:
        """Was this ticket written against a permit that had been amended."""
        row = maybe_one(
            self.connection,
            "SELECT forgiven FROM ticket WHERE number = ?",
            (str(serial(str(number))),),
        )
        if row is None:
            raise NotFoundError("ticket", str(number))
        return bool(row["forgiven"])

    def for_permit(self, number: str) -> list[Ticket]:
        """Every ticket written against one permit, oldest first."""
        return [
            self._build(row)
            for row in rows(
                self.connection,
                "SELECT * FROM ticket WHERE permit_number = ? ORDER BY weighed_on, number",
                (str(serial(str(number))),),
            )
        ]

    def violations_of(self, carrier: str) -> list[Violation]:
        """Every violation against one carrier, oldest first."""
        return [
            violation_from_row(row)
            for row in rows(
                self.connection,
                "SELECT * FROM violation WHERE carrier_code = ? ORDER BY found_on, id",
                (str(carrier),),
            )
        ]

    def violations_on(self, ticket: str) -> list[Violation]:
        """Every violation off one ticket, in the order they were worked out."""
        return [
            violation_from_row(row)
            for row in rows(
                self.connection,
                "SELECT * FROM violation WHERE ticket_number = ? ORDER BY id",
                (str(serial(str(ticket))),),
            )
        ]

    def since(self, day: Day) -> list[Violation]:
        """Every violation on or after a day, across every carrier."""
        return [
            violation_from_row(row)
            for row in rows(
                self.connection,
                "SELECT * FROM violation WHERE found_on >= ? ORDER BY found_on, id",
                (format_day(day),),
            )
        ]

    def count(self) -> int:
        """How many tickets are on file."""
        return int(scalar(self.connection, "SELECT count(*) FROM ticket") or 0)

    def __len__(self) -> int:
        return self.count()
