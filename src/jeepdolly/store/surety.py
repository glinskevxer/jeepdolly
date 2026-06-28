"""Reading and writing the certificates a carrier has lodged.

Keyed by carrier, cover and policy number, so one carrier may hold two liability
policies at once. That happens every time a policy is replaced a month before the
old one runs out, and the office wants both on file for that month rather than
one overwriting the other and leaving a hole nobody can see afterwards.

The consequence is that "the carrier's liability cover" is a question with more
than one answer, and every caller has to say which day it is asking about.
``in_force`` takes a day for that reason and there is deliberately no version of
it that does not.

Certificates are never edited in place. A corrected amount is a fresh row under
the same policy number, which ``put`` writes over the old one, and a lapsed
certificate stays on file until somebody removes it on purpose.
"""

from __future__ import annotations

import sqlite3

from jeepdolly.errors import NotFoundError
from jeepdolly.ids.reference import Code, code
from jeepdolly.party.surety import Certificate, Cover, lapsing
from jeepdolly.store.sqlite import maybe_one, rows, scalar
from jeepdolly.units.clock import Day, DaySpan, format_day, parse_day
from jeepdolly.units.money import cents

__all__ = ["SuretyStore", "certificate_from_row"]

_COLUMNS = (
    "carrier_code",
    "cover",
    "insurer",
    "policy",
    "amount",
    "first_day",
    "last_day",
)


def certificate_from_row(row: sqlite3.Row) -> Certificate:
    """Build a certificate out of one row."""
    return Certificate(
        carrier=Code(row["carrier_code"]),
        cover=Cover(row["cover"]),
        insurer=row["insurer"],
        policy=row["policy"],
        amount=cents(int(row["amount"])),
        span=DaySpan(parse_day(row["first_day"]), parse_day(row["last_day"])),
    )


class SuretyStore:
    """Every bond and policy the office holds a certificate for."""

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

    def put(self, certificate: Certificate) -> Certificate:
        """Write a certificate, replacing any row under the same policy number."""
        self._known(str(certificate.carrier))
        names = ", ".join(_COLUMNS)
        placeholders = ", ".join("?" for _ in _COLUMNS)
        self.connection.execute(
            f"INSERT INTO certificate ({names}) VALUES ({placeholders})"
            " ON CONFLICT (carrier_code, cover, policy) DO UPDATE SET"
            " insurer = excluded.insurer, amount = excluded.amount,"
            " first_day = excluded.first_day, last_day = excluded.last_day",
            (
                str(certificate.carrier),
                str(certificate.cover),
                certificate.insurer,
                certificate.policy,
                int(certificate.amount),
                format_day(certificate.span.first),
                format_day(certificate.span.last),
            ),
        )
        return certificate

    def find(self, carrier: str, cover: Cover, policy: str) -> Certificate | None:
        """One certificate by carrier, cover and policy number, or ``None``."""
        row = maybe_one(
            self.connection,
            "SELECT * FROM certificate WHERE carrier_code = ? AND cover = ? AND policy = ?",
            (str(code(str(carrier))), str(Cover(cover)), policy.strip()),
        )
        return None if row is None else certificate_from_row(row)

    def get(self, carrier: str, cover: Cover, policy: str) -> Certificate:
        """One certificate, raising if there is no such row."""
        found = self.find(carrier, cover, policy)
        if found is None:
            raise NotFoundError("certificate", f"{code(str(carrier))} {policy}")
        return found

    def for_carrier(self, carrier: str) -> list[Certificate]:
        """Every certificate on file for one carrier, newest expiry first."""
        wanted = self._known(carrier)
        return [
            certificate_from_row(row)
            for row in rows(
                self.connection,
                "SELECT * FROM certificate WHERE carrier_code = ?"
                " ORDER BY last_day DESC, cover, policy",
                (str(wanted),),
            )
        ]

    def in_force(self, carrier: str, on: Day) -> list[Certificate]:
        """The certificates good on a day, one row per cover at most.

        Where a carrier holds two policies for the same cover on the same day,
        the one running longest wins. That is the one the office would chase
        last and the one a decision should be recorded against.
        """
        wanted = self._known(carrier)
        day = format_day(on)
        found = rows(
            self.connection,
            "SELECT * FROM certificate WHERE carrier_code = ?"
            " AND first_day <= ? AND last_day >= ?"
            " ORDER BY cover, last_day DESC, policy",
            (str(wanted), day, day),
        )
        best: dict[str, Certificate] = {}
        for row in found:
            made = certificate_from_row(row)
            best.setdefault(str(made.cover), made)
        return [best[key] for key in sorted(best)]

    def lapsing(self, on: Day, within: int) -> list[Certificate]:
        """Everything across the whole file that runs out inside a window."""
        held = [
            certificate_from_row(row)
            for row in rows(
                self.connection,
                "SELECT * FROM certificate WHERE last_day >= ? ORDER BY last_day, carrier_code",
                (format_day(on),),
            )
        ]
        return lapsing(held, on, within)

    def remove(self, carrier: str, cover: Cover, policy: str) -> None:
        """Take a certificate off the file."""
        self.get(carrier, cover, policy)
        self.connection.execute(
            "DELETE FROM certificate WHERE carrier_code = ? AND cover = ? AND policy = ?",
            (str(code(str(carrier))), str(Cover(cover)), policy.strip()),
        )

    def count(self) -> int:
        """How many certificates are on file."""
        return int(scalar(self.connection, "SELECT count(*) FROM certificate") or 0)

    def __len__(self) -> int:
        return self.count()
