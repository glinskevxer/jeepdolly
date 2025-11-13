"""The counter: everything joined up, in the order a clerk does it.

Every layer below this one is deliberately ignorant of the others. The limits do
not know about the map, the map does not know about the calendar, and none of
them knows about the file. That keeps them testable and it means none of them is
useful on its own. The desk is where they are wired together, and it is the only
place a bug in the wiring can live.

The order is fixed and it matters:

1. look the carrier and the rig up, and refuse a retired carrier before anything
   is computed
2. find a route the rig can actually be driven on
3. walk it, with the seasonal orders in force on the first day of the span
4. decide
5. price and issue

Step three uses the *first day of the permit*, not today. A permit written in
February for a move in April is written under April's frost law orders, and the
office has been burned by the other reading.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from jeepdolly.almanac.embargo import EmbargoBook
from jeepdolly.almanac.season import SeasonBook
from jeepdolly.billing.account import EntryKind
from jeepdolly.billing.tariff import SCHEDULE, Tariff
from jeepdolly.errors import ConflictError, NotAllowedError, NotFoundError
from jeepdolly.limits.assess import assess
from jeepdolly.limits.dimension import LEGAL, SizeRule
from jeepdolly.limits.finding import Finding, Severity
from jeepdolly.permit.application import Application
from jeepdolly.permit.decision import Decision, Outcome, decide
from jeepdolly.permit.permit import Permit, issue
from jeepdolly.permit.review import Review, open_review
from jeepdolly.rig.config import Configuration
from jeepdolly.route.clear import RouteReport, walk
from jeepdolly.route.plan import Route
from jeepdolly.route.search import clearing, shortest
from jeepdolly.store.applications import FiledApplication
from jeepdolly.store.office import Office
from jeepdolly.travel.escort import ORDINARY as ORDINARY_ESCORTS
from jeepdolly.travel.escort import EscortSchedule
from jeepdolly.units.clock import Day
from jeepdolly.units.distance import Miles
from jeepdolly.units.mass import NO_WEIGHT

__all__ = ["Assessed", "Desk"]


@dataclass(frozen=True, slots=True)
class Assessed:
    """Everything worked out about one application before it is decided."""

    filed: FiledApplication
    config: Configuration
    findings: tuple[Finding, ...]
    route: Route | None
    report: RouteReport | None

    @property
    def application(self) -> Application:
        """What was asked for."""
        return self.filed.application

    @property
    def distance(self) -> Miles | None:
        """How far the route is, or nothing for an annual permit."""
        return None if self.route is None else self.route.distance

    @property
    def blocked(self) -> bool:
        """Is there anything no permit can fix."""
        return any(f.blocking for f in self.findings)


@dataclass(slots=True)
class Desk:
    """The counter, holding the file and the office's standing rules."""

    office: Office
    tariff: Tariff = SCHEDULE
    size_rule: SizeRule = LEGAL
    escorts: EscortSchedule = ORDINARY_ESCORTS
    seasons: SeasonBook = field(default_factory=lambda: SeasonBook(seasons=()))
    embargoes: EmbargoBook = field(default_factory=lambda: EmbargoBook(embargoes=()))

    @classmethod
    def at(cls, office: Office, **rules: object) -> Desk:
        """A desk with the almanac read off the file it is working on.

        Building the books here rather than in every caller is what stops a
        permit being decided against an empty almanac because somebody forgot to
        pass one in. That has happened, and the permit that came out was legal
        against the statute and not against the frost law in force that week.
        """
        made = cls(office=office, **rules)  # type: ignore[arg-type]
        made.seasons = office.almanac.season_book()
        made.embargoes = office.almanac.embargo_book()
        return made

    def file(self, application: Application) -> FiledApplication:
        """Take an application at the counter, refusing a retired carrier."""
        carrier = self.office.carriers.get(str(application.carrier))
        if not carrier.issuable:
            raise NotAllowedError("carrier", "retired", "file an application for")
        return self.office.applications.add(application)

    def assess(self, key: int) -> Assessed:
        """Work out everything about a filed application without deciding it."""
        filed = self.office.applications.get(key)
        application = filed.application
        rig = self.office.rigs.get(str(application.rig))
        config = rig.config
        if not application.routed:
            seen = assess(config, application.load, size_rule=self.size_rule)
            return Assessed(
                filed=filed, config=config, findings=seen.findings, route=None, report=None
            )
        network = self.office.roadway.network()
        assert application.origin is not None
        assert application.destination is not None
        route = clearing(
            network,
            str(application.origin),
            str(application.destination),
            config,
            application.load,
        )
        if route is None:
            route = shortest(network, str(application.origin), str(application.destination))
        if route is None:
            raise NotFoundError("route", f"{application.origin} to {application.destination}")
        report = walk(
            route,
            network,
            config,
            application.load,
            self.size_rule,
            seasons=self.seasons,
            on=application.span.first,
        )
        return Assessed(
            filed=filed,
            config=config,
            findings=report.findings,
            route=route,
            report=report,
        )

    def decide(self, key: int, on: Day) -> tuple[Assessed, Decision]:
        """Assess and decide one filed application."""
        seen = self.assess(key)
        made = decide(
            application=seen.application,
            findings=seen.findings,
            decided_on=on,
            distance=seen.distance,
            tariff=self.tariff,
            size_rule=self.size_rule,
            escort_schedule=self.escorts,
        )
        return seen, made

    def refer(self, key: int, on: Day) -> Review:
        """Put an application on the engineer's list.

        Only an application the desk would refer gets a review. Referring one a
        clerk could have written is how an engineer's list fills up with work
        nobody needed doing.
        """
        _, made = self.decide(key, on)
        if made.outcome is not Outcome.REFER:
            raise NotAllowedError("application", str(made.outcome), "refer")
        for existing in self.office.reviews.for_application(key):
            if existing.open:
                raise ConflictError("review", existing.reference)
        return self.office.reviews.add(
            open_review(self.office.reviews.next_reference(), key, on)
        )

    def approve(
        self, reference: str, engineer: str, on: Day, conditions: tuple[str, ...] = ()
    ) -> Review:
        """Approve a review, with whatever conditions the engineer set."""
        review = self.office.reviews.get(reference)
        return self.office.reviews.save_state(review.approved_by(engineer, on, conditions))

    def refuse(self, reference: str, engineer: str, on: Day, note: str) -> Review:
        """Refuse a review, with the engineer's reason."""
        review = self.office.reviews.get(reference)
        return self.office.reviews.save_state(review.refused_by(engineer, on, note))

    def approval_for(self, key: int) -> Review | None:
        """The approved review covering one application, if there is one."""
        for review in self.office.reviews.for_application(key):
            if review.approved:
                return review
        return None

    def issue(self, key: int, on: Day) -> Permit:
        """Decide one application and write the permit, if there is one.

        A referred application may still be issued once an engineer has approved
        it. The engineer's conditions come through onto the permit as notes, so
        the driver's copy carries them and nothing has to be remembered.
        """
        seen, made = self.decide(key, on)
        if made.outcome is Outcome.REFER:
            approval = self.approval_for(key)
            if approval is None:
                raise NotAllowedError("application", str(made.outcome), "issue a permit for")
            made = self._cleared(seen, made, approval, on)
        if made.outcome is not Outcome.ISSUE:
            raise NotAllowedError("application", str(made.outcome), "issue a permit for")
        permit = issue(self.office.permits.next_number(), made, on)
        return self.office.permits.add(permit, seen.filed.key)

    def _cleared(self, seen: Assessed, made: Decision, approval: Review, on: Day) -> Decision:
        """Redecide an application an engineer has cleared.

        The blocking findings are kept, with their severity lowered to a note, so
        the permit still shows what was over and by how much. The engineer's own
        conditions are added beside them.
        """
        softened = tuple(
            Finding(
                rule=f.rule,
                subject=f.subject,
                severity=Severity.NOTE if f.severity is Severity.REFUSE else f.severity,
                detail=(
                    f"{f.detail} (cleared by {approval.reference})"
                    if f.severity is Severity.REFUSE
                    else f.detail
                ),
                excess=NO_WEIGHT if f.severity is Severity.REFUSE else f.excess,
            )
            for f in made.findings
        )
        conditions = tuple(
            Finding(
                rule="review-condition",
                subject=str(approval.reference),
                severity=Severity.NOTE,
                detail=text,
            )
            for text in approval.conditions
        )
        return decide(
            application=seen.application,
            findings=softened + conditions,
            decided_on=on,
            distance=seen.distance,
            tariff=self.tariff,
            size_rule=self.size_rule,
            escort_schedule=self.escorts,
            cleared=True,
        )

    def void(self, number: str, reason: str, on: Day, refund: bool = True) -> Permit:
        """Void an issued permit and put the fee back on the account.

        The refund is posted only if the fee was actually charged. A permit
        issued and never charged has nothing to give back, and posting a refund
        for it would hand the carrier money the office never took, which is a
        mistake the void report would not show.
        """
        permit = self.office.permits.get(number)
        voided = self.office.permits.save_state(permit.voided(reason, on))
        if refund and self._was_charged(voided):
            self.office.accounts.post(
                carrier=voided.carrier,
                day=on,
                kind=EntryKind.REFUND,
                amount=voided.fee,
                reference=str(voided.number),
                note=f"void: {voided.reason}",
            )
        return voided

    def _was_charged(self, permit: Permit) -> bool:
        """Has this permit's fee already been charged to its carrier."""
        charges = self.office.accounts.account(permit.carrier).of_kind(EntryKind.CHARGE)
        refunds = self.office.accounts.account(permit.carrier).of_kind(EntryKind.REFUND)
        number = str(permit.number)
        charged = any(entry.reference == number for entry in charges)
        already = any(entry.reference == number for entry in refunds)
        return charged and not already

    def extend(self, number: str, last: Day) -> Permit:
        """Push an issued permit's last day back a few days."""
        permit = self.office.permits.get(number)
        return self.office.permits.save_state(permit.extended(last))

    def amend(self, number: str, application: Application, on: Day) -> Permit:
        """Replace a permit with a fresh one and mark the old one superseded.

        The new permit is decided from scratch. Nothing is carried over from the
        old one, including its fee, because an amendment that changed the rig
        and kept the fee is the shape of a costly mistake.
        """
        old = self.office.permits.get(number)
        if not old.live:
            raise NotAllowedError("permit", str(old.state), "amend")
        filed = self.file(application)
        new = self.issue(filed.key, on)
        self.office.permits.save_state(old.superseded_by(new.number))
        return new

    def blockers_of(self, key: int) -> tuple[Finding, ...]:
        """Just the reasons one application cannot be permitted."""
        return tuple(f for f in self.assess(key).findings if f.severity is Severity.REFUSE)
