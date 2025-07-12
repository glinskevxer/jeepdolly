"""Report commands: the permit sheet, the day sheet and the return."""

from __future__ import annotations

import click

from jeepdolly.almanac.embargo import EmbargoBook
from jeepdolly.cli.context import Session, office_of
from jeepdolly.report.daily import day_sheet
from jeepdolly.report.permit import permit_sheet, route_sheet
from jeepdolly.report.revenue import revenue_sheet
from jeepdolly.route.search import shortest
from jeepdolly.units.clock import DaySpan, parse_day

__all__ = ["report"]


@click.group()
def report() -> None:
    """Print the office's paperwork."""


@report.command("permit")
@click.argument("number")
@click.pass_obj
def permit_report(session: Session, number: str) -> None:
    """Print one permit as it goes in the cab."""
    with office_of(session) as office:
        found = office.permits.get(number)
        lines = permit_sheet(found)
    for line in lines:
        click.echo(line)


@report.command("route")
@click.option("--from", "origin", required=True, help="Junction the run starts at.")
@click.option("--to", "destination", required=True, help="Junction the run ends at.")
@click.pass_obj
def route_report(session: Session, origin: str, destination: str) -> None:
    """Print the route sheet between two junctions."""
    with office_of(session) as office:
        network = office.roadway.network()
        found = shortest(network, origin, destination)
        if found is None:
            click.echo("no way through")
            return
        lines = route_sheet(found, network)
    for line in lines:
        click.echo(line)


@report.command("day")
@click.argument("day")
@click.pass_obj
def day_report(session: Session, day: str) -> None:
    """Print the movement sheet for one day."""
    with office_of(session) as office:
        network = office.roadway.network()
        wanted = parse_day(day)
        lines = day_sheet(office.permits.good_on(wanted), wanted, network, EmbargoBook(()))
    for line in lines:
        click.echo(line)


@report.command("revenue")
@click.option("--first", default="", help="First day of the return.")
@click.option("--last", default="", help="Last day of the return.")
@click.pass_obj
def revenue_report(session: Session, first: str, last: str) -> None:
    """Print the revenue return."""
    with office_of(session) as office:
        span = DaySpan(parse_day(first), parse_day(last)) if first and last else None
        lines = revenue_sheet(office.permits.all(), span)
    for line in lines:
        click.echo(line)
