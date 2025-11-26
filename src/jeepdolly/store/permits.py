"""Reading and writing permits, with the working that produced them.

The findings, the fee lines and the escorts are written out beside the permit
rather than recomputed on read. That is deliberate duplication and it is the
whole point of the table: a permit issued under last spring's frost law orders
has to keep showing last spring's numbers, and recomputing it today would
quietly change a record the carrier is holding a paper copy of.

Only issued permits get a number and a row here. A refusal or a referral is a
decision without a permit, and the office keeps those on the application rather
than inventing a permit number for something that was never issued.
"""

from __future__ import annotations

import sqlite3

from jeepdolly.billing.invoice import Invoice
from jeepdolly.billing.tariff import FeeLine
from jeepdolly.errors import ConflictError
from jeepdolly.ids.reference import PERMIT, Serial, code, serial
from jeepdolly.limits.finding import Finding, Severity
from jeepdolly.permit.decision import Decision, Outcome
from jeepdolly.permit.permit import Permit, State
from jeepdolly.store.applications import ApplicationStore
from jeepdolly.store.counter import next_serial
from jeepdolly.store.sqlite import maybe_one, one, rows, scalar
from jeepdolly.travel.escort import Escort, Role
from jeepdolly.units.clock import Day, DaySpan, format_day, parse_day
from jeepdolly.units.distance import hundredths
from jeepdolly.units.mass import pounds
from jeepdolly.units.money import cents

__all__ = [
    "REASON_SEPARATOR",
    "PermitStore",
]

#: Reasons are joined with this inside one escort row.
REASON_SEPARATOR = " | "


