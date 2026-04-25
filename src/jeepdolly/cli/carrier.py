"""Carrier commands."""

from __future__ import annotations

import click

from jeepdolly.cli.context import Session, office_of
from jeepdolly.party.carrier import Carrier
from jeepdolly.party.contact import Contact, Role

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
