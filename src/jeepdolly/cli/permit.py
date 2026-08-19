"""Permit commands: apply, quote, issue, void, extend."""

from __future__ import annotations

import click

from jeepdolly.cli.ask import day_or_today, today
from jeepdolly.cli.context import Session, office_of
from jeepdolly.limits.assess import Assessment
from jeepdolly.limits.finding import Finding
from jeepdolly.limits.relief import remedies_for
from jeepdolly.limits.statute import INTERSTATE
from jeepdolly.permit.application import Application, Kind
from jeepdolly.permit.desk import Desk
from jeepdolly.permit.revoke import Cause
from jeepdolly.rig.load import NONDIVISIBLE_REASONS, Load
from jeepdolly.units.clock import DaySpan, format_day, parse_day
from jeepdolly.units.distance import format_distance
from jeepdolly.units.length import parse_length
from jeepdolly.units.mass import parse_weight
from jeepdolly.units.money import cents, format_money

__all__ = ["permit"]


def _show(findings: tuple[Finding, ...]) -> None:
    """Print findings one per line, worst last so the eye lands on it."""
    for finding in findings:
        click.echo(f"  {finding.severity}: {finding}")


@click.group()
def permit() -> None:
    """Apply for, price and issue permits."""


@permit.command("apply")
@click.option("--carrier", required=True, help="Whose permit this is.")
@click.option("--rig", required=True, help="Which rig, by reference.")
@click.option("--description", required=True, help="What is on the trailer.")
@click.option("--weight", required=True, help="Load weight.")
@click.option("--width", required=True, help="Load width.")
@click.option("--height", required=True, help="Load height.")
@click.option("--length", required=True, help="Deck length.")
@click.option("--front-overhang", default="0", show_default=True, help="Front overhang.")
@click.option("--rear-overhang", default="0", show_default=True, help="Rear overhang.")
@click.option(
    "--reason",
    type=click.Choice(NONDIVISIBLE_REASONS),
    default=NONDIVISIBLE_REASONS[0],
    show_default=True,
    help="Why the load cannot be split.",
)
@click.option("--divisible", is_flag=True, help="The load can be split up.")
@click.option(
    "--kind",
    type=click.Choice([str(k) for k in Kind]),
    default=str(Kind.TRIP),
    show_default=True,
    help="What sort of permit.",
)
@click.option("--first", required=True, help="First day the permit is good.")
@click.option("--last", required=True, help="Last day the permit is good.")
@click.option("--origin", default="", help="Junction the run starts at.")
@click.option("--destination", default="", help="Junction the run ends at.")
@click.option("--filed", default="", help="Day the application was taken.")
@click.pass_obj
def apply(session: Session, /, **given: str) -> None:
    """Take an application at the counter."""
    with office_of(session) as office, office.writing():
        load = Load(
            description=given["description"],
            weight=parse_weight(given["weight"]),
            width=parse_length(given["width"]),
            height=parse_length(given["height"]),
            length=parse_length(given["length"]),
            front_overhang=parse_length(given["front_overhang"]),
            rear_overhang=parse_length(given["rear_overhang"]),
            divisible=bool(given["divisible"]),
            reason="" if given["divisible"] else given["reason"],
        )
        filed_on = parse_day(given["filed"]) if given["filed"] else today()
        application = Application(
            carrier=given["carrier"],  # type: ignore[arg-type]
            rig=given["rig"],  # type: ignore[arg-type]
            load=load,
            span=DaySpan(parse_day(given["first"]), parse_day(given["last"])),
            filed_on=filed_on,
            kind=Kind(given["kind"]),
            origin=given["origin"] or None,  # type: ignore[arg-type]
            destination=given["destination"] or None,  # type: ignore[arg-type]
        )
        desk = Desk.at(office, clerk=session.clerk)
        alike = desk.like(application)
        made = desk.file(application)
    click.echo(f"application {made.key}: {made.application}")
    for one in alike:
        click.echo(f"warning: {one}")


