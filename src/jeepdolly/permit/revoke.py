"""Pulling a permit, and what the carrier gets back when it happens.

The office had one word for this and it was doing too much work. A permit pulled
because the office routed it over a bridge that was closed, a permit pulled
because the carrier rang up and cancelled, and a permit pulled because the load
on the trailer was nothing like the load on the application are three different
events with three different answers about the money, and they were all a void
with a sentence of free text next to them.

So the reason is a code now, and the refund falls out of it. Three of the codes
give everything back, two give nothing back, and the rest depend on whether the
load had already gone. That last part is the bit worth reading twice: the same
cause refunds differently depending on the day it is invoked, because once the
rig is on the road the office has done all of the work it was paid for and the
escorts have already been booked.

Two of the codes also count against the carrier. A carrier caught hauling a load
it did not declare cannot be issued anything for a while, and that block is read
by the issuing decision rather than enforced here.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from enum import StrEnum

from jeepdolly.billing.tariff import SCHEDULE, Tariff
from jeepdolly.errors import BadValueError, NotAllowedError
from jeepdolly.ids.reference import Serial, serial
from jeepdolly.permit.permit import Permit, State
from jeepdolly.units.clock import Day, format_day, only_a_day
from jeepdolly.units.money import Money, cents

__all__ = [
    "AT_FAULT",
    "BLOCK_DAYS",
    "FULL_REFUND",
    "MAX_DETAIL",
    "NO_REFUND",
    "Cause",
    "Revocation",
    "blocked_on",
    "refund_due",
    "revoke",
]

#: How long an at fault revocation stops a carrier being issued anything.
BLOCK_DAYS = 90

MAX_DETAIL = 200


class Cause(StrEnum):
    """Why a permit was pulled."""

    CANCELLED = "carrier cancelled"
    OFFICE_ERROR = "office error"
    ROUTE_CLOSED = "route closed"
    RIG_FAILED = "rig failed inspection"
    FALSE_LOAD = "load was not as declared"
    UNSAFE_MOVE = "move was unsafe"


#: The office's own fault, so the carrier gets all of it back whatever the day.
FULL_REFUND = frozenset({Cause.OFFICE_ERROR, Cause.ROUTE_CLOSED})

#: The carrier's fault in a way that costs the office money, so nothing back.
NO_REFUND = frozenset({Cause.FALSE_LOAD, Cause.UNSAFE_MOVE})

#: These go on the carrier's record and stop it being issued anything for a while.
AT_FAULT = frozenset({Cause.FALSE_LOAD, Cause.UNSAFE_MOVE})


def _day(on: Day) -> Day:
    """Refuse anything that is not a plain date."""
    only_a_day(on, "day")
    return on


def refund_due(permit: Permit, cause: Cause, on: Day, tariff: Tariff = SCHEDULE) -> Money:
    """What the carrier gets back if this permit is pulled for this reason.

    A cancellation before the first day keeps the writing fee and gives back the
    rest. A cancellation once the permit is good keeps all of it, because the
    assessment, the route and the escort booking have all already happened and
    none of them can be sold to anybody else.
    """
    if not isinstance(permit, Permit):
        raise BadValueError("permit", permit, "want a permit")
    wanted = Cause(cause)
    only_a_day(on)
    if wanted in NO_REFUND:
        return cents(0)
    if wanted in FULL_REFUND:
        return permit.fee
    if on >= permit.span.first:
        return cents(0)
    return cents(max(int(permit.fee) - int(tariff.trip_base), 0))


@dataclass(frozen=True, slots=True, order=True)
class Revocation:
    """One permit pulled, why, and what went back."""

    number: Serial
    cause: Cause
    on: Day
    refunded: Money
    detail: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "number", serial(str(self.number)))
        object.__setattr__(self, "cause", Cause(self.cause))
        object.__setattr__(self, "on", only_a_day(self.on))
        object.__setattr__(self, "refunded", cents(int(self.refunded)))
        if int(self.refunded) < 0:
            raise BadValueError("refunded", int(self.refunded), "negative")
        if not isinstance(self.detail, str):
            raise BadValueError("detail", self.detail, "want text")
        tidy = " ".join(self.detail.split())
        if len(tidy) > MAX_DETAIL:
            raise BadValueError("detail", self.detail, f"over {MAX_DETAIL} characters")
        object.__setattr__(self, "detail", tidy)
        if self.at_fault and not tidy:
            raise BadValueError(
                "detail", self.detail, "an at fault revocation says what happened"
            )

    @property
    def at_fault(self) -> bool:
        """Does this one count against the carrier."""
        return self.cause in AT_FAULT

    @property
    def blocks_until(self) -> Day | None:
        """The last day this revocation stops the carrier being issued anything."""
        if not self.at_fault:
            return None
        return self.on + dt.timedelta(days=BLOCK_DAYS)

    def blocks_on(self, day: Day) -> bool:
        """Would this revocation stop an issue on a given day."""
        until = self.blocks_until
        return until is not None and self.on <= only_a_day(day) <= until

    def __str__(self) -> str:
        return f"{self.number} pulled {format_day(self.on)}: {self.cause}"


def revoke(
    permit: Permit,
    cause: Cause,
    on: Day,
    detail: str = "",
    tariff: Tariff = SCHEDULE,
) -> tuple[Permit, Revocation]:
    """Pull a permit and work out the refund in one step."""
    if not isinstance(permit, Permit):
        raise BadValueError("permit", permit, "want a permit")
    wanted = Cause(cause)
    if permit.state is not State.ACTIVE:
        raise NotAllowedError("permit", str(permit.state), "revoke")
    back = refund_due(permit, wanted, on, tariff)
    pulled = permit.voided(str(wanted), on)
    made = Revocation(number=permit.number, cause=wanted, on=on, refunded=back, detail=detail)
    return pulled, made


def blocked_on(revocations: list[Revocation], day: Day) -> Revocation | None:
    """The revocation stopping this carrier being issued anything, if any.

    The one running longest wins, so a carrier with two at fault revocations is
    blocked until the later of them rather than the earlier.
    """
    holding = [one for one in revocations if one.blocks_on(day)]
    if not holding:
        return None
    return max(holding, key=lambda one: one.on)
