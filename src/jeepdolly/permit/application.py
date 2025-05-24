"""What the carrier asks for.

An application is a request and nothing more. It has not been checked against
the rig, the route or the calendar, and it carries no findings and no fee. That
separation is deliberate: the same application can be decided twice, on two
different days, against two different sets of frost law orders, and the office
needs to be able to show that the request did not change.

The three kinds are not variations on one thing. A single trip permit is one run
between two named junctions. An annual permit is a year of runs anywhere on a
class of road, so it carries no route at all. A superload is a single trip that
goes to engineering review before anybody prices it.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from enum import StrEnum

from jeepdolly.errors import BadValueError
from jeepdolly.ids.reference import Code, Serial, code, serial
from jeepdolly.rig.load import Load
from jeepdolly.units.clock import Day, DaySpan

__all__ = ["ANNUAL_DAYS", "MAX_LEAD_DAYS", "MAX_TRIP_DAYS", "Application", "Kind"]

#: A single trip permit is good for this many days at the outside.
MAX_TRIP_DAYS = 10

#: An annual permit runs a full year, and only a full year.
ANNUAL_DAYS = 365

#: The office will not take an application more than this far ahead.
MAX_LEAD_DAYS = 90


class Kind(StrEnum):
    """What sort of permit is being asked for."""

    TRIP = "trip"
    ANNUAL = "annual"
    SUPERLOAD = "superload"


@dataclass(frozen=True, slots=True)
class Application:
    """One request, as filed at the counter."""

    carrier: Code
    rig: Serial
    load: Load
    span: DaySpan
    filed_on: Day
    kind: Kind = Kind.TRIP
    origin: Code | None = None
    destination: Code | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "carrier", code(str(self.carrier)))
        object.__setattr__(self, "rig", serial(str(self.rig)))
        object.__setattr__(self, "kind", Kind(self.kind))
        if not isinstance(self.load, Load):
            raise BadValueError("load", self.load, "want a load")
        if not isinstance(self.span, DaySpan):
            raise BadValueError("span", self.span, "want a day span")
        if not isinstance(self.filed_on, dt.date) or isinstance(self.filed_on, dt.datetime):
            raise BadValueError("filed on", self.filed_on, "want a date")
        if self.span.first < self.filed_on:
            raise BadValueError("span", str(self.span), "starts before it was filed")
        if (self.span.first - self.filed_on).days > MAX_LEAD_DAYS:
            raise BadValueError("span", str(self.span), f"more than {MAX_LEAD_DAYS} days ahead")
        self._check_kind()

    def _check_kind(self) -> None:
        """The three kinds want different things, and want them here."""
        if self.kind is Kind.ANNUAL:
            if self.span.days != ANNUAL_DAYS:
                raise BadValueError(
                    "span", self.span.days, f"an annual runs {ANNUAL_DAYS} days"
                )
            if self.origin is not None or self.destination is not None:
                raise BadValueError("route", self.origin, "an annual permit names no route")
            return
        if self.span.days > MAX_TRIP_DAYS:
            raise BadValueError("span", self.span.days, f"a trip runs at most {MAX_TRIP_DAYS}")
        if self.origin is None or self.destination is None:
            raise BadValueError("route", None, "a trip permit names both ends")
        object.__setattr__(self, "origin", code(str(self.origin)))
        object.__setattr__(self, "destination", code(str(self.destination)))
        if self.origin == self.destination:
            raise BadValueError("route", self.origin, "starts and ends at the same junction")

    @property
    def routed(self) -> bool:
        """Does this application name a route."""
        return self.origin is not None

    @property
    def days(self) -> int:
        """How many days the permit is being asked to cover."""
        return self.span.days

    @property
    def reviewed(self) -> bool:
        """Does this application go to engineering before it is priced."""
        return self.kind is Kind.SUPERLOAD

    def covers(self, day: Day) -> bool:
        """Would the permit be good on this day."""
        return self.span.covers(day)

    def __str__(self) -> str:
        where = f"{self.origin} to {self.destination}" if self.routed else "no fixed route"
        return f"{self.carrier} {self.rig} {self.kind}, {where}, {self.span}"