class PermitStore:
    """Every permit the office has issued."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Hold the open connection and the application store beside it."""
        self.connection = connection
        self.applications = ApplicationStore(connection)

    def next_number(self) -> Serial:
        """The number the next permit will be issued under."""
        return next_serial(self.connection, PERMIT, "permit", "number")

    def add(self, permit: Permit, application_key: int) -> Permit:
        """Write an issued permit and everything that went into it."""
        if self.find(str(permit.number)) is not None:
            raise ConflictError("permit", permit.number)
        self.applications.get(application_key)
        decision = permit.decision
        self.connection.execute(
            "INSERT INTO permit (number, application_id, outcome, decided_on, issued_on,"
            " first_day, last_day, state, reason, replaced_by, distance)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(permit.number),
                int(application_key),
                str(decision.outcome),
                format_day(decision.decided_on),
                format_day(permit.issued_on),
                format_day(permit.span.first),
                format_day(permit.span.last),
                str(permit.state),
                permit.reason,
                None if permit.replaced_by is None else str(permit.replaced_by),
                None if decision.distance is None else int(decision.distance),
            ),
        )
        self._write_findings(permit)
        self._write_fee_lines(permit)
        self._write_escorts(permit)
        return permit

    def _write_findings(self, permit: Permit) -> None:
        for position, finding in enumerate(permit.decision.findings):
            self.connection.execute(
                "INSERT INTO permit_finding (permit_number, position, rule, subject,"
                " severity, detail, excess) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    str(permit.number),
                    position,
                    finding.rule,
                    finding.subject,
                    str(finding.severity),
                    finding.detail,
                    int(finding.excess),
                ),
            )

    def _write_fee_lines(self, permit: Permit) -> None:
        invoice = permit.decision.invoice
        assert invoice is not None
        for position, line in enumerate(invoice.lines):
            self.connection.execute(
                "INSERT INTO permit_fee_line (permit_number, position, code, detail, amount)"
                " VALUES (?, ?, ?, ?, ?)",
                (str(permit.number), position, line.code, line.detail, int(line.amount)),
            )

    def _write_escorts(self, permit: Permit) -> None:
        for position, escort in enumerate(permit.decision.escorts):
            self.connection.execute(
                "INSERT INTO permit_escort (permit_number, position, role, reasons)"
                " VALUES (?, ?, ?, ?)",
                (
                    str(permit.number),
                    position,
                    str(escort.role),
                    REASON_SEPARATOR.join(escort.reasons),
                ),
            )

    def _read_findings(self, number: Serial) -> tuple[Finding, ...]:
        return tuple(
            Finding(
                rule=row["rule"],
                subject=row["subject"],
                severity=Severity(row["severity"]),
                detail=row["detail"],
                excess=pounds(int(row["excess"])),
            )
            for row in rows(
                self.connection,
                "SELECT * FROM permit_finding WHERE permit_number = ? ORDER BY position",
                (str(number),),
            )
        )

    def _read_invoice(self, number: Serial) -> Invoice:
        return Invoice(
            lines=tuple(
                FeeLine(
                    code=row["code"], detail=row["detail"], amount=cents(int(row["amount"]))
                )
                for row in rows(
                    self.connection,
                    "SELECT * FROM permit_fee_line WHERE permit_number = ? ORDER BY position",
                    (str(number),),
                )
            )
        )

    def _read_escorts(self, number: Serial) -> tuple[Escort, ...]:
        return tuple(
            Escort(
                role=Role(row["role"]),
                reasons=tuple(row["reasons"].split(REASON_SEPARATOR)),
            )
            for row in rows(
                self.connection,
                "SELECT * FROM permit_escort WHERE permit_number = ? ORDER BY position",
                (str(number),),
            )
        )

    def _from_row(self, row: sqlite3.Row) -> Permit:
        number = serial(row["number"])
        filed = self.applications.get(int(row["application_id"]))
        distance = row["distance"]
        decision = Decision(
            application=filed.application,
            outcome=Outcome(row["outcome"]),
            findings=self._read_findings(number),
            escorts=self._read_escorts(number),
            decided_on=parse_day(row["decided_on"]),
            invoice=self._read_invoice(number),
            distance=None if distance is None else hundredths(int(distance)),
        )
        return Permit(
            number=number,
            decision=decision,
            issued_on=parse_day(row["issued_on"]),
            span=DaySpan(parse_day(row["first_day"]), parse_day(row["last_day"])),
            state=State(row["state"]),
            reason=row["reason"],
            replaced_by=None if row["replaced_by"] is None else serial(row["replaced_by"]),
        )

    def get(self, key: str) -> Permit:
        """One permit by number, raising if it is not there."""
        row = one(
            self.connection,
            "SELECT * FROM permit WHERE number = ?",
            (str(serial(str(key))),),
            kind="permit",
        )
        return self._from_row(row)

    def find(self, key: str) -> Permit | None:
        """One permit by number, or ``None``."""
        row = maybe_one(
            self.connection, "SELECT * FROM permit WHERE number = ?", (str(serial(str(key))),)
        )
        return None if row is None else self._from_row(row)

    def save_state(self, permit: Permit) -> Permit:
        """Write back a state change, leaving the working alone."""
        self.get(str(permit.number))
        self.connection.execute(
            "UPDATE permit SET state = ?, reason = ?, replaced_by = ?,"
            " first_day = ?, last_day = ? WHERE number = ?",
            (
                str(permit.state),
                permit.reason,
                None if permit.replaced_by is None else str(permit.replaced_by),
                format_day(permit.span.first),
                format_day(permit.span.last),
                str(permit.number),
            ),
        )
        return permit

    def all(self) -> list[Permit]:
        """Every permit, in number order."""
        return [
            self._from_row(row)
            for row in rows(self.connection, "SELECT * FROM permit ORDER BY number")
        ]

    def for_carrier(self, carrier: str) -> list[Permit]:
        """Every permit issued to one carrier, in number order."""
        owner = code(str(carrier))
        return [
            self._from_row(row)
            for row in rows(
                self.connection,
                "SELECT p.* FROM permit p JOIN application a ON a.id = p.application_id"
                " WHERE a.carrier_code = ? ORDER BY p.number",
                (str(owner),),
            )
        ]

    def good_on(self, day: Day) -> list[Permit]:
        """Every permit a load may move under on one day."""
        stamp = format_day(day)
        return [
            self._from_row(row)
            for row in rows(
                self.connection,
                "SELECT * FROM permit WHERE state = 'active' AND first_day <= ?"
                " AND last_day >= ? ORDER BY number",
                (stamp, stamp),
            )
        ]

    def count(self) -> int:
        """How many permits have been issued."""
        return int(scalar(self.connection, "SELECT count(*) FROM permit") or 0)

    def __len__(self) -> int:
        return self.count()
