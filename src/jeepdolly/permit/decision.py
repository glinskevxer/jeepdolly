"""Turning findings into one of three answers.

Issue, refer, refuse. The interesting part is that a blocking finding does not
automatically mean refuse, because the office blocks for two different reasons
and they have opposite remedies.

A load too tall for a bridge on the route is a refusal. Nothing the office can
do about it and no fee fixes it; the carrier reroutes or dismantles.

A load wider than the review threshold is also blocking, in the sense that a
clerk cannot write it over the counter, but the remedy is an engineer looking at
it rather than the carrier going away. Those rules are named here, and a
blocking finding from one of them refers rather than refuses.

Getting this backwards is expensive in both directions. Refusing a referable
load sends business away; referring a refusable one puts an engineer on a job
with no possible answer.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from enum import StrEnum

from jeepdolly.billing.invoice import Invoice, price
from jeepdolly.billing.tariff import SCHEDULE, Tariff
from jeepdolly.errors import BadValueError
from jeepdolly.limits.dimension import LEGAL, SizeRule
from jeepdolly.limits.finding import Finding, Severity, excess_of
from jeepdolly.permit.application import Application
from jeepdolly.travel.escort import ORDINARY, Escort, EscortSchedule, escorts_for
from jeepdolly.units.clock import Day
from jeepdolly.units.distance import Miles
from jeepdolly.units.money import Money

__all__ = ["REFERABLE_RULES", "Decision", "Outcome", "decide", "outcome_for"]

#: A blocking finding from one of these goes to an engineer, not back to the
#: carrier. Everything else that blocks is a refusal.
REFERABLE_RULES = frozenset({"over-width", "over-height", "over-length"})


class Outcome(StrEnum):
    """What the office is going to do about the application."""

    ISSUE = "issue"
    REFER = "refer"
    REFUSE = "refuse"


@dataclass(frozen=True, slots=True)
class Decision:
    """One application, decided on one day, with the working kept."""

    application: Application
    outcome: Outcome
    findings: tuple[Finding, ...]
    escorts: tuple[Escort, ...]
    decided_on: Day
    invoice: Invoice | None = None
    distance: Miles | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "outcome", Outcome(self.outcome))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "escorts", tuple(self.escorts))
        if not isinstance(self.decided_on, dt.date) or isinstance(self.decided_on, dt.datetime):
            raise BadValueError("decided on", self.decided_on, "want a date")
        if self.decided_on < self.application.filed_on:
            raise BadValueError("decided on", self.decided_on, "before the application")
        if self.outcome is Outcome.ISSUE and self.invoice is None:
            raise BadValueError("invoice", None, "an issued permit is priced")
        if self.outcome is not Outcome.ISSUE and self.invoice is not None:
            raise BadValueError("invoice", "present", "only an issued permit is priced")

    @property
    def issued(self) -> bool:
        """Is a permit coming out of this."""
        return self.outcome is Outcome.ISSUE

    @property
    def blockers(self) -> tuple[Finding, ...]:
        """Everything that stopped a permit being written over the counter."""
        return tuple(f for f in self.findings if f.blocking)

    @property
    def reasons(self) -> tuple[str, ...]:
        """The blocking findings as one line each, for the refusal letter."""
        return tuple(str(f) for f in self.blockers)

    @property
    def fee(self) -> Money | None:
        """What the carrier owes, or nothing when no permit was written."""
        return None if self.invoice is None else self.invoice.total

    @property
    def escort_count(self) -> int:
        """How many vehicles the carrier has to put on the road."""
        return len(self.escorts)

    def __str__(self) -> str:
        tail = "" if self.invoice is None else f", {self.invoice}"
        return f"{self.application.carrier} {self.outcome}{tail}"


def outcome_for(application: Application, findings: tuple[Finding, ...]) -> Outcome:
    """Which of the three answers this application gets."""
    blockers = [f for f in findings if f.severity is Severity.REFUSE]
    if any(f.rule not in REFERABLE_RULES for f in blockers):
        return Outcome.REFUSE
    if blockers or application.reviewed:
        return Outcome.REFER
    return Outcome.ISSUE


def decide(
    application: Application,
    findings: tuple[Finding, ...],
    decided_on: Day,
    distance: Miles | None = None,
    tariff: Tariff = SCHEDULE,
    size_rule: SizeRule = LEGAL,
    escort_schedule: EscortSchedule = ORDINARY,
) -> Decision:
    """Decide one application against findings already worked out.

    Nothing is assessed here. The caller has walked the route or assessed the
    rig and hands the findings in, which is what lets the same decision be
    replayed later against the findings that were actually used.
    """
    outcome = outcome_for(application, findings)
    escorts = escorts_for(application.load, escort_schedule)
    invoice = None
    if outcome is Outcome.ISSUE:
        invoice = price(
            application=application,
            excess=excess_of(findings),
            distance=distance,
            escorts=len(escorts),
            tariff=tariff,
            rule=size_rule,
        )
    return Decision(
        application=application,
        outcome=outcome,
        findings=findings,
        escorts=escorts,
        decided_on=decided_on,
        invoice=invoice,
        distance=distance,
    )
