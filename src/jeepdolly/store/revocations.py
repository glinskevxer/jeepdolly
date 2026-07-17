"""Reading and writing why permits were pulled.

One row per permit, because a permit can only be pulled once. The permit's own
state says it is void and this says why, which is a split the office argued about
and settled on the grounds that the permit table is read on every list and this
table is read twice a year.

The carrier code is copied onto the row rather than reached through the permit.
That is denormalised on purpose: the question this table exists to answer is
"is this carrier blocked today", it is asked at the counter while somebody waits,
and joining three tables to answer it was the reason the check kept getting
skipped.
"""

from __future__ import annotations

import sqlite3

from jeepdolly.errors import ConflictError, NotFoundError
from jeepdolly.ids.reference import Serial, serial
from jeepdolly.permit.revoke import Cause, Revocation, blocked_on
from jeepdolly.store.sqlite import maybe_one, one, rows, scalar
from jeepdolly.units.clock import Day, format_day, parse_day
from jeepdolly.units.money import cents

__all__ = ["RevocationStore", "revocation_from_row"]


def revocation_from_row(row: sqlite3.Row) -> Revocation:
    """Build a revocation out of one row."""
    return Revocation(
        number=Serial(row["permit_number"]),
        cause=Cause(row["cause"]),
        on=parse_day(row["pulled_on"]),
        refunded=cents(int(row["refunded"])),
        detail=row["detail"],
    )


class RevocationStore:
    """Every permit the office has pulled, and why."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Hold the open connection this store reads and writes."""
        self.connection = connection

    def add(self, revocation: Revocation, carrier: str) -> Revocation:
        """Write a revocation against a permit that has not been pulled before."""
        number = str(revocation.number)
        found = maybe_one(self.connection, "SELECT 1 FROM permit WHERE number = ?", (number,))
        if found is None:
            raise NotFoundError("permit", number)
        if self.find(number) is not None:
            raise ConflictError("revocation", number)
        self.connection.execute(
            "INSERT INTO revocation"
            " (permit_number, carrier_code, cause, pulled_on, refunded, detail)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                number,
                str(carrier),
                str(revocation.cause),
                format_day(revocation.on),
                int(revocation.refunded),
                revocation.detail,
            ),
        )
        return revocation

    def find(self, number: str) -> Revocation | None:
        """Why one permit was pulled, or ``None`` if it was not."""
        row = maybe_one(
            self.connection,
            "SELECT * FROM revocation WHERE permit_number = ?",
            (str(serial(str(number))),),
        )
        return None if row is None else revocation_from_row(row)

    def get(self, number: str) -> Revocation:
        """Why one permit was pulled, raising if it was not."""
        row = one(
            self.connection,
            "SELECT * FROM revocation WHERE permit_number = ?",
            (str(serial(str(number))),),
            kind="revocation",
        )
        return revocation_from_row(row)

    def for_carrier(self, carrier: str) -> list[Revocation]:
        """Every permit pulled on one carrier, oldest first."""
        return [
            revocation_from_row(row)
            for row in rows(
                self.connection,
                "SELECT * FROM revocation WHERE carrier_code = ?"
                " ORDER BY pulled_on, permit_number",
                (str(carrier),),
            )
        ]

    def blocking(self, carrier: str, day: Day) -> Revocation | None:
        """The revocation stopping this carrier being issued anything today."""
        return blocked_on(self.for_carrier(carrier), day)

    def of_cause(self, cause: Cause) -> list[Revocation]:
        """Every permit pulled for one reason, oldest first."""
        return [
            revocation_from_row(row)
            for row in rows(
                self.connection,
                "SELECT * FROM revocation WHERE cause = ? ORDER BY pulled_on, permit_number",
                (str(Cause(cause)),),
            )
        ]

    def count(self) -> int:
        """How many revocations are on file."""
        return int(scalar(self.connection, "SELECT count(*) FROM revocation") or 0)

    def __len__(self) -> int:
        return self.count()
