"""The entry point."""

from __future__ import annotations

from pathlib import Path

import click

from jeepdolly import __version__
from jeepdolly.cli.account import account
from jeepdolly.cli.carrier import carrier
from jeepdolly.cli.context import DEFAULT_FILE, Session, reporting
from jeepdolly.cli.permit import permit
from jeepdolly.cli.report import report
from jeepdolly.cli.rig import rig
from jeepdolly.cli.road import road
from jeepdolly.store.migrations import LATEST
from jeepdolly.store.office import create, opened_office

__all__ = ["main"]


@click.group()
@click.option(
    "--file",
    "-f",
    "path",
    default=str(DEFAULT_FILE),
    envvar="JEEPDOLLY_FILE",
    show_default=True,
    help="The office file to work on.",
)
@click.option("--debug", is_flag=True, help="Show the traceback instead of one line.")
@click.version_option(__version__)
@click.pass_context
def main(ctx: click.Context, path: str, debug: bool) -> None:
    """Oversize and overweight permit records."""
    ctx.obj = Session(path=Path(path), debug=debug)


@main.command("init")
@click.pass_obj
def init(session: Session) -> None:
    """Make a new office file."""
    with reporting(session):
        create(session.path)
    click.echo(f"created {session.path} at schema {LATEST}")


@main.command("status")
@click.pass_obj
def status(session: Session) -> None:
    """Say what is in the office file."""
    with reporting(session), opened_office(session.path) as office:
        click.echo(f"file {session.path}")
        click.echo(f"schema {office.version} of {LATEST}")
        click.echo(f"carriers {office.carriers.count()}")
        click.echo(f"rigs {office.rigs.count()}")
        click.echo(f"loads {office.loads.count()}")
        nodes, segments, structures = office.roadway.counts()
        click.echo(f"junctions {nodes}")
        click.echo(f"segments {segments}")
        click.echo(f"structures {structures}")
        click.echo(f"applications {office.applications.count()}")
        click.echo(f"permits {office.permits.count()}")


main.add_command(carrier)
main.add_command(road)
main.add_command(rig)
main.add_command(permit)
main.add_command(account)
main.add_command(report)
