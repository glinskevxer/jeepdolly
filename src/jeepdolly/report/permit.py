"""The printed permit and the route sheet that goes with it.

Two documents from the same record. The permit is what goes in the cab and gets
handed to an officer at the scale; it is short, it names the rig and the load,
and it lists the conditions. The route sheet is what the driver follows and it
is a stretch per line with the structures called out.

Both are lists of lines rather than one string. The caller decides how to join
them, which is the difference between printing to a terminal, writing a file and
folding them into a larger report.
"""

from __future__ import annotations

from jeepdolly.permit.permit import Permit
from jeepdolly.report.layout import LEFT, RIGHT, pairs, table
from jeepdolly.report.sheet import Sheet
from jeepdolly.roadway.network import Network
from jeepdolly.route.plan import Route
from jeepdolly.units.clock import format_day
from jeepdolly.units.distance import format_distance, hundredths
from jeepdolly.units.length import format_length
from jeepdolly.units.mass import format_weight
from jeepdolly.units.money import format_money

__all__ = ["conditions", "fee_table", "permit_sheet", "route_sheet"]


def conditions(permit: Permit) -> list[str]:
    """The conditions printed on the back of the permit.

    Escorts first, because they are what the carrier has to arrange, then the
    notes from the assessment, which are what the driver has to do.
    """
    lines: list[str] = []
    for escort in permit.decision.escorts:
        lines.append(f"{escort.role} escort: {', '.join(escort.reasons)}")
    for finding in permit.decision.findings:
        if str(finding.severity) == "note":
            lines.append(finding.detail)
    return lines


def fee_table(permit: Permit) -> list[str]:
    """The fee lines and the total, laid out."""
    invoice = permit.decision.invoice
    assert invoice is not None
    body = [[line.code, line.detail, format_money(line.amount)] for line in invoice.lines]
    body.append(["", "total", format_money(invoice.total)])
    return table(["code", "detail", "amount"], body, aligns=[LEFT, LEFT, RIGHT])


def permit_sheet(permit: Permit) -> list[str]:
    """The permit as it is printed for the cab."""
    application = permit.application
    load = application.load
    sheet = Sheet().title(f"oversize permit {permit.number}")
    sheet.notes(
        pairs(
            [
                ("carrier", permit.carrier),
                ("rig", str(application.rig)),
                ("kind", str(application.kind)),
                ("good", str(permit.span)),
                ("issued", format_day(permit.issued_on)),
                ("state", str(permit.state)),
            ]
        )
    )
    sheet.section("load").notes(
        pairs(
            [
                ("description", load.description),
                ("weight", format_weight(load.weight)),
                ("width", format_length(load.width)),
                ("height", format_length(load.height)),
                ("length", format_length(load.overall_length)),
                ("divisible", "yes" if load.divisible else "no"),
            ]
        )
    )
    if application.routed:
        sheet.section("route").notes(
            pairs(
                [
                    ("from", str(application.origin)),
                    ("to", str(application.destination)),
                    (
                        "distance",
                        "-"
                        if permit.decision.distance is None
                        else format_distance(permit.decision.distance),
                    ),
                ]
            )
        )
    found = conditions(permit)
    if found:
        sheet.section("conditions").notes(f"- {line}" for line in found)
    sheet.section("fee").notes(fee_table(permit))
    if permit.state != "active":
        sheet.section(f"NOT VALID: this permit is {permit.state}")
        if permit.reason:
            sheet.note(f"reason: {permit.reason}")
    return sheet.done()


def route_sheet(route: Route, network: Network) -> list[str]:
    """The stretch by stretch sheet the driver follows."""
    sheet = Sheet().title(f"route sheet {route.origin} to {route.destination}")
    body: list[list[str]] = []
    running = 0
    for index, leg in enumerate(route.legs, start=1):
        running += int(leg.distance)
        body.append(
            [
                str(index),
                leg.segment.route,
                str(leg.from_node),
                str(leg.to_node),
                format_distance(leg.distance),
                format_distance(hundredths(running)),
            ]
        )
    sheet.rows(
        ["leg", "route", "from", "to", "miles", "running"],
        body,
        aligns=[RIGHT, LEFT, LEFT, LEFT, RIGHT, RIGHT],
    )
    built: list[list[str]] = []
    for leg in route.legs:
        for structure in network.structures_on(str(leg.segment.code)):
            posted = (
                format_length(structure.clearance)
                if structure.clearance is not None
                else format_weight(structure.rating)
                if structure.rating is not None
                else "unposted"
            )
            built.append(
                [
                    str(leg.segment.code),
                    format_distance(structure.milepost),
                    str(structure.reference),
                    structure.name,
                    posted,
                ]
            )
    if built:
        sheet.section("structures on the route").rows(
            ["stretch", "milepost", "reference", "name", "posted"], built
        )
    return sheet.summary([("total", format_distance(route.distance))]).done()
