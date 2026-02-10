"""File maintenance: soundness, backups and vacuuming."""

from __future__ import annotations

from pathlib import Path

import click

from jeepdolly.cli.context import Session, office_of, reporting
from jeepdolly.report.layout import LEFT, RIGHT, banner, pairs, table
from jeepdolly.store.backup import back_up, check_file, file_size, row_counts, vacuum

__all__ = ["office"]


def _bytes(count: int) -> str:
    """A byte count in the units a clerk reads."""
    if count < 1024:
        return f"{count} B"
    if count < 1024 * 1024:
        return f"{count / 1024:.1f} kB"
    return f"{count / (1024 * 1024):.1f} MB"


@click.group()
def office() -> None:
    """Look after the office file itself."""


@office.command("sound")
@click.pass_obj
def sound(session: Session) -> None:
    """Ask sqlite whether the file is whole, and the office whether it is current."""
    with reporting(session):
        found = check_file(session.path)
    click.echo(str(found))
    if not found.sound:
        raise SystemExit(1)


@office.command("backup")
@click.argument("target", type=click.Path(dir_okay=False, path_type=Path))
@click.pass_obj
def backup(session: Session, target: Path) -> None:
    """Copy the office file page by page to somewhere else."""
    with reporting(session):
        made = back_up(session.path, target)
    click.echo(f"wrote {made} ({_bytes(file_size(made))})")


@office.command("vacuum")
@click.pass_obj
def compact(session: Session) -> None:
    """Rebuild the file into as few pages as it needs."""
    with reporting(session):
        before = file_size(session.path)
        saved = vacuum(session.path)
    click.echo(f"{_bytes(before)} before, {_bytes(saved)} freed")


@office.command("rows")
@click.pass_obj
def counts(session: Session) -> None:
    """Print how many rows each table holds."""
    with office_of(session) as made:
        found = row_counts(made.connection)
        lines = banner("row counts")
        lines.extend(
            table(
                ["table", "rows"],
                [[name, str(number)] for name, number in found.items()],
                aligns=[LEFT, RIGHT],
            )
        )
        lines.append("")
        lines.extend(
            pairs(
                [
                    ("tables", str(len(found))),
                    ("rows", str(sum(found.values()))),
                    ("size", _bytes(file_size(session.path))),
                ]
            )
        )
    for line in lines:
        click.echo(line)
