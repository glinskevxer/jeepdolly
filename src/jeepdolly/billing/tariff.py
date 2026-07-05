"""The fee schedule.

A permit fee is a sum of named lines and never a single number worked out in one
expression. The carrier gets the lines printed on the invoice, the auditor
recomputes them one at a time, and a change to one line does not disturb the
others.

The overweight charge is banded and *progressive*. Ten tons over is charged at
the first band's rate; thirty tons over is charged at the first band for the
first ten, the second band for the next fifteen, and the third for the rest. A
flat lookup would be simpler and would produce a cliff at every band edge where
one extra ton costs three hundred dollars, which is the sort of thing carriers
notice.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from jeepdolly.errors import BadValueError
from jeepdolly.units.distance import Miles, whole_miles
from jeepdolly.units.mass import Pounds, tons_over
from jeepdolly.units.money import Money, at_rate, cents, format_money, total

__all__ = [
    "SCHEDULE",
    "Band",
    "FeeLine",
    "Tariff",
    "band_charge",
    "check_bands",
]


@dataclass(frozen=True, slots=True, order=True)
class Band:
    """One step of a progressive charge.

    ``upper`` is the number of tons this band runs to, counted from zero. The
    last band carries ``None``, which means it runs to whatever is left.
    """

    upper: int | None
    rate: Money

    def __post_init__(self) -> None:
        object.__setattr__(self, "rate", cents(int(self.rate)))
        if self.upper is not None:
            if isinstance(self.upper, bool) or not isinstance(self.upper, int):
                raise BadValueError("band", self.upper, "want a whole number of tons")
            if self.upper < 1:
                raise BadValueError("band", self.upper, "want at least one ton")
        if int(self.rate) < 0:
            raise BadValueError("rate", int(self.rate), "negative")


def check_bands(bands: tuple[Band, ...]) -> None:
    """A band table has climbing edges and exactly one open band, at the end."""
    if not bands:
        raise BadValueError("bands", bands, "want at least one band")
    if any(b.upper is None for b in bands[:-1]):
        raise BadValueError("bands", bands, "only the last band runs to the end")
    if bands[-1].upper is not None:
        raise BadValueError("bands", bands, "the last band runs to the end")
    edges = [b.upper for b in bands[:-1] if b.upper is not None]
    if edges != sorted(set(edges)):
        raise BadValueError("bands", edges, "the band edges climb")


def band_charge(tons: int, bands: tuple[Band, ...]) -> Money:
    """Charge a quantity across a progressive band table."""
    if isinstance(tons, bool) or not isinstance(tons, int):
        raise BadValueError("tons", tons, "want a whole number")
    if tons < 0:
        raise BadValueError("tons", tons, "negative")
    check_bands(bands)
    lines: list[Money] = []
    floor = 0
    for band in bands:
        ceiling = tons if band.upper is None else min(tons, band.upper)
        if ceiling > floor:
            lines.append(at_rate(band.rate, ceiling - floor))
        floor = max(floor, 0 if band.upper is None else band.upper)
        if floor >= tons:
            break
    return total(lines)


@dataclass(frozen=True, slots=True)
class FeeLine:
    """One line on the invoice."""

    code: str
    detail: str
    amount: Money

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", cents(int(self.amount)))
        for field in ("code", "detail"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise BadValueError(field, value, "want some text")
            object.__setattr__(self, field, " ".join(value.split()))

    def __str__(self) -> str:
        return f"{self.code} {self.detail} {format_money(self.amount)}"


@dataclass(frozen=True, slots=True)
class Tariff:
    """Every rate the office charges."""

    name: str
    trip_base: Money
    annual_base: Money
    superload_base: Money
    per_mile: Money
    per_escort: Money
    per_foot_over_width: Money
    per_foot_over_height: Money
    amendment_fee: Money
    overweight_bands: tuple[Band, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise BadValueError("name", self.name, "want some text")
        for field in (
            "trip_base",
            "annual_base",
            "superload_base",
            "per_mile",
            "per_escort",
            "per_foot_over_width",
            "per_foot_over_height",
            "amendment_fee",
        ):
            value = cents(int(getattr(self, field)))
            if int(value) < 0:
                raise BadValueError(field, int(value), "negative")
            object.__setattr__(self, field, value)
        object.__setattr__(self, "overweight_bands", tuple(self.overweight_bands))
        band_charge(0, self.overweight_bands)

    def mileage(self, distance: Miles) -> Money:
        """The distance charge, billed on whole miles rounded up."""
        return at_rate(self.per_mile, whole_miles(distance))

    def overweight(self, excess: Pounds, limit: Pounds) -> Money:
        """The overweight charge for a rig that is over a limit."""
        return band_charge(tons_over(excess, limit), self.overweight_bands)

    def overweight_tons(self, tons: int) -> Money:
        """The overweight charge for a number of tons already worked out."""
        return band_charge(tons, self.overweight_bands)

    def escorts(self, count: int) -> Money:
        """The administrative charge for the escorts the permit calls for."""
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise BadValueError("escorts", count, "want a whole number")
        return at_rate(self.per_escort, count)

    def over_width(self, feet_over: Decimal | int) -> Money:
        """The width charge, per foot or part foot over the legal width."""
        return at_rate(self.per_foot_over_width, feet_over)

    def over_height(self, feet_over: Decimal | int) -> Money:
        """The height charge, per foot or part foot over the legal height."""
        return at_rate(self.per_foot_over_height, feet_over)


#: The office's standing schedule.
SCHEDULE = Tariff(
    name="2025 schedule",
    trip_base=cents(2500),
    annual_base=cents(50000),
    superload_base=cents(15000),
    per_mile=cents(6),
    per_escort=cents(1500),
    per_foot_over_width=cents(1000),
    per_foot_over_height=cents(1500),
    amendment_fee=cents(3500),
    overweight_bands=(
        Band(upper=10, rate=cents(500)),
        Band(upper=25, rate=cents(800)),
        Band(upper=None, rate=cents(1200)),
    ),
)
