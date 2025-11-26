"""Reading and writing engineering reviews.

The conditions go in their own table with a position, because they are printed
in the order the engineer wrote them and joining them into one field with a
separator is how a condition containing that separator turns into two.

A review is written once and then only its state changes, the same shape as a
permit. ``save_state`` rewrites the header and replaces the conditions, which is
the one place in this package a child table is deleted and rewritten rather than
appended to. That is safe because an approval sets its conditions once and the
alternative is a position counter that has to survive a withdrawal.
"""

from __future__ import annotations

import sqlite3

from jeepdolly.errors import ConflictError
from jeepdolly.ids.reference import REVIEW, Serial, serial
from jeepdolly.permit.review import Review, ReviewState
from jeepdolly.store.applications import ApplicationStore
from jeepdolly.store.counter import next_serial
from jeepdolly.store.sqlite import maybe_one, one, rows, scalar
from jeepdolly.units.clock import Day, format_day, parse_day

__all__ = ["ReviewStore"]


class ReviewStore:
    """Every application that has been in front of an engineer."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Hold the open connection and the application store beside it."""
        self.connection = connection
        self.applications = ApplicationStore(connection)

    def next_reference(self) -> Serial:
        """The reference the next review will be opened under."""
        return next_serial(self.connection, REVIEW, "review", "reference")

    def add(self, review: Review) -> Review:
        """Open a review against an application that is on file."""
        if self.find(str(review.reference)) is not None:
            raise ConflictError("review", review.reference)
        self.applications.get(review.application_key)
        self.connection.execute(
            "INSERT INTO review (reference, application_id, opened_on, state, engineer,"
            " decided_on, note) VALUES (?, ?, ?, ?, ?, ?, ?)",
            self._header(review),
        )
        self._write_conditions(review)
        return review

    def _header(self, review: Review) -> tuple[object, ...]:
        """The review's own row, without its conditions."""
        return (
            str(review.reference),
            review.application_key,
            format_day(review.opened_on),
            str(review.state),
            review.engineer,
            None if review.decided_on is None else format_day(review.decided_on),
            review.note,
        )

    def _write_conditions(self, review: Review) -> None:
        for position, text in enumerate(review.conditions):
            self.connection.execute(
                "INSERT INTO review_condition (review_reference, position, text)"
                " VALUES (?, ?, ?)",
                (str(review.reference), position, text),
            )

    def _conditions(self, reference: Serial) -> tuple[str, ...]:
        return tuple(
            row["text"]
            for row in rows(
                self.connection,
                "SELECT text FROM review_condition WHERE review_reference = ?"
                " ORDER BY position",
                (str(reference),),
            )
        )

    def _from_row(self, row: sqlite3.Row) -> Review:
        reference = serial(row["reference"])
        decided = row["decided_on"]
        return Review(
            reference=reference,
            application_key=int(row["application_id"]),
            opened_on=parse_day(row["opened_on"]),
            state=ReviewState(row["state"]),
            engineer=row["engineer"],
            decided_on=None if decided is None else parse_day(decided),
            conditions=self._conditions(reference),
            note=row["note"],
        )

    def get(self, key: str) -> Review:
        """One review by reference, raising if it is not there."""
        row = one(
            self.connection,
            "SELECT * FROM review WHERE reference = ?",
            (str(serial(str(key))),),
            kind="review",
        )
        return self._from_row(row)

    def find(self, key: str) -> Review | None:
        """One review by reference, or ``None``."""
        row = maybe_one(
            self.connection,
            "SELECT * FROM review WHERE reference = ?",
            (str(serial(str(key))),),
        )
        return None if row is None else self._from_row(row)

    def save_state(self, review: Review) -> Review:
        """Write back a decision, replacing the conditions."""
        self.get(str(review.reference))
        self.connection.execute(
            "UPDATE review SET state = ?, engineer = ?, decided_on = ?, note = ?"
            " WHERE reference = ?",
            (
                str(review.state),
                review.engineer,
                None if review.decided_on is None else format_day(review.decided_on),
                review.note,
                str(review.reference),
            ),
        )
        self.connection.execute(
            "DELETE FROM review_condition WHERE review_reference = ?", (str(review.reference),)
        )
        self._write_conditions(review)
        return review

    def all(self) -> list[Review]:
        """Every review, in reference order."""
        return [
            self._from_row(row)
            for row in rows(self.connection, "SELECT * FROM review ORDER BY reference")
        ]

    def open_list(self) -> list[Review]:
        """Everything still on the engineer's list, oldest first."""
        return [
            self._from_row(row)
            for row in rows(
                self.connection,
                "SELECT * FROM review WHERE state = 'open' ORDER BY opened_on, reference",
            )
        ]

    def for_application(self, key: int) -> list[Review]:
        """Every review opened against one application, oldest first."""
        return [
            self._from_row(row)
            for row in rows(
                self.connection,
                "SELECT * FROM review WHERE application_id = ? ORDER BY reference",
                (int(key),),
            )
        ]

    def decided_between(self, first: Day, last: Day) -> list[Review]:
        """Every review decided inside a span of days."""
        return [
            self._from_row(row)
            for row in rows(
                self.connection,
                "SELECT * FROM review WHERE decided_on IS NOT NULL"
                " AND decided_on >= ? AND decided_on <= ? ORDER BY decided_on, reference",
                (format_day(first), format_day(last)),
            )
        ]

    def count(self) -> int:
        """How many reviews have been opened."""
        return int(scalar(self.connection, "SELECT count(*) FROM review") or 0)

    def __len__(self) -> int:
        return self.count()
