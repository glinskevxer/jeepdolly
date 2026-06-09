"""Journal commands: what the office did, and when."""

from __future__ import annotations

import click

from jeepdolly.cli.context import Session, office_of
from jeepdolly.report.layout import LEFT, RIGHT, banner, table
from jeepdolly.store.history import EventKind
from jeepdolly.units.clock import DaySpan, format_day, parse_day

__all__ = ["history"]


@click.group()
def history() -> None:
    """Read the office journal."""


@history.command("show")
@click.option("--about", default="", help="Only entries about this permit or application.")
@click.option("--kind", default="", help="Only entries of this kind.")
@click.option("--first", default="", help="First day to show.")
@click.option("--last", default="", help="Last day to show.")
@click.pass_obj
def show(session: Session, about: str, kind: str, first: str, last: str) -> None:
    """Print the journal, narrowed however you like."""
    with office_of(session) as office:
        if about:
            found = office.history.about(about)
        elif kind:
            found = office.history.of_kind(EventKind(kind))
        elif first and last:
            found = office.history.within(DaySpan(parse_day(first), parse_day(last)))
        else:
            found = office.history.all()
        if not found:
            click.echo("nothing in the journal")
            return
        lines = banner("office journal")
        lines.extend(
            table(
                ["no", "day", "subject", "what", "clerk", "detail"],
                [
                    [
                        str(one.sequence),
                        format_day(one.day),
                        one.subject,
                        str(one.kind),
                        one.clerk or "-",
                        one.detail or "-",
                    ]
                    for one in found
                ],
                aligns=[RIGHT, LEFT, LEFT, LEFT, LEFT, LEFT],
            )
        )
    for line in lines:
        click.echo(line)


@history.command("kinds")
def kinds() -> None:
    """List the kinds of entry the journal holds."""
    for one in EventKind:
        click.echo(str(one))
