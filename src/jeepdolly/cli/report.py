"""Report commands: the permit sheet, the day sheet and the return."""

from __future__ import annotations

import click

from jeepdolly.almanac.embargo import EmbargoBook
from jeepdolly.cli.context import Session, office_of
from jeepdolly.report.carrier import CarrierFile, carrier_sheet
from jeepdolly.report.daily import counties_of, day_sheet
from jeepdolly.report.layout import banner, pairs, table
from jeepdolly.report.permit import permit_sheet, route_sheet
from jeepdolly.report.revenue import revenue_sheet
from jeepdolly.rig.load import Load
from jeepdolly.route.detour import detour_for
from jeepdolly.route.search import shortest
from jeepdolly.travel.schedule import plan_days
from jeepdolly.units.clock import DaySpan, format_day, parse_day
from jeepdolly.units.length import feet, parse_length

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


@report.command("carrier")
@click.argument("code")
@click.pass_obj
def carrier_report(session: Session, code: str) -> None:
    """Print everything the office holds about one carrier."""
    with office_of(session) as office:
        found = office.carriers.get(code)
        permits = office.permits.for_carrier(str(found.code))
        subjects = {str(p.number) for p in permits}
        events = [e for e in office.history.all() if e.subject in subjects]
        file = CarrierFile(
            carrier=found,
            rigs=tuple(office.rigs.for_carrier(str(found.code))),
            permits=tuple(permits),
            account=office.accounts.account(str(found.code)),
            events=tuple(events),
        )
        lines = carrier_sheet(file)
    for line in lines:
        click.echo(line)


@report.command("detour")
@click.option("--from", "origin", required=True, help="Junction the run starts at.")
@click.option("--to", "destination", required=True, help="Junction the run ends at.")
@click.option("--rig", required=True, help="Which rig, by reference.")
@click.option("--closed", required=True, help="Comma separated stretches that are shut.")
@click.option("--width", default="8'6\"", show_default=True, help="Load width.")
@click.option("--height", default="13'6\"", show_default=True, help="Load height.")
@click.pass_obj
def detour_report(
    session: Session,
    origin: str,
    destination: str,
    rig: str,
    closed: str,
    width: str,
    height: str,
) -> None:
    """Say what closing some stretches does to one rig's run."""
    shut = [part.strip() for part in closed.split(",") if part.strip()]
    with office_of(session) as office:
        network = office.roadway.network()
        filed = office.rigs.get(rig)
        load = Load(
            description="detour enquiry",
            weight=filed.config.gross,
            width=parse_length(width),
            height=parse_length(height),
            length=feet(48),
            divisible=False,
            reason="single-piece",
        )
        made = detour_for(network, origin, destination, filed.config, load, shut)
    click.echo(str(made))
    if made.usual is not None:
        click.echo(f"  usual   {' '.join(str(s.code) for s in made.usual.segments)}")
    if made.instead is not None:
        click.echo(f"  instead {' '.join(str(s.code) for s in made.instead.segments)}")


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


@report.command("schedule")
@click.argument("number")
@click.option("--county", default="", help="Which county, or blank for every one on the route.")
@click.pass_obj
def schedule_report(session: Session, number: str, county: str) -> None:
    """Print the day by day movement plan for one permit."""
    with office_of(session) as office:
        found = office.permits.get(number)
        network = office.roadway.network()
        book = office.almanac.embargo_book()
        counties = [county] if county else list(counties_of(found, network)) or ["statewide"]
        lines: list[str] = []
        for where in counties:
            made = plan_days(found.application.load, found.span, where, book)
            if lines:
                lines.append("")
            lines.extend(banner(f"{found.number} in {where}"))
            lines.extend(
                table(
                    ["day", "hours", "stopped by"],
                    [
                        [format_day(one.day), one.hours, ", ".join(one.stopped_by) or "-"]
                        for one in made.days
                    ],
                )
            )
            lines.append("")
            lines.extend(
                pairs(
                    [
                        ("days", str(len(made))),
                        ("movable", str(len(made.movable))),
                        ("stopped", str(len(made.stopped))),
                    ]
                )
            )
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
