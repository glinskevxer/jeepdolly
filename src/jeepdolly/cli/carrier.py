"""Carrier commands, including the paper a carrier has lodged."""

from __future__ import annotations

import click

from jeepdolly.cli.ask import day_or_today
from jeepdolly.cli.context import Session, office_of
from jeepdolly.party.carrier import Carrier
from jeepdolly.party.contact import Contact, Role
from jeepdolly.party.surety import Certificate, Cover
from jeepdolly.permit.application import Kind
from jeepdolly.permit.cover import gaps, requirements
from jeepdolly.report.surety import CHASE_WITHIN, cover_sheet
from jeepdolly.units.clock import DaySpan, parse_day
from jeepdolly.units.money import parse_money

__all__ = ["carrier"]


@click.group()
def carrier() -> None:
    """Add, list and retire carriers."""


@carrier.command("add")
@click.option("--code", required=True, help="The office's short key for this carrier.")
@click.option("--name", required=True, help="The trading name.")
@click.option("--usdot", required=True, type=int, help="The federal number.")
@click.option("--state", required=True, help="Two letter home state.")
@click.pass_obj
def add(session: Session, code: str, name: str, usdot: int, state: str) -> None:
    """Put a new carrier on file."""
    with office_of(session) as office, office.writing():
        made = office.carriers.add(
            Carrier(code=code, name=name, usdot=usdot, home_state=state)  # type: ignore[arg-type]
        )
    click.echo(str(made))


@carrier.command("list")
@click.option("--all", "show_all", is_flag=True, help="Include retired carriers.")
@click.pass_obj
def listing(session: Session, show_all: bool) -> None:
    """List carriers, active ones by default."""
    with office_of(session) as office:
        found = office.carriers.all() if show_all else office.carriers.active()
    if not found:
        click.echo("no carriers on file")
        return
    for one in found:
        click.echo(str(one))


@carrier.command("show")
@click.argument("code")
@click.pass_obj
def show(session: Session, code: str) -> None:
    """Show one carrier."""
    with office_of(session) as office:
        found = office.carriers.get(code)
    click.echo(str(found))
    click.echo(f"home state {found.home_state}")
    click.echo("issuable" if found.issuable else "not issuable")


@carrier.command("retire")
@click.argument("code")
@click.pass_obj
def retire(session: Session, code: str) -> None:
    """Stop a carrier being issued new permits."""
    with office_of(session) as office, office.writing():
        found = office.carriers.get(code)
        office.carriers.save(found.retired())
    click.echo(f"{found.code} retired")


@carrier.command("restore")
@click.argument("code")
@click.pass_obj
def restore(session: Session, code: str) -> None:
    """Let a retired carrier be issued permits again."""
    with office_of(session) as office, office.writing():
        found = office.carriers.get(code)
        office.carriers.save(found.restored())
    click.echo(f"{found.code} restored")


@carrier.command("contact")
@click.argument("code")
@click.option(
    "--role",
    type=click.Choice([str(r) for r in Role]),
    default=str(Role.DISPATCH),
    show_default=True,
    help="What the office would ring them about.",
)
@click.option("--name", required=True, help="Who answers.")
@click.option("--number", required=True, help="Their phone number, however you have it.")
@click.option("--email", default="", help="Their address, if there is one.")
@click.option("--primary", is_flag=True, help="Ring this one by default.")
@click.pass_obj
def contact(
    session: Session,
    code: str,
    role: str,
    name: str,
    number: str,
    email: str,
    primary: bool,
) -> None:
    """Record who to ring at a carrier."""
    with office_of(session) as office, office.writing():
        made = office.contacts.put(
            Contact(
                carrier=code,  # type: ignore[arg-type]
                role=Role(role),
                name=name,
                number=number,
                email=email,
                primary=primary,
            )
        )
    click.echo(str(made))


@carrier.command("contacts")
@click.argument("code")
@click.pass_obj
def contacts(session: Session, code: str) -> None:
    """List everyone the office has a number for at a carrier."""
    with office_of(session) as office:
        found = office.contacts.for_carrier(code)
    if not found:
        click.echo("no contacts on file")
        return
    for one in found:
        click.echo(str(one))


