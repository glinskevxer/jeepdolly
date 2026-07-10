"""The permit itself, and the four things that can happen to it.

A permit is issued once and then only ever changes state. It is not edited. An
amendment produces a new permit and marks the old one superseded, so the pair
stays on file and the driver's copy can always be matched to a record.

The four states are not a workflow. ``ACTIVE`` and ``VOID`` are recorded, and
``EXPIRED`` is a function of the calendar rather than something the office does,
so it is derived rather than stored. ``SUPERSEDED`` is recorded and points at
the permit that replaced it.

Voiding is the only state change a clerk makes by hand, and it needs a reason.
An unreasoned void is how a permit quietly disappears from the revenue report.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from enum import StrEnum

from jeepdolly.errors import BadValueError, NotAllowedError
from jeepdolly.ids.reference import Serial, serial
from jeepdolly.permit.application import Application
from jeepdolly.permit.decision import Decision, Outcome
from jeepdolly.units.clock import Day, DaySpan
from jeepdolly.units.money import Money

__all__ = ["MAX_EXTENSION_DAYS", "Permit", "State", "issue"]

#: A permit may be extended by this many days without a fresh application.
MAX_EXTENSION_DAYS = 5


class State(StrEnum):
    """What the office has recorded about a permit."""

    ACTIVE = "active"
    VOID = "void"
    SUPERSEDED = "superseded"


@dataclass(frozen=True, slots=True)
class Permit:
    """One issued permit."""

    number: Serial
    decision: Decision
    issued_on: Day
    span: DaySpan
    state: State = State.ACTIVE
    reason: str = ""
    replaced_by: Serial | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "number", serial(str(self.number)))
        object.__setattr__(self, "state", State(self.state))
        if not isinstance(self.decision, Decision):
            raise BadValueError("decision", self.decision, "want a decision")
        if self.decision.outcome is not Outcome.ISSUE:
            raise BadValueError("decision", self.decision.outcome, "was not an issue")
        if not isinstance(self.span, DaySpan):
            raise BadValueError("span", self.span, "want a day span")
        if not isinstance(self.issued_on, dt.date) or isinstance(self.issued_on, dt.datetime):
            raise BadValueError("issued on", self.issued_on, "want a date")
        if self.span.first < self.decision.application.span.first:
            raise BadValueError("span", str(self.span), "starts before what was applied for")
        self._check_state()

    def _check_state(self) -> None:
        """A reason belongs to a void and a successor to a supersession."""
        if not isinstance(self.reason, str):
            raise BadValueError("reason", self.reason, "want text")
        if self.state is State.VOID and not self.reason.strip():
            raise BadValueError("reason", self.reason, "a void needs a reason")
        if self.state is not State.VOID and self.reason.strip():
            raise BadValueError("reason", self.reason, "only a void carries one")
        if self.state is State.SUPERSEDED and self.replaced_by is None:
            raise BadValueError("replaced by", None, "a superseded permit names its successor")
        if self.state is not State.SUPERSEDED and self.replaced_by is not None:
            raise BadValueError("replaced by", self.replaced_by, "nothing replaced this")
        if self.replaced_by is not None:
            object.__setattr__(self, "replaced_by", serial(str(self.replaced_by)))

    @property
    def application(self) -> Application:
        """What was asked for."""
        return self.decision.application

    @property
    def carrier(self) -> str:
        """Whose permit this is."""
        return str(self.application.carrier)

    @property
    def fee(self) -> Money:
        """What was charged for it."""
        assert self.decision.invoice is not None
        return self.decision.invoice.total

    @property
    def live(self) -> bool:
        """Is the permit still one the office stands behind."""
        return self.state is State.ACTIVE

    def expired_on(self, day: Day) -> bool:
        """Has the permit run out by this day."""
        return day > self.span.last

    def good_on(self, day: Day) -> bool:
        """May the load move under this permit on this day."""
        return self.live and self.span.covers(day)

    def voided(self, reason: str, on: Day) -> Permit:
        """The same permit, marked void.

        ``on`` is only checked, not stored. The office records the void in the
        permit history rather than on the permit, because a permit voided twice
        by two clerks is a thing that has happened and the history has both.
        """
        if self.state is State.VOID:
            raise NotAllowedError("permit", "already void", "void")
        if self.state is State.SUPERSEDED:
            raise NotAllowedError("permit", "superseded", "void")
        if not reason.strip():
            raise BadValueError("reason", reason, "a void needs a reason")
        if on < self.issued_on:
            raise BadValueError("void date", on, "before the permit was issued")
        return Permit(
            number=self.number,
            decision=self.decision,
            issued_on=self.issued_on,
            span=self.span,
            state=State.VOID,
            reason=" ".join(reason.split()),
        )

    def superseded_by(self, number: Serial) -> Permit:
        """The same permit, marked replaced by another."""
        if self.state is State.VOID:
            raise NotAllowedError("permit", "void", "supersede")
        if self.state is State.SUPERSEDED:
            raise NotAllowedError("permit", "already superseded", "supersede")
        if serial(str(number)) == self.number:
            raise BadValueError("replaced by", number, "a permit cannot replace itself")
        return Permit(
            number=self.number,
            decision=self.decision,
            issued_on=self.issued_on,
            span=self.span,
            state=State.SUPERSEDED,
            replaced_by=serial(str(number)),
        )

    def respanned(self, span: DaySpan) -> Permit:
        """The same permit over different days, keeping its number and its fee.

        The number is the point. The carrier has it on the escort boards and the
        bridge people have it in their notification, so a change of dates that
        produces a new number costs more phone calls than it saves.
        """
        if not self.live:
            raise NotAllowedError("permit", str(self.state), "move the dates of")
        if not isinstance(span, DaySpan):
            raise BadValueError("span", span, "want a day span")
        return Permit(
            number=self.number,
            decision=self.decision,
            issued_on=self.issued_on,
            span=span,
            state=self.state,
        )

    def extended(self, last: Day) -> Permit:
        """The same permit running a few days longer.

        Capped, because an extension is meant to cover a load that did not get
        away on the Friday. A carrier wanting another fortnight is applying for
        a permit, and the cap is what keeps the two apart.
        """
        if not self.live:
            raise NotAllowedError("permit", str(self.state), "extend")
        if last <= self.span.last:
            raise BadValueError("extension", last, "not past the current last day")
        added = (last - self.span.last).days
        if added > MAX_EXTENSION_DAYS:
            raise BadValueError("extension", added, f"more than {MAX_EXTENSION_DAYS} days")
        return self.respanned(DaySpan(self.span.first, last))

    def __str__(self) -> str:
        return f"{self.number} {self.carrier} {self.state} {self.span}"


def issue(number: Serial, decision: Decision, issued_on: Day) -> Permit:
    """Write a permit from a decision that came out as an issue."""
    if decision.outcome is not Outcome.ISSUE:
        raise NotAllowedError("application", str(decision.outcome), "issue a permit for")
    return Permit(
        number=number,
        decision=decision,
        issued_on=issued_on,
        span=decision.application.span,
    )
