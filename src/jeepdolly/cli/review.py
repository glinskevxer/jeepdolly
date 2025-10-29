"""Engineering review commands."""

from __future__ import annotations

import datetime as dt

import click

from jeepdolly.cli.context import Session, office_of
from jeepdolly.permit.desk import Desk
from jeepdolly.report.layout import LEFT, banner, table
from jeepdolly.units.clock import format_day, parse_day

__all__ = ["review"]


def _today() -> dt.date:
    """The office's idea of today."""
    return dt.datetime.now().astimezone().date()


@click.group()
def review() -> None:
    """Open, approve and refuse engineering reviews."""


@review.command("open")
@click.argument("application", type=int)
@click.option("--on", default="", help="Day the review is opened.")
@click.pass_obj
def open_one(session: Session, application: int, on: str) -> None:
    """Put a referred application on the engineer's list."""
    with office_of(session) as office, office.writing():
        made = Desk(office=office).refer(application, parse_day(on) if on else _today())
    click.echo(str(made))


@review.command("approve")
@click.argument("reference")
@click.option("--engineer", required=True, help="Who signed it off.")
@click.option("--on", default="", help="Day the decision was made.")
@click.option(
    "--condition",
    "conditions",
    multiple=True,
    help="A condition to print on the permit. Repeat for each one.",
)
@click.pass_obj
def approve(
    session: Session, reference: str, engineer: str, on: str, conditions: tuple[str, ...]
) -> None:
    """Approve a review with the engineer's conditions."""
    with office_of(session) as office, office.writing():
        made = Desk(office=office).approve(
            reference, engineer, parse_day(on) if on else _today(), conditions
        )
    click.echo(str(made))
    for text in made.conditions:
        click.echo(f"  condition: {text}")


@review.command("refuse")
@click.argument("reference")
@click.option("--engineer", required=True, help="Who refused it.")
@click.option("--note", required=True, help="Why it was refused.")
@click.option("--on", default="", help="Day the decision was made.")
@click.pass_obj
def refuse(session: Session, reference: str, engineer: str, note: str, on: str) -> None:
    """Refuse a review with the engineer's reason."""
    with office_of(session) as office, office.writing():
        made = Desk(office=office).refuse(
            reference, engineer, parse_day(on) if on else _today(), note
        )
    click.echo(f"{made} because {made.note}")


@review.command("list")
@click.option("--all", "show_all", is_flag=True, help="Include closed reviews.")
@click.pass_obj
def listing(session: Session, show_all: bool) -> None:
    """List the engineer's work, open ones by default."""
    with office_of(session) as office:
        found = office.reviews.all() if show_all else office.reviews.open_list()
        if not found:
            click.echo("nothing on the list")
            return
        lines = banner("engineering reviews")
        lines.extend(
            table(
                ["reference", "application", "opened", "state", "engineer"],
                [
                    [
                        str(one.reference),
                        str(one.application_key),
                        format_day(one.opened_on),
                        str(one.state),
                        one.engineer or "-",
                    ]
                    for one in found
                ],
                aligns=[LEFT] * 5,
            )
        )
    for line in lines:
        click.echo(line)