@carrier.command("primary")
@click.argument("code")
@click.option(
    "--role",
    type=click.Choice([str(r) for r in Role]),
    required=True,
    help="Which contact becomes the default.",
)
@click.pass_obj
def primary(session: Session, code: str, role: str) -> None:
    """Make one contact the one to ring by default."""
    with office_of(session) as office, office.writing():
        made = office.contacts.promote(code, Role(role))
    click.echo(str(made))


@carrier.command("ring")
@click.argument("number")
@click.pass_obj
def ring(session: Session, number: str) -> None:
    """Say whose number this is."""
    with office_of(session) as office:
        found = office.contacts.by_number(number)
    if not found:
        click.echo("nobody on file has that number")
        return
    for one in found:
        click.echo(str(one))


@carrier.command("search")
@click.argument("text")
@click.pass_obj
def search(session: Session, text: str) -> None:
    """Find carriers by part of a name or code."""
    with office_of(session) as office:
        found = office.carriers.search(text)
    if not found:
        click.echo("nothing found")
        return
    for one in found:
        click.echo(str(one))


@carrier.command("lodge")
@click.argument("code")
@click.option(
    "--cover",
    required=True,
    type=click.Choice([str(c) for c in Cover]),
    help="What the certificate covers.",
)
@click.option("--insurer", required=True, help="Who wrote the policy.")
@click.option("--policy", required=True, help="The insurer's own number for it.")
@click.option("--amount", required=True, help="Face amount, like 100000 or $1,000,000.")
@click.option("--from", "first", required=True, help="First day it is good.")
@click.option("--to", "last", required=True, help="Last day it is good.")
@click.pass_obj
def lodge(
    session: Session,
    code: str,
    cover: str,
    insurer: str,
    policy: str,
    amount: str,
    first: str,
    last: str,
) -> None:
    """Put a bond or a policy on file against a carrier."""
    made = Certificate(
        carrier=code,  # type: ignore[arg-type]
        cover=Cover(cover),
        insurer=insurer,
        policy=policy,
        amount=parse_money(amount),
        span=DaySpan(parse_day(first), parse_day(last)),
    )
    with office_of(session) as office, office.writing():
        office.surety.put(made)
    click.echo(str(made))


@carrier.command("paper")
@click.argument("code")
@click.option("--on", "day", help="The day to read the file as at, default today.")
@click.pass_obj
def paper(session: Session, code: str, day: str | None) -> None:
    """List what a carrier has lodged, and what is good today."""
    on = day_or_today(day or "")
    with office_of(session) as office:
        held = office.surety.for_carrier(code)
        good = {str(one.policy) for one in office.surety.in_force(code, on)}
    if not held:
        click.echo(f"{code} has nothing on file")
        return
    for one in held:
        mark = "good" if one.policy in good else "not good"
        click.echo(f"{one} [{mark}]")


@carrier.command("cover")
@click.argument("code")
@click.option(
    "--kind",
    default=str(Kind.TRIP),
    type=click.Choice([str(k) for k in Kind]),
    help="Which sort of permit to check against.",
)
@click.option("--escorted", is_flag=True, help="Price in the escort cover as well.")
@click.option("--on", "day", help="The day to read the file as at, default today.")
@click.pass_obj
def cover(session: Session, code: str, kind: str, escorted: bool, day: str | None) -> None:
    """Say whether a carrier is clear to be issued a permit."""
    on = day_or_today(day or "")
    with office_of(session) as office:
        held = office.surety.for_carrier(code)
    wanted = Kind(kind)
    short = gaps(held, wanted, on, escorted)
    for need in requirements(wanted, escorted):
        click.echo(f"needs {need}")
    if not short:
        click.echo(f"{code} is clear for a {wanted} permit")
        return
    for one in short:
        click.echo(str(one))
    raise SystemExit(1)


@carrier.command("chase")
@click.option("--within", default=CHASE_WITHIN, type=int, help="How many days ahead to look.")
@click.option("--on", "day", help="The day to read the file as at, default today.")
@click.pass_obj
def chase(session: Session, within: int, day: str | None) -> None:
    """Print the certificate chase list across every carrier."""
    on = day_or_today(day or "")
    with office_of(session) as office:
        held = [
            one for row in office.carriers.all() for one in office.surety.for_carrier(row.code)
        ]
    for line in cover_sheet(held, on, within):
        click.echo(line)
