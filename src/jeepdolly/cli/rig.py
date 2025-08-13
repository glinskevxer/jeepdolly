"""Rig commands: record an arrangement and read it back."""

from __future__ import annotations

import datetime as dt

import click

from jeepdolly.cli.context import Session, office_of
from jeepdolly.rig.axle import Axle
from jeepdolly.rig.config import Configuration
from jeepdolly.units.clock import format_day, parse_day
from jeepdolly.units.length import feet, format_length, inches
from jeepdolly.units.mass import format_weight, parse_weight

__all__ = ["rig"]

#: The arrangement the counter records when nobody says otherwise: a five axle
#: tractor semitrailer at the legal weights.
DEFAULT_AXLES = (
    (12000, 2, 11, 0),
    (17000, 4, 11, 15),
    (17000, 4, 11, 4),
    (17000, 4, 11, 30),
    (17000, 4, 11, 4),
)


@click.group()
def rig() -> None:
    """Record rigs and read them back."""


@rig.command("build")
@click.option("--carrier", required=True, help="Whose rig this is.")
@click.option("--name", required=True, help="The carrier's shorthand, like 3S2.")
@click.option(
    "--axle",
    "axles",
    multiple=True,
    help="One axle as weight,tires,tire width,spacing ahead. Repeat per axle.",
)
@click.option("--on", default="", help="Day the rig was recorded.")
@click.pass_obj
def build(session: Session, carrier: str, name: str, axles: tuple[str, ...], on: str) -> None:
    """Record a rig, axle by axle."""
    parsed = [_axle(text) for text in axles] if axles else list(DEFAULT_AXLES)
    made = Configuration(
        name=name,  # type: ignore[arg-type]
        axles=tuple(
            Axle(
                weight=parse_weight(str(weight)),
                tires=tires,
                tire_width=inches(width),
                steering=index == 0,
            )
            for index, (weight, tires, width, _) in enumerate(parsed)
        ),
        spacings=tuple(feet(gap) for *_, gap in parsed[1:]),
    )
    with office_of(session) as office, office.writing():
        day = parse_day(on) if on else dt.datetime.now().astimezone().date()
        filed = office.rigs.add(carrier, made, day)
    click.echo(f"{filed.reference} {filed.config}")


def _axle(text: str) -> tuple[int, int, int, int]:
    """Read one ``weight,tires,width,spacing`` field."""
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 4:
        raise click.BadParameter("want weight,tires,tire width,spacing ahead")
    try:
        weight, tires, width, gap = (int(p.replace(",", "")) for p in parts)
    except ValueError as exc:
        raise click.BadParameter("every field is a whole number") from exc
    return weight, tires, width, gap


@rig.command("show")
@click.argument("reference")
@click.pass_obj
def show(session: Session, reference: str) -> None:
    """Print one rig, axle by axle."""
    with office_of(session) as office:
        filed = office.rigs.get(reference)
    click.echo(f"{filed.reference} {filed.carrier} {filed.config.name}")
    click.echo(f"recorded {format_day(filed.recorded_on)}")
    click.echo(f"gross {format_weight(filed.config.gross)}")
    click.echo(f"wheelbase {format_length(filed.config.wheelbase)}")
    for index, axle in enumerate(filed.config.axles):
        ahead = (
            "" if index == 0 else f", {format_length(filed.config.spacings[index - 1])} ahead"
        )
        click.echo(f"  axle {index + 1}: {axle}{ahead}")


@rig.command("list")
@click.option("--carrier", default="", help="Only this carrier's rigs.")
@click.pass_obj
def listing(session: Session, carrier: str) -> None:
    """List rigs, filtered by carrier."""
    with office_of(session) as office:
        found = office.rigs.for_carrier(carrier) if carrier else office.rigs.all()
    if not found:
        click.echo("no rigs on file")
        return
    for one in found:
        click.echo(str(one))
