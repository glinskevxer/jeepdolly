"""The journal: what the office did, in the order it did it.

Every other table holds the current state of something. This one holds what
happened, and nothing in it is ever changed or deleted. It is what answers "why
is this permit void" a year later, when the person who voided it has left and
the reason field says "cancelled".

Entries are not derived from the other tables and the other tables are not
derived from these. The journal is written beside the change, in the same
transaction, so a change that rolls back takes its entry with it. That is the
one guarantee this design rests on and it is why the writer takes a connection
rather than opening its own.

There is no code for looking up "the current state" here. Anything that walks the
journal to work out state is a bug waiting for its first gap.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from dataclasses import dataclass
from enum import StrEnum

from jeepdolly.errors import BadValueError
from jeepdolly.store.sqlite import rows, scalar
from jeepdolly.units.clock import Day, DaySpan, format_day, parse_day

__all__ = ["MAX_DETAIL", "Event", "EventKind", "HistoryStore"]

MAX_DETAIL = 200


class EventKind(StrEnum):
    """What sort of thing happened."""

    FILED = "filed"
    QUOTED = "quoted"
    ISSUED = "issued"
    VOIDED = "voided"
    EXTENDED = "extended"
    AMENDED = "amended"
    REFERRED = "referred"
    APPROVED = "approved"
    REFUSED = "refused"
    CHARGED = "charged"
    REFUNDED = "refunded"
    LOADED = "loaded"
    WEIGHED = "weighed"


@dataclass(frozen=True, slots=True, order=True)
class Event:
    """One thing the office did, on one day, to one thing."""

    sequence: int
    day: Day
    kind: EventKind
    subject: str
    detail: str = ""
    clerk: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", EventKind(self.kind))
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int):
            raise BadValueError("sequence", self.sequence, "want a whole number")
        if self.sequence < 1:
            raise BadValueError("sequence", self.sequence, "sequences start at 1")
        if not isinstance(self.day, dt.date) or isinstance(self.day, dt.datetime):
            raise BadValueError("day", self.day, "want a date")
        if not isinstance(self.subject, str) or not self.subject.strip():
            raise BadValueError("subject", self.subject, "want some text")
        object.__setattr__(self, "subject", " ".join(self.subject.split()))
        for name in ("detail", "clerk"):
            value = getattr(self, name)
            if not isinstance(value, str):
                raise BadValueError(name, value, "want text")
            object.__setattr__(self, name, " ".join(value.split()))
        if len(self.detail) > MAX_DETAIL:
            raise BadValueError("detail", self.detail, f"over {MAX_DETAIL} characters")

    def __str__(self) -> str:
        who = f" by {self.clerk}" if self.clerk else ""
        tail = f": {self.detail}" if self.detail else ""
        return f"{format_day(self.day)} {self.subject} {self.kind}{who}{tail}"


class HistoryStore:
    """Everything the office has done, append only."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Hold the open connection this store writes to."""
        self.connection = connection

    def write(
        self,
        day: Day,
        kind: EventKind,
        subject: str,
        detail: str = "",
        clerk: str = "",
    ) -> Event:
        """Record one thing that happened."""
        made = Event(
            sequence=self.next_sequence(),
            day=day,
            kind=EventKind(kind),
            subject=subject,
            detail=detail,
            clerk=clerk,
        )
        self.connection.execute(
            "INSERT INTO journal (sequence, day, kind, subject, detail, clerk)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                made.sequence,
                format_day(made.day),
                str(made.kind),
                made.subject,
                made.detail,
                made.clerk,
            ),
        )
        return made

    def next_sequence(self) -> int:
        """The number the next entry will take."""
        highest = scalar(self.connection, "SELECT max(sequence) FROM journal")
        return 1 if highest is None else int(highest) + 1

    def _from_row(self, row: sqlite3.Row) -> Event:
        return Event(
            sequence=int(row["sequence"]),
            day=parse_day(row["day"]),
            kind=EventKind(row["kind"]),
            subject=row["subject"],
            detail=row["detail"],
            clerk=row["clerk"],
        )

    def all(self) -> list[Event]:
        """Every entry, oldest first."""
        return [
            self._from_row(row)
            for row in rows(self.connection, "SELECT * FROM journal ORDER BY sequence")
        ]

    def about(self, subject: str) -> list[Event]:
        """Every entry about one thing, oldest first."""
        return [
            self._from_row(row)
            for row in rows(
                self.connection,
                "SELECT * FROM journal WHERE subject = ? ORDER BY sequence",
                (" ".join(str(subject).split()),),
            )
        ]

    def within(self, span: DaySpan) -> list[Event]:
        """Every entry inside a span of days, oldest first."""
        return [
            self._from_row(row)
            for row in rows(
                self.connection,
                "SELECT * FROM journal WHERE day >= ? AND day <= ? ORDER BY sequence",
                (format_day(span.first), format_day(span.last)),
            )
        ]

    def of_kind(self, kind: EventKind) -> list[Event]:
        """Every entry of one kind, oldest first."""
        return [
            self._from_row(row)
            for row in rows(
                self.connection,
                "SELECT * FROM journal WHERE kind = ? ORDER BY sequence",
                (str(EventKind(kind)),),
            )
        ]

    def count(self) -> int:
        """How many entries are on file."""
        return int(scalar(self.connection, "SELECT count(*) FROM journal") or 0)

    def __len__(self) -> int:
        return self.count()
