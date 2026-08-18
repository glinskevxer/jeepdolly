"""Building next year's application out of last year's permit.

An annual permit expires and the carrier wants the same thing again. Retyping the
rig, the load and the dates is where a renewal goes wrong: the office has issued
a renewal against a rig the carrier sold, more than once.

So a renewal is built from the permit rather than typed. Everything comes across
except the dates, and the dates are computed: the new span starts the day after
the old one ends and runs the same length.

It is still an application. It goes through the same assessment, against whatever
the limits and the frost laws are now, and it can be refused. That is the whole
point of renewing rather than extending: an extension keeps the old decision and
a renewal makes a new one.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from jeepdolly.errors import BadValueError, NotAllowedError
from jeepdolly.permit.application import ANNUAL_DAYS, Application, Kind
from jeepdolly.permit.permit import Permit, State
from jeepdolly.units.clock import Day, DaySpan, only_a_day

__all__ = ["RENEW_WINDOW", "Renewal", "renew", "renewable"]

#: How many days before it runs out a permit may be renewed.
RENEW_WINDOW = 45


@dataclass(frozen=True, slots=True)
class Renewal:
    """One permit and the application that would replace it."""

    from_permit: Permit
    application: Application

    @property
    def span(self) -> DaySpan:
        """The days the new permit would cover."""
        return self.application.span

    @property
    def gap(self) -> int:
        """How many days sit between the old permit and the new one."""
        return (self.span.first - self.from_permit.span.last).days - 1

    def __str__(self) -> str:
        return f"{self.from_permit.number} renewed as {self.span}"


def renewable(permit: Permit, on: Day) -> bool:
    """May this permit be renewed as at this day.

    A void or superseded permit may not. Nor may one whose renewal window has
    not opened yet, because a renewal issued four months early is a permit good
    for a rig that has had four months to change.
    """
    if permit.state is not State.ACTIVE:
        return False
    ahead = (permit.span.last - on).days
    return ahead <= RENEW_WINDOW


def renew(permit: Permit, on: Day, first: Day | None = None) -> Renewal:
    """Build the application that renews a permit.

    ``first`` overrides the start day, which the office uses when a carrier
    wants a gap. It may not be before the day after the old permit ends: two
    permits for the same rig on the same day is a thing the enforcement side
    would ask about.
    """
    only_a_day(on, "day")
    if permit.state is not State.ACTIVE:
        raise NotAllowedError("permit", str(permit.state), "renew")
    if not renewable(permit, on):
        ahead = (permit.span.last - on).days
        raise NotAllowedError(
            "permit",
            f"{ahead} days from running out",
            f"renew more than {RENEW_WINDOW} days early",
        )
    old = permit.application
    day_after = permit.span.last + dt.timedelta(days=1)
    start = day_after if first is None else first
    if start < day_after:
        raise BadValueError("first day", start, "overlaps the permit being renewed")
    length = ANNUAL_DAYS if old.kind is Kind.ANNUAL else old.span.days
    span = DaySpan(start, start + dt.timedelta(days=length - 1))
    made = Application(
        carrier=old.carrier,
        rig=old.rig,
        load=old.load,
        span=span,
        filed_on=on,
        kind=old.kind,
        origin=old.origin,
        destination=old.destination,
    )
    return Renewal(from_permit=permit, application=made)
