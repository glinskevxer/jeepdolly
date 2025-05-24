"""Turning a decided application into a bill.

The invoice is a list of lines and a total, and the total is the sum of the
lines and nothing else. There is no discount, no minimum and no rounding of the
total, because every one of those has to be a line the carrier can see.

Dimension charges are per foot or part foot over the legal figure. A load one
inch over twelve feet is charged for a whole foot, which is the schedule as
written; the office has been asked about it and the answer is that the schedule
is what the legislature passed.
"""

from __future__ import annotations

from dataclasses import dataclass

from jeepdolly.billing.tariff import SCHEDULE, FeeLine, Tariff
from jeepdolly.errors import BadValueError, NotFoundError
from jeepdolly.limits.dimension import LEGAL, SizeRule
from jeepdolly.permit.application import Application, Kind
from jeepdolly.rig.load import Load
from jeepdolly.units.distance import Miles, format_distance, whole_miles
from jeepdolly.units.length import Inches, format_length
from jeepdolly.units.mass import POUNDS_PER_TON, Pounds, format_weight
from jeepdolly.units.money import Money, format_money, total

__all__ = ["BASE_CODES", "Invoice", "feet_over", "price"]

#: Which base line each kind of permit gets.
BASE_CODES = {Kind.TRIP: "TRIP", Kind.ANNUAL: "ANNUAL", Kind.SUPERLOAD: "SUPER"}


def feet_over(value: Inches, limit: Inches) -> int:
    """Whole feet or part feet a dimension is over a limit, rounded up."""
    excess = int(value) - int(limit)
    if excess <= 0:
        return 0
    return -(-excess // 12)


@dataclass(frozen=True, slots=True)
class Invoice:
    """Every line the carrier owes on one permit."""

    lines: tuple[FeeLine, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "lines", tuple(self.lines))
        seen = [line.code for line in self.lines]
        if len(set(seen)) != len(seen):
            raise BadValueError("invoice", seen, "two lines share a code")

    @property
    def total(self) -> Money:
        """What the permit costs."""
        return total(line.amount for line in self.lines)

    @property
    def codes(self) -> tuple[str, ...]:
        """The line codes, in the order they were worked out."""
        return tuple(line.code for line in self.lines)

    def line(self, code: str) -> FeeLine:
        """One line by code."""
        for found in self.lines:
            if found.code == code:
                return found
        raise NotFoundError("fee line", code)

    def has(self, code: str) -> bool:
        """Is there a line with this code."""
        return code in self.codes

    def __len__(self) -> int:
        return len(self.lines)

    def __str__(self) -> str:
        return f"{len(self.lines)} lines, {format_money(self.total)}"


def _base_line(application: Application, tariff: Tariff) -> FeeLine:
    """The flat charge for the kind of permit asked for."""
    amounts = {
        Kind.TRIP: tariff.trip_base,
        Kind.ANNUAL: tariff.annual_base,
        Kind.SUPERLOAD: tariff.superload_base,
    }
    return FeeLine(
        code=BASE_CODES[application.kind],
        detail=f"{application.kind} permit, {application.days} days",
        amount=amounts[application.kind],
    )


def _size_lines(load: Load, tariff: Tariff, rule: SizeRule) -> list[FeeLine]:
    """The width and height charges, if either applies."""
    lines: list[FeeLine] = []
    wide = feet_over(load.width, rule.width)
    if wide:
        lines.append(
            FeeLine(
                code="WIDTH",
                detail=f"{format_length(load.width)} over {format_length(rule.width)}",
                amount=tariff.over_width(wide),
            )
        )
    tall = feet_over(load.height, rule.height)
    if tall:
        lines.append(
            FeeLine(
                code="HEIGHT",
                detail=f"{format_length(load.height)} over {format_length(rule.height)}",
                amount=tariff.over_height(tall),
            )
        )
    return lines


def price(
    application: Application,
    excess: Pounds,
    distance: Miles | None = None,
    escorts: int = 0,
    tariff: Tariff = SCHEDULE,
    rule: SizeRule = LEGAL,
) -> Invoice:
    """Work out what one permit costs, line by line.

    ``excess`` is the largest single billable overage from the assessment, not
    the sum of them. ``distance`` is only used on a routed permit; an annual
    permit has no route and is refused if one is handed in.
    """
    lines: list[FeeLine] = [_base_line(application, tariff)]
    if application.routed:
        if distance is None:
            raise BadValueError("distance", None, "a routed permit is billed by the mile")
        lines.append(
            FeeLine(
                code="MILES",
                detail=f"{format_distance(distance)} at {whole_miles(distance)} miles billed",
                amount=tariff.mileage(distance),
            )
        )
    elif distance is not None:
        raise BadValueError("distance", int(distance), "an annual permit has no route")
    if int(excess) > 0:
        tons = -(-int(excess) // POUNDS_PER_TON)
        lines.append(
            FeeLine(
                code="WEIGHT",
                detail=f"{format_weight(excess)} over, billed as {tons} tons",
                amount=tariff.overweight_tons(tons),
            )
        )
    lines.extend(_size_lines(application.load, tariff, rule))
    if escorts:
        lines.append(
            FeeLine(
                code="ESCORT",
                detail=f"{escorts} escort vehicles",
                amount=tariff.escorts(escorts),
            )
        )
    return Invoice(lines=tuple(lines))
