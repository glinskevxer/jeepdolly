"""Enforcement commands: weighing a rig and reading what it cost."""

from __future__ import annotations

import click

from jeepdolly.cli.ask import day_or_today
from jeepdolly.cli.context import Session, office_of
from jeepdolly.enforce.violation import owed
from jeepdolly.permit.desk import Desk
from jeepdolly.units.mass import format_weight, parse_weight
from jeepdolly.units.money import format_money

__all__ = ["enforce"]


@click.group()
def enforce() -> None:
    """Weigh a permitted rig and price what the scales found."""


@enforce.command("weigh")
@click.argument("number")
@click.option(
    "--axle",
    "axles",
    multiple=True,
    required=True,
    help="One pad weight, given once per axle in order.",
)
@click.option("--place", required=True, help="Where the rig was weighed.")
@click.option("--officer", required=True, help="Who weighed it.")
@click.option("--on", default="", help="Day it was weighed.")
@click.pass_obj
def weigh(
    session: Session,
    number: str,
    axles: tuple[str, ...],
    place: str,
    officer: str,
    on: str,
) -> None:
    """Take a weight ticket against a permit."""
    weights = tuple(parse_weight(one) for one in axles)
    with office_of(session) as office, office.writing():
        desk = Desk.at(office, clerk=session.clerk)
        ticket, found = desk.weigh(number, weights, day_or_today(on), place, officer)
    click.echo(str(ticket))
    if not found:
        click.echo("inside the permit")
        return
    for one in found:
        click.echo(str(one))
    click.echo(f"penalties {format_money(owed(found))}")


@enforce.command("tickets")
@click.argument("number")
@click.pass_obj
def tickets(session: Session, number: str) -> None:
    """List every weight ticket written against one permit."""
    with office_of(session) as office:
        found = office.enforcement.for_permit(number)
    if not found:
        click.echo(f"{number} has never been weighed")
        return
    for one in found:
        click.echo(str(one))


@enforce.command("record")
@click.argument("carrier")
@click.pass_obj
def record(session: Session, carrier: str) -> None:
    """Print a carrier's violation record, oldest first."""
    with office_of(session) as office:
        office.carriers.get(carrier)
        found = office.enforcement.violations_of(carrier)
    if not found:
        click.echo(f"{carrier} has nothing against it")
        return
    for one in found:
        click.echo(str(one))
    click.echo(f"{len(found)} violations, {format_money(owed(found))}")


@enforce.command("ticket")
@click.argument("number")
@click.pass_obj
def ticket(session: Session, number: str) -> None:
    """Show one weight ticket, pad by pad."""
    with office_of(session) as office:
        found = office.enforcement.get(number)
        against = office.enforcement.violations_on(number)
        forgiven = office.enforcement.forgiven(number)
    click.echo(str(found))
    for position, weight in enumerate(found.axles, start=1):
        click.echo(f"axle {position} {format_weight(weight)}")
    click.echo(f"gross {format_weight(found.gross)}")
    if forgiven:
        click.echo("charged as a first offence, the permit was amended that day")
    for one in against:
        click.echo(str(one))
