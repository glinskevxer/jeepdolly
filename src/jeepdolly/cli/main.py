"""The entry point."""

from __future__ import annotations

from pathlib import Path

import click

from jeepdolly import __version__
from jeepdolly.cli.account import account
from jeepdolly.cli.almanac import almanac
from jeepdolly.cli.carrier import carrier
from jeepdolly.cli.context import DEFAULT_FILE, Session, reporting
from jeepdolly.cli.enforce import enforce
from jeepdolly.cli.history import history
from jeepdolly.cli.office import office
from jeepdolly.cli.permit import permit
from jeepdolly.cli.report import report
from jeepdolly.cli.review import review
from jeepdolly.cli.rig import rig
from jeepdolly.cli.road import road
from jeepdolly.importer.csv_in import load_all
from jeepdolly.importer.csv_out import write_all
from jeepdolly.party.carrier import Carrier
from jeepdolly.permit.permit import Permit
from jeepdolly.store.migrations import LATEST
from jeepdolly.store.office import Office, create, opened_office

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
@click.option(
    "--clerk",
    default="",
    envvar="JEEPDOLLY_CLERK",
    help="Who is at the counter, for the journal.",
)
@click.version_option(__version__)
@click.pass_context
def main(ctx: click.Context, path: str, debug: bool, clerk: str) -> None:
    """Oversize and overweight permit records."""
    ctx.obj = Session(path=Path(path), debug=debug, clerk=clerk)


@main.command("init")
@click.pass_obj
def init(session: Session) -> None:
    """Make a new office file."""
    with reporting(session):
        create(session.path)
    click.echo(f"created {session.path} at schema {LATEST}")


@main.command("load")
@click.argument("folder", type=click.Path(exists=True, file_okay=False))
@click.pass_obj
def load(session: Session, folder: str) -> None:
    """Bulk load carriers and the map from a folder of csv files."""
    with reporting(session), opened_office(session.path) as office:
        got = load_all(office, Path(folder))
    click.echo(f"loaded {got}")


@main.command("dump")
@click.argument("folder", type=click.Path(file_okay=False))
@click.pass_obj
def dump(session: Session, folder: str) -> None:
    """Write the carriers and the map back out as csv files."""
    with reporting(session), opened_office(session.path) as office:
        got = write_all(office, Path(folder))
    click.echo(f"wrote {got} to {folder}")


@main.command("check")
@click.pass_obj
def check(session: Session) -> None:
    """Read the whole file back and say whether it holds together.

    Everything the office stores is validated on the way out, so reading it all
    is the check. A file that has been edited by hand, or that came off a backup
    half written, fails here rather than at the counter.
    """
    with reporting(session), opened_office(session.path) as office:
        network = office.roadway.network()
        carriers = office.carriers.all()
        permits = office.permits.all()
        counts = (
            len(carriers),
            len(office.rigs.all()),
            len(office.loads.all()),
            len(office.applications.all()),
            len(permits),
        )
        click.echo(f"schema {office.version} of {LATEST}")
        click.echo(f"map {'joined up' if network.connected else 'not joined up'}")
        click.echo(
            "read back {} carriers, {} rigs, {} loads, {} applications, {} permits".format(
                *counts
            )
        )
        _read_the_rest(office, carriers, permits)
        for carrier in carriers:
            office.accounts.account(str(carrier.code))
        click.echo("every account balances")
    click.echo("check: clean")


def _read_the_rest(office: Office, carriers: list[Carrier], permits: list[Permit]) -> None:
    """Read back everything hanging off a carrier or a permit.

    These tables came later and the check did not grow with them, which meant a
    hand edited certificate or a weight ticket with a broken pad row passed the
    check and failed at the counter. Reading them here is the whole point of the
    command: every record in this package validates on the way out, so reading it
    is the only check there is.
    """
    lodged = 0
    for one in carriers:
        key = str(one.code)
        lodged += len(office.surety.for_carrier(key))
        office.revocations.for_carrier(key)
        office.enforcement.violations_of(key)
    amended = 0
    weighed = 0
    for issued in permits:
        number = str(issued.number)
        amended += len(office.amendments.for_permit(number))
        weighed += len(office.enforcement.for_permit(number))
        office.amendments.current(number)
        office.revocations.find(number)
    click.echo(
        f"read back {lodged} certificates, {amended} amendments, {weighed} weight tickets"
    )


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
        click.echo(f"reviews {office.reviews.count()}")
        seasons, embargoes = office.almanac.counts()
        click.echo(f"seasons {seasons}")
        click.echo(f"embargoes {embargoes}")
        click.echo(f"journal {office.history.count()}")
        click.echo(f"clerk {session.clerk or 'not signed on'}")


main.add_command(carrier)
main.add_command(road)
main.add_command(rig)
main.add_command(permit)
main.add_command(account)
main.add_command(report)
main.add_command(review)
main.add_command(almanac)
main.add_command(history)
main.add_command(enforce)
main.add_command(office)