@permit.command("quote")
@click.argument("key", type=int)
@click.option("--on", default="", help="Day the decision is made.")
@click.pass_obj
def quote(session: Session, key: int, on: str) -> None:
    """Price an application without issuing anything."""
    with office_of(session) as office:
        desk = Desk.at(office, clerk=session.clerk)
        seen, made = desk.decide(key, parse_day(on) if on else today())
        if seen.route is not None:
            codes = " ".join(str(s.code) for s in seen.route.segments)
            click.echo(f"route {codes} {format_distance(seen.route.distance)}")
        click.echo(f"outcome {made.outcome}")
        if made.findings:
            click.echo("findings")
            _show(made.findings)
        for escort in made.escorts:
            click.echo(f"escort {escort}")
        if made.invoice is None:
            click.echo("not priced")
            return
        for line in made.invoice.lines:
            click.echo(f"  {line}")
        click.echo(f"total {format_money(made.invoice.total)}")


@permit.command("advise")
@click.argument("key", type=int)
@click.pass_obj
def advise(session: Session, key: int) -> None:
    """Say what would have to change to get an application through."""
    with office_of(session) as office:
        seen = Desk.at(office, clerk=session.clerk).assess(key)
        remedies = remedies_for(Assessment(findings=seen.findings), INTERSTATE)
    if not remedies:
        click.echo("nothing has to change")
        return
    for one in remedies:
        click.echo(f"{one.kind}: {one}")


@permit.command("issue")
@click.argument("key", type=int)
@click.option("--on", default="", help="Day the permit is issued.")
@click.pass_obj
def issue_one(session: Session, key: int, on: str) -> None:
    """Decide an application and write the permit."""
    with office_of(session) as office, office.writing():
        made = Desk.at(office, clerk=session.clerk).issue(key, parse_day(on) if on else today())
    click.echo(f"{made.number} issued, {format_money(made.fee)}")


@permit.command("renew")
@click.argument("number")
@click.option("--on", default="", help="Day the renewal is taken.")
@click.option("--first", default="", help="First day of the new permit.")
@click.pass_obj
def renew_one(session: Session, number: str, on: str, first: str) -> None:
    """File the application that renews a permit."""
    with office_of(session) as office, office.writing():
        made = Desk.at(office, clerk=session.clerk).renew(
            number, day_or_today(on), parse_day(first) if first else None
        )
    click.echo(f"application {made.key}: {made.application}")


@permit.command("show")
@click.argument("number")
@click.pass_obj
def show(session: Session, number: str) -> None:
    """Print one permit."""
    with office_of(session) as office:
        found = office.permits.get(number)
        click.echo(str(found))
        click.echo(f"carrier {found.carrier}")
        click.echo(f"issued {format_day(found.issued_on)}")
        click.echo(f"fee {format_money(found.fee)}")
        for escort in found.decision.escorts:
            click.echo(f"escort {escort}")
        if found.decision.findings:
            click.echo("findings")
            _show(found.decision.findings)


@permit.command("void")
@click.argument("number")
@click.option(
    "--cause",
    required=True,
    type=click.Choice([str(c) for c in Cause]),
    help="Why the permit is being pulled.",
)
@click.option("--detail", default="", help="What happened, for an at fault cause.")
@click.option("--on", default="", help="Day the void is recorded.")
@click.pass_obj
def void(session: Session, number: str, cause: str, detail: str, on: str) -> None:
    """Pull an issued permit and refund whatever the reason calls for."""
    with office_of(session) as office, office.writing():
        desk = Desk.at(office, clerk=session.clerk)
        made = desk.void(number, Cause(cause), day_or_today(on), detail)
        back = office.revocations.get(str(made.number))
    click.echo(f"{made.number} void: {back.cause}")
    click.echo(f"refunded {format_money(back.refunded)}")
    if back.blocks_until is not None:
        click.echo(f"{made.carrier} cannot be issued anything to {back.blocks_until}")


@permit.command("extend")
@click.argument("number")
@click.option("--last", required=True, help="New last day.")
@click.pass_obj
def extend(session: Session, number: str, last: str) -> None:
    """Push a permit's last day back."""
    with office_of(session) as office, office.writing():
        made = Desk.at(office, clerk=session.clerk).extend(number, parse_day(last))
    click.echo(f"{made.number} now good to {format_day(made.span.last)}")


