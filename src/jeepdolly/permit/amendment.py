"""Changing something on a permit that has already been issued.

The office does this constantly and used to do it by voiding the permit and
writing a new one, which is tidy in the file and wrong everywhere else. The
carrier has the old number painted on the escort boards, the bridge people have
it in their notification, and a void that lands the morning of the move reads to
enforcement as a permit that was pulled.

So an amendment leaves the number alone and records what moved. The record holds
both applications, the one that was priced and the one that now applies, and
works out for itself which of them differ. It is not given the list of changes,
because a clerk typing the list and the clerk typing the new figures were the
same person having a bad morning at least twice.

Not everything is amendable. The carrier and the sort of permit are the two
things that make it a different permit rather than the same one changed, and
asking for either comes back as a refusal that says to file again.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from jeepdolly.errors import BadValueError, NotAllowedError
from jeepdolly.ids.reference import Serial, serial
from jeepdolly.permit.application import Application
from jeepdolly.permit.permit import MAX_EXTENSION_DAYS, Permit, State
from jeepdolly.units.clock import Day, only_a_day

__all__ = [
    "CLERICAL",
    "MATERIAL",
    "MAX_NOTE",
    "Amendment",
    "Change",
    "amend",
    "amendable",
    "differences",
]

#: Longer than any note a clerk has needed for why something moved.
MAX_NOTE = 200


class Change(StrEnum):
    """One thing about a permit that an amendment moved."""

    DATES = "dates"
    ROUTE = "route"
    LOAD = "load"
    RIG = "rig"


#: These change what the limits and the route search would answer, so the whole
#: assessment has to be run again and the permit repriced.
MATERIAL = frozenset({Change.ROUTE, Change.LOAD, Change.RIG})

#: These do not. The permit is reissued on the same findings at the same fee.
CLERICAL = frozenset({Change.DATES})


def differences(was: Application, now: Application) -> tuple[Change, ...]:
    """What actually differs between two applications, in a fixed order.

    Carrier and kind are deliberately not in the answer. They are checked by
    ``amend`` and refused there, because a change of either is a different
    permit and calling it a difference invites somebody to allow it.
    """
    for name, value in (("was", was), ("now", now)):
        if not isinstance(value, Application):
            raise BadValueError(name, value, "want an application")
    found: list[Change] = []
    if was.span != now.span:
        found.append(Change.DATES)
    if (was.origin, was.destination) != (now.origin, now.destination):
        found.append(Change.ROUTE)
    if was.load != now.load:
        found.append(Change.LOAD)
    if was.rig != now.rig:
        found.append(Change.RIG)
    return tuple(found)


@dataclass(frozen=True, slots=True)
class Amendment:
    """One issued permit, what it said, and what it says now."""

    number: Serial
    was: Application
    now: Application
    filed_on: Day
    note: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "number", serial(str(self.number)))
        only_a_day(self.filed_on, "filed on")
        if not isinstance(self.note, str):
            raise BadValueError("note", self.note, "want text")
        tidy = " ".join(self.note.split())
        if len(tidy) > MAX_NOTE:
            raise BadValueError("note", self.note, f"over {MAX_NOTE} characters")
        object.__setattr__(self, "note", tidy)
        if not differences(self.was, self.now):
            raise BadValueError("amendment", str(self.number), "changes nothing")

    @property
    def changes(self) -> tuple[Change, ...]:
        """Everything this amendment moved."""
        return differences(self.was, self.now)

    @property
    def material(self) -> bool:
        """Does this amendment force the assessment to be run again."""
        return bool(MATERIAL & set(self.changes))

    @property
    def clerical(self) -> bool:
        """Is this one the office can reissue without repricing."""
        return not self.material

    @property
    def days_added(self) -> int:
        """How many days longer the permit runs, which may be negative."""
        return self.now.span.days - self.was.span.days

    def __str__(self) -> str:
        moved = ", ".join(str(one) for one in self.changes)
        return f"{self.number} amended: {moved}"


def amendable(permit: Permit, on: Day) -> bool:
    """May this permit be amended as at a day.

    A permit that has already run out may not. There is nothing left to amend,
    and the office would rather write a fresh one than have a permit whose dates
    were changed after the load was already down the road.
    """
    only_a_day(on, "day")
    return permit.state is State.ACTIVE and not permit.expired_on(on)


def amend(permit: Permit, now: Application, on: Day, note: str = "") -> Amendment:
    """Build the amendment that moves an issued permit onto a new application."""
    if not isinstance(permit, Permit):
        raise BadValueError("permit", permit, "want a permit")
    if not isinstance(now, Application):
        raise BadValueError("application", now, "want an application")
    if not amendable(permit, on):
        state = "expired" if permit.state is State.ACTIVE else str(permit.state)
        raise NotAllowedError("permit", state, "amend")
    was = permit.application
    if was.carrier != now.carrier:
        raise NotAllowedError("permit", "a different carrier", "amend onto")
    if was.kind is not now.kind:
        raise NotAllowedError("permit", f"a {now.kind} permit", "amend onto")
    if on < permit.issued_on:
        raise BadValueError("filed on", on, "before the permit was issued")
    stretched = (now.span.last - permit.span.last).days
    if stretched > MAX_EXTENSION_DAYS:
        raise NotAllowedError(
            "permit",
            f"{stretched} more days",
            f"stretch by more than {MAX_EXTENSION_DAYS} without a fresh application",
        )
    return Amendment(number=permit.number, was=was, now=now, filed_on=on, note=note)
