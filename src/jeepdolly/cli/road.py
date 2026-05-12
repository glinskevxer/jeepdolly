"""Road map commands."""

from __future__ import annotations

import click

from jeepdolly.cli.context import Session, office_of
from jeepdolly.roadway.node import Node
from jeepdolly.roadway.segment import RoadClass, Segment
from jeepdolly.roadway.structure import Structure, StructureKind
from jeepdolly.units.distance import format_distance, parse_distance
from jeepdolly.units.length import format_length, parse_length
from jeepdolly.units.mass import format_weight, parse_weight

__all__ = ["road"]


@click.group()
def road() -> None:
    """Put junctions, stretches and structures on the map."""


@road.command("node")
@click.option("--code", required=True, help="The office's key for the junction.")
@click.option("--name", required=True, help="What the route sheet calls it.")
@click.option("--county", required=True, help="Which county it sits in.")
@click.pass_obj
def add_node(session: Session, code: str, name: str, county: str) -> None:
    """Put a junction on the map."""
    with office_of(session) as office, office.writing():
        made = office.roadway.add_node(
            Node(code=code, name=name, county=county)  # type: ignore[arg-type]
        )
    click.echo(str(made))


@road.command("segment")
@click.option("--code", required=True, help="The office's key for the stretch.")
@click.option("--start", required=True, help="Junction it leaves.")
@click.option("--end", required=True, help="Junction it reaches.")
@click.option("--route", required=True, help="Route designation, like US-12.")
@click.option("--miles", "distance", required=True, help="Length, to a hundredth.")
@click.option(
    "--class",
    "road_class",
    type=click.Choice([str(c) for c in RoadClass]),
    default=str(RoadClass.STATE),
    show_default=True,
    help="Which limit set applies.",
)
@click.option("--one-way", is_flag=True, help="Only travelled start to end.")
@click.option("--posted", default="", help="Local gross order, if there is one.")
@click.option("--max-width", default="", help="Width the road itself will take.")
@click.option("--max-height", default="", help="Height the road itself will take.")
@click.pass_obj
def add_segment(
    session: Session,
    code: str,
    start: str,
    end: str,
    route: str,
    distance: str,
    road_class: str,
    one_way: bool,
    posted: str,
    max_width: str,
    max_height: str,
) -> None:
    """Put a stretch of road on the map."""
    with office_of(session) as office, office.writing():
        made = office.roadway.add_segment(
            Segment(
                code=code,  # type: ignore[arg-type]
                start=start,  # type: ignore[arg-type]
                end=end,  # type: ignore[arg-type]
                route=route,
                distance=parse_distance(distance),
                road_class=RoadClass(road_class),
                one_way=one_way,
                posted_gross=parse_weight(posted) if posted else None,
                max_width=parse_length(max_width) if max_width else None,
                max_height=parse_length(max_height) if max_height else None,
            )
        )
    click.echo(f"{made} {format_distance(made.distance)}")


@road.command("structure")
@click.option("--segment", required=True, help="Which stretch it sits on.")
@click.option("--name", required=True, help="What the bridge crew calls it.")
@click.option(
    "--kind",
    type=click.Choice([str(k) for k in StructureKind]),
    default=str(StructureKind.BRIDGE),
    show_default=True,
    help="What sort of thing it is.",
)
@click.option("--milepost", required=True, help="Where on the stretch it sits.")
@click.option("--clearance", default="", help="Posted height, for an overhead.")
@click.option("--rating", default="", help="Posted load, for a bridge.")
@click.pass_obj
def add_structure(
    session: Session,
    segment: str,
    name: str,
    kind: str,
    milepost: str,
    clearance: str,
    rating: str,
) -> None:
    """Put something in the way on a stretch."""
    with office_of(session) as office, office.writing():
        made = office.roadway.add_structure(
            Structure(
                reference=office.roadway.next_structure(),
                segment=segment,  # type: ignore[arg-type]
                name=name,
                kind=StructureKind(kind),
                milepost=parse_distance(milepost),
                clearance=parse_length(clearance) if clearance else None,
                rating=parse_weight(rating) if rating else None,
            )
        )
    click.echo(str(made))


@road.command("map")
@click.pass_obj
def show_map(session: Session) -> None:
    """Print the map, one stretch per line."""
    with office_of(session) as office:
        network = office.roadway.network()
        lines = []
        for segment in network:
            lines.append(f"{segment} {format_distance(segment.distance)}")
            for structure in network.structures_on(str(segment.code)):
                posted = (
                    format_length(structure.clearance)
                    if structure.clearance is not None
                    else format_weight(structure.rating)
                    if structure.rating is not None
                    else "unposted"
                )
                lines.append(
                    f"    {structure.reference} {structure.name}"
                    f" at {format_distance(structure.milepost)}, {posted}"
                )
        joined = network.connected
        counts = office.roadway.counts()
    if not lines:
        click.echo("nothing on the map")
        return
    for line in lines:
        click.echo(line)
    click.echo(f"{counts[0]} junctions, {counts[1]} stretches, {counts[2]} structures")
    click.echo("joined up" if joined else "not joined up")