@permit.command("list")
@click.option("--carrier", default="", help="Only this carrier's permits.")
@click.option("--on", default="", help="Only permits good on this day.")
@click.pass_obj
def listing(session: Session, carrier: str, on: str) -> None:
    """List permits, filtered by carrier or by day."""
    with office_of(session) as office:
        if carrier:
            found = office.permits.for_carrier(carrier)
        elif on:
            found = office.permits.good_on(parse_day(on))
        else:
            found = office.permits.all()
    if not found:
        click.echo("no permits")
        return
    for one in found:
        click.echo(f"{one} {format_money(one.fee)}")


def _amended(now: Application, given: dict[str, str]) -> Application:
    """The current application with whatever the clerk typed swapped in.

    Everything not named keeps what the permit already says. An amendment is
    almost always one field, and making the clerk retype the load to change the
    destination is how the destination gets changed along with the width.
    """
    load = Load(
        description=given["description"] or now.load.description,
        weight=parse_weight(given["weight"]) if given["weight"] else now.load.weight,
        width=parse_length(given["width"]) if given["width"] else now.load.width,
        height=parse_length(given["height"]) if given["height"] else now.load.height,
        length=parse_length(given["length"]) if given["length"] else now.load.length,
        front_overhang=now.load.front_overhang,
        rear_overhang=now.load.rear_overhang,
        divisible=now.load.divisible,
        reason=now.load.reason,
    )
    span = DaySpan(
        parse_day(given["first"]) if given["first"] else now.span.first,
        parse_day(given["last"]) if given["last"] else now.span.last,
    )
    return Application(
        carrier=now.carrier,
        rig=given["rig"] or now.rig,  # type: ignore[arg-type]
        load=load,
        span=span,
        filed_on=now.filed_on,
        kind=now.kind,
        origin=given["origin"] or now.origin,  # type: ignore[arg-type]
        destination=given["destination"] or now.destination,  # type: ignore[arg-type]
    )


@permit.command("amend")
@click.argument("number")
@click.option("--rig", default="", help="Move the permit onto another rig.")
@click.option("--description", default="", help="What is on the trailer.")
@click.option("--weight", default="", help="New load weight.")
@click.option("--width", default="", help="New load width.")
@click.option("--height", default="", help="New load height.")
@click.option("--length", default="", help="New deck length.")
@click.option("--first", default="", help="New first day.")
@click.option("--last", default="", help="New last day.")
@click.option("--origin", default="", help="New junction to start at.")
@click.option("--destination", default="", help="New junction to end at.")
@click.option("--note", default="", help="Why it was amended.")
@click.option("--on", default="", help="Day the amendment was taken.")
@click.pass_obj
def amend(session: Session, /, number: str, **given: str) -> None:
    """Change an issued permit without giving it a new number."""
    with office_of(session) as office, office.writing():
        desk = Desk.at(office, clerk=session.clerk)
        wanted = _amended(desk.current(number), given)
        made = desk.amend(number, wanted, day_or_today(given["on"]), given["note"])
    click.echo(str(made.amendment))
    word = "refund" if int(made.charged) < 0 else "charged"
    click.echo(f"{word} {format_money(cents(abs(int(made.charged))))}")


@permit.command("amendments")
@click.argument("number")
@click.pass_obj
def amendments(session: Session, number: str) -> None:
    """List every amendment written against one permit, oldest first."""
    with office_of(session) as office:
        chain = office.amendments.for_permit(number)
    if not chain:
        click.echo(f"{number} has not been amended")
        return
    for one in chain:
        line = f"{format_day(one.amendment.filed_on)} {one.amendment}"
        click.echo(f"{line} {format_money(one.charged)}")
        if one.amendment.note:
            click.echo(f"  {one.amendment.note}")


@permit.command("alike")
@click.argument("key", type=int)
@click.pass_obj
def alike(session: Session, key: int) -> None:
    """List anything already on file that looks like the same move."""
    with office_of(session) as office:
        filed = office.applications.get(key)
        found = [
            one
            for one in Desk.at(office, clerk=session.clerk).like(filed.application)
            if one.key != key
        ]
    if not found:
        click.echo(f"application {key} does not look like anything else on file")
        return
    for one in found:
        click.echo(str(one))
