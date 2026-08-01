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
from jeepdolly.billing.reprice import Reprice, reprice
from jeepdolly.billing.tariff import SCHEDULE, Tariff
from jeepdolly.enforce.ticket import Ticket, check_ticket
from jeepdolly.enforce.violation import Violation, violations_from
from jeepdolly.errors import ConflictError, NotAllowedError, NotFoundError
from jeepdolly.limits.assess import assess
from jeepdolly.limits.dimension import LEGAL, SizeRule
from jeepdolly.limits.finding import Finding, Severity
from jeepdolly.permit.amendment import Amendment, amend
from jeepdolly.permit.application import Application
from jeepdolly.permit.decision import Decision, Outcome, decide
from jeepdolly.permit.permit import Permit, issue
from jeepdolly.permit.renewal import renew
from jeepdolly.permit.review import Review, open_review
from jeepdolly.permit.revoke import Cause, Revocation, revoke
from jeepdolly.rig.config import Configuration
from jeepdolly.route.clear import RouteReport, walk
from jeepdolly.route.plan import Route
from jeepdolly.route.search import clearing, shortest
from jeepdolly.store.amendments import FiledAmendment
from jeepdolly.store.applications import FiledApplication
from jeepdolly.store.history import EventKind
from jeepdolly.store.office import Office
from jeepdolly.travel.escort import ORDINARY as ORDINARY_ESCORTS
from jeepdolly.travel.escort import EscortSchedule
from jeepdolly.units.clock import Day
from jeepdolly.units.distance import Miles
from jeepdolly.units.mass import NO_WEIGHT, Pounds
from jeepdolly.units.money import cents, format_money

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
    """The counter, holding the file and the office's standing rules.

    ``clerk`` is whoever is at the counter. It is written into the journal and
    nowhere else, and it is allowed to be blank, because the office ran for a
    year before anybody was asked to sign on.
    """

    office: Office
    tariff: Tariff = SCHEDULE
    size_rule: SizeRule = LEGAL
    escorts: EscortSchedule = ORDINARY_ESCORTS
    seasons: SeasonBook = field(default_factory=lambda: SeasonBook(seasons=()))
    embargoes: EmbargoBook = field(default_factory=lambda: EmbargoBook(embargoes=()))
    clerk: str = ""

    def note(self, day: Day, kind: EventKind, subject: str, detail: str = "") -> None:
        """Write one line in the journal, beside the change it describes."""
        self.office.history.write(day, kind, subject, detail, self.clerk)

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
        filed = self.office.applications.add(application)
        self.note(
            application.filed_on,
            EventKind.FILED,
            f"application {filed.key}",
            f"{application.carrier} {application.kind} {application.load.description}",
        )
        return filed

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
        opened = self.office.reviews.add(
            open_review(self.office.reviews.next_reference(), key, on)
        )
        self.note(on, EventKind.REFERRED, str(opened.reference), f"application {key}")
        return opened

    def approve(
        self, reference: str, engineer: str, on: Day, conditions: tuple[str, ...] = ()
    ) -> Review:
        """Approve a review, with whatever conditions the engineer set."""
        review = self.office.reviews.get(reference)
        done = self.office.reviews.save_state(review.approved_by(engineer, on, conditions))
        self.note(
            on,
            EventKind.APPROVED,
            str(done.reference),
            f"{engineer}, {len(done.conditions)} conditions",
        )
        return done

    def refuse(self, reference: str, engineer: str, on: Day, note: str) -> Review:
        """Refuse a review, with the engineer's reason."""
        review = self.office.reviews.get(reference)
        done = self.office.reviews.save_state(review.refused_by(engineer, on, note))
        self.note(on, EventKind.REFUSED, str(done.reference), f"{engineer}: {done.note}")
        return done

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

        A carrier sitting under an at fault revocation is refused here rather
        than at the counter. The block runs for months and the clerk taking the
        application is rarely the clerk who pulled the permit that caused it.
        """
        seen, made = self.decide(key, on)
        holding = self.blocked(str(seen.application.carrier), on)
        if holding is not None:
            raise NotAllowedError(
                "carrier",
                f"blocked to {holding.blocks_until} for {holding.cause}",
                "be issued a permit",
            )
        if made.outcome is Outcome.REFER:
            approval = self.approval_for(key)
            if approval is None:
                raise NotAllowedError("application", str(made.outcome), "issue a permit for")
            made = self._cleared(seen, made, approval, on)
        if made.outcome is not Outcome.ISSUE:
            raise NotAllowedError("application", str(made.outcome), "issue a permit for")
        permit = issue(self.office.permits.next_number(), made, on)
        written = self.office.permits.add(permit, seen.filed.key)
        self.note(
            on,
            EventKind.ISSUED,
            str(written.number),
            f"{written.carrier} {format_money(written.fee)} on application {seen.filed.key}",
        )
        return written

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

    def void(self, number: str, cause: Cause, on: Day, detail: str = "") -> Permit:
        """Pull an issued permit, and refund whatever the reason says to.

        This used to take a sentence and a boolean. The sentence meant nothing to
        anything downstream and the boolean was the clerk deciding the refund at
        the counter, which is how two identical cancellations a week apart came
        back at different figures.

        The refund is posted only if the fee was actually charged. A permit
        issued and never charged has nothing to give back, and posting a refund
        for it would hand the carrier money the office never took, which is a
        mistake the void report would not show.
        """
        permit = self.office.permits.get(number)
        pulled, made = revoke(permit, cause, on, detail, self.tariff)
        voided = self.office.permits.save_state(pulled)
        self.office.revocations.add(made, voided.carrier)
        self.note(on, EventKind.VOIDED, str(voided.number), str(made.cause))
        if int(made.refunded) > 0 and self._was_charged(voided):
            self.office.accounts.post(
                carrier=voided.carrier,
                day=on,
                kind=EntryKind.REFUND,
                amount=made.refunded,
                reference=str(voided.number),
                note=f"void: {made.cause}",
            )
            self.note(on, EventKind.REFUNDED, str(voided.number), format_money(made.refunded))
        return voided

    def weigh(
        self, number: str, axles: tuple[Pounds, ...], on: Day, place: str, officer: str
    ) -> tuple[Ticket, list[Violation]]:
        """Take a weight ticket against a permit and price whatever it found.

        The permit's own gross is what the rig is measured against, and the rig
        it is compared to is the one the permit currently names rather than the
        one it was issued against. A carrier that amended onto a heavier rig on
        the Tuesday is weighed against the Tuesday rig on the Wednesday.

        A permit amended on the day of the weighing forgives the repeat multiple.
        Most of those are an amendment that never reached the driver, and the
        office would rather charge the pounds than the pattern.
        """
        permit = self.office.permits.get(number)
        wanted = self.office.amendments.current(number)
        rig = self.office.rigs.get(str(wanted.rig))
        ticket = Ticket(
            number=self.office.enforcement.next_number(),
            permit=permit.number,
            weighed_on=on,
            place=place,
            officer=officer,
            axles=axles,
        )
        chain = self.office.amendments.for_permit(number)
        forgiven = any(one.amendment.filed_on == on for one in chain)
        overages = check_ticket(ticket, rig.config, rig.config.gross)
        history = self.office.enforcement.violations_of(permit.carrier)
        found = violations_from(
            overages, ticket.number, permit.number, permit.carrier, on, history, forgiven
        )
        self.office.enforcement.add(ticket, found, forgiven)
        self.note(on, EventKind.WEIGHED, str(permit.number), str(ticket))
        for one in found:
            self.office.accounts.post(
                carrier=permit.carrier,
                day=on,
                kind=EntryKind.CHARGE,
                amount=one.penalty,
                reference=str(ticket.number),
                note=str(one.kind),
            )
        return ticket, found

    def blocked(self, carrier: str, on: Day) -> Revocation | None:
        """Whatever is stopping this carrier being issued anything today."""
        return self.office.revocations.blocking(carrier, on)

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
        longer = self.office.permits.save_state(permit.extended(last))
        self.note(last, EventKind.EXTENDED, str(longer.number), f"good to {longer.span.last}")
        return longer

    def amend(
        self, number: str, application: Application, on: Day, note: str = ""
    ) -> FiledAmendment:
        """Change an issued permit in place, keeping its number.

        This used to void the permit and write a new one, which was tidy in the
        file and wrong at the roadside. The carrier has the old number painted
        on the escort boards and the bridge owners have it in their notification,
        so a supersession that landed the morning of the move read to enforcement
        as a permit that had been pulled.

        What the permit was issued at stays on the permit. The difference goes on
        the account against the same number, so the fee ledger still adds up and
        the original invoice is still the invoice that was paid.
        """
        permit = self.office.permits.get(number)
        made = amend(permit, application, on, note)
        wanted = self.file(made.now)
        settled = self._settle(permit, made, wanted.key, on)
        filed = self.office.amendments.add(made, settled.due, wanted.key)
        if made.now.span != permit.span:
            self.office.permits.save_state(permit.respanned(made.now.span))
        self.note(on, EventKind.AMENDED, str(permit.number), str(made))
        if int(settled.due) != 0:
            self._post_amendment(permit, settled, on)
        return filed

    def _settle(self, permit: Permit, made: Amendment, key: int, on: Day) -> Reprice:
        """Work out what one amendment costs, repricing it if it has to be."""
        was_invoice = permit.decision.invoice
        assert was_invoice is not None
        if not made.material:
            return reprice(made.was, made.now, was_invoice, was_invoice, False, self.tariff)
        _, decision = self.decide(key, on)
        now_invoice = decision.invoice
        if now_invoice is None:
            raise NotAllowedError("permit", "no longer issuable", "amend onto")
        return reprice(made.was, made.now, was_invoice, now_invoice, True, self.tariff)

    def _post_amendment(self, permit: Permit, settled: Reprice, on: Day) -> None:
        """Put the amendment's charge or refund on the carrier's account."""
        owed = int(settled.due)
        self.office.accounts.post(
            carrier=permit.carrier,
            day=on,
            kind=EntryKind.REFUND if owed < 0 else EntryKind.CHARGE,
            amount=cents(abs(owed)),
            reference=str(permit.number),
            note="amendment",
        )

    def current(self, number: str) -> Application:
        """What an issued permit says now, after every amendment against it."""
        return self.office.amendments.current(number)

    def renew(self, number: str, on: Day, first: Day | None = None) -> FiledApplication:
        """File the application that renews a permit, without deciding it.

        Filing and deciding are kept apart here on purpose. A renewal is assessed
        against today's limits and this year's frost laws, and the clerk wants to
        see what it says before the carrier is told the price.
        """
        permit = self.office.permits.get(number)
        made = renew(permit, on, first)
        filed = self.file(made.application)
        self.note(
            on,
            EventKind.FILED,
            f"application {filed.key}",
            f"renews {permit.number} as {made.span}",
        )
        return filed

    def blockers_of(self, key: int) -> tuple[Finding, ...]:
        """Just the reasons one application cannot be permitted."""
        return tuple(f for f in self.assess(key).findings if f.severity is Severity.REFUSE)
