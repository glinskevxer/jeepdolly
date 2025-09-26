"""Engineering review: what happens to an application a clerk cannot decide.

A superload, or anything past the review dimensions, does not get refused at the
counter and it does not get priced there either. It goes on a list an engineer
works through, and the engineer either approves it with conditions or refuses it
with a reason.

The conditions matter more than the approval. An engineer almost never says yes
without also saying "at walking pace over the Clark Fork bridge" or "with the
county notified twenty four hours ahead", and those conditions have to end up
printed on the permit rather than in an email.

A review is closed once. Approving a refused review, or refusing an approved one,
is not an edit the office allows: the engineer opens a fresh review instead, and
the pair stays on file.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from enum import StrEnum

from jeepdolly.errors import BadValueError, NotAllowedError
from jeepdolly.ids.reference import Serial, serial
from jeepdolly.units.clock import Day

__all__ = ["CLOSED", "MAX_CONDITIONS", "MAX_ENGINEER", "Review", "ReviewState", "open_review"]

#: More conditions than this on one permit is a sign the answer was really no.
MAX_CONDITIONS = 12

MAX_ENGINEER = 60


class ReviewState(StrEnum):
    """Where an engineering review has got to."""

    OPEN = "open"
    APPROVED = "approved"
    REFUSED = "refused"
    WITHDRAWN = "withdrawn"


#: The states a review cannot be moved out of.
CLOSED = frozenset({ReviewState.APPROVED, ReviewState.REFUSED, ReviewState.WITHDRAWN})


@dataclass(frozen=True, slots=True)
class Review:
    """One application in front of an engineer."""

    reference: Serial
    application_key: int
    opened_on: Day
    state: ReviewState = ReviewState.OPEN
    engineer: str = ""
    decided_on: Day | None = None
    conditions: tuple[str, ...] = ()
    note: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "reference", serial(str(self.reference)))
        object.__setattr__(self, "state", ReviewState(self.state))
        self._check_key()
        self._tidy_text()
        self._check_state()

    def _check_key(self) -> None:
        """The application key is a whole number and the open day is a date."""
        key = self.application_key
        if isinstance(key, bool) or not isinstance(key, int):
            raise BadValueError("application", key, "want a whole number")
        if key < 1:
            raise BadValueError("application", key, "keys start at 1")
        if not isinstance(self.opened_on, dt.date) or isinstance(self.opened_on, dt.datetime):
            raise BadValueError("opened on", self.opened_on, "want a date")

    def _tidy_text(self) -> None:
        """Collapse the free text fields and check what is in them."""
        object.__setattr__(
            self, "conditions", tuple(" ".join(str(c).split()) for c in self.conditions)
        )
        if len(self.conditions) > MAX_CONDITIONS:
            raise BadValueError("conditions", len(self.conditions), f"over {MAX_CONDITIONS}")
        if any(not c for c in self.conditions):
            raise BadValueError("conditions", self.conditions, "one of them is empty")
        for name in ("engineer", "note"):
            value = getattr(self, name)
            if not isinstance(value, str):
                raise BadValueError(name, value, "want text")
            object.__setattr__(self, name, " ".join(value.split()))
        if len(self.engineer) > MAX_ENGINEER:
            raise BadValueError("engineer", self.engineer, f"over {MAX_ENGINEER} characters")

    def _check_state(self) -> None:
        """An open review has no decision and a closed one has all of it."""
        if self.state is ReviewState.OPEN:
            if self.decided_on is not None or self.engineer:
                raise BadValueError("review", self.state, "an open review has no decision")
            return
        self._check_engineer()
        self._check_decided_day()
        if self.state is ReviewState.REFUSED and not self.note:
            raise BadValueError("note", "", "a refusal says why")
        if self.state is not ReviewState.APPROVED and self.conditions:
            raise BadValueError("conditions", self.conditions, "only an approval carries them")

    def _check_engineer(self) -> None:
        """A decision names an engineer and a withdrawal does not."""
        if self.state is ReviewState.WITHDRAWN:
            if self.engineer:
                raise BadValueError("engineer", self.engineer, "a withdrawal has no engineer")
        elif not self.engineer:
            raise BadValueError("engineer", "", "a decided review names its engineer")

    def _check_decided_day(self) -> None:
        """A closed review has a decision day, and it is not before it opened."""
        if self.decided_on is None:
            raise BadValueError("decided on", None, "a closed review has a day")
        if not isinstance(self.decided_on, dt.date) or isinstance(self.decided_on, dt.datetime):
            raise BadValueError("decided on", self.decided_on, "want a date")
        if self.decided_on < self.opened_on:
            raise BadValueError("decided on", self.decided_on, "before it was opened")

    @property
    def open(self) -> bool:
        """Is this still on the engineer's list."""
        return self.state is ReviewState.OPEN

    @property
    def approved(self) -> bool:
        """Did the engineer say yes."""
        return self.state is ReviewState.APPROVED

    @property
    def days_open(self) -> int:
        """How many days it took, or has taken so far as at its decision."""
        if self.decided_on is None:
            return 0
        return (self.decided_on - self.opened_on).days

    def _refuse_second_decision(self, wanted: str) -> None:
        """Raise if the review has already been closed."""
        if self.state in CLOSED:
            raise NotAllowedError("review", str(self.state), wanted)

    def approved_by(self, engineer: str, on: Day, conditions: tuple[str, ...] = ()) -> Review:
        """The same review, approved with conditions."""
        self._refuse_second_decision("approve")
        return Review(
            reference=self.reference,
            application_key=self.application_key,
            opened_on=self.opened_on,
            state=ReviewState.APPROVED,
            engineer=engineer,
            decided_on=on,
            conditions=conditions,
        )

    def refused_by(self, engineer: str, on: Day, note: str) -> Review:
        """The same review, refused with a reason."""
        self._refuse_second_decision("refuse")
        return Review(
            reference=self.reference,
            application_key=self.application_key,
            opened_on=self.opened_on,
            state=ReviewState.REFUSED,
            engineer=engineer,
            decided_on=on,
            note=note,
        )

    def withdrawn(self, on: Day, note: str = "") -> Review:
        """The same review, taken off the list by the carrier."""
        self._refuse_second_decision("withdraw")
        return Review(
            reference=self.reference,
            application_key=self.application_key,
            opened_on=self.opened_on,
            state=ReviewState.WITHDRAWN,
            decided_on=on,
            note=note or "withdrawn by the carrier",
        )

    def __str__(self) -> str:
        tail = f" by {self.engineer}" if self.engineer else ""
        return f"{self.reference} application {self.application_key} {self.state}{tail}"


def open_review(reference: Serial, application_key: int, on: Day) -> Review:
    """Put an application on the engineer's list."""
    return Review(reference=reference, application_key=application_key, opened_on=on)
