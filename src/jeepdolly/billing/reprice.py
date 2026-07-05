"""What an amendment costs, once the permit has already been paid for.

Three rules, and the third one is the reason this is its own module rather than
four lines inside the invoice.

A clerical change is a flat handling charge. Nothing about the load or the road
moved, so there is nothing to work out again and the office is billing for the
clerk's time and the reprint.

A material change is priced from scratch at the current schedule, and the carrier
pays the difference. Not the new total, the difference, because they already paid
the old one.

And then the third: a difference that comes out negative is a refund, and the
refund is capped so the office keeps at least what the permit cost to write in
the first place. A carrier who books a hundred mile route, pays for it, and then
amends down to four miles is not owed most of their money back, because the
office did the whole assessment either way. That cap is what makes the sign of
the difference matter rather than just its size, and it is the rule that gets
forgotten every time somebody reimplements this.

Nothing here knows what an amendment is. It takes the two applications, the two
invoices, and one flag saying whether the change was material, which keeps the
fee schedule from having to grow an opinion about permit lifecycle.
"""

from __future__ import annotations

from dataclasses import dataclass

from jeepdolly.billing.invoice import Invoice
from jeepdolly.billing.tariff import SCHEDULE, FeeLine, Tariff
from jeepdolly.errors import BadValueError
from jeepdolly.permit.application import Application, Kind
from jeepdolly.units.money import Money, cents, format_money, total

__all__ = ["AMEND_CODE", "CREDIT_CODE", "DIFFERENCE_CODE", "Reprice", "day_credit", "reprice"]

#: The handling charge line, which every amendment carries.
AMEND_CODE = "AMEND"

#: The line that settles up a material change, whichever way it points.
DIFFERENCE_CODE = "DIFF"

#: The line that gives back unused days on a permit that was shortened.
CREDIT_CODE = "DAYS"


def day_credit(was: Application, now: Application, paid: Money) -> Money:
    """What the unused days on a shortened permit are worth.

    Only on a trip permit, and only on days actually given up. An annual is sold
    as a year and is not a season ticket the carrier can hand back in August.

    The share is worked out on whole days and rounded down, which is the office
    keeping the fraction. A day is a small enough unit that nobody has ever
    argued about the rounding, and doing it the other way would let a carrier
    amend a three day permit down to two and be owed more than a third.
    """
    for name, value in (("was", was), ("now", now)):
        if not isinstance(value, Application):
            raise BadValueError(name, value, "want an application")
    if was.kind is not Kind.TRIP or now.kind is not Kind.TRIP:
        return cents(0)
    given_up = was.span.days - now.span.days
    if given_up <= 0:
        return cents(0)
    return cents(int(cents(int(paid))) * given_up // was.span.days)


@dataclass(frozen=True, slots=True)
class Reprice:
    """The amendment's own invoice, and what the permit now stands at."""

    lines: tuple[FeeLine, ...]
    was_total: Money
    now_total: Money

    def __post_init__(self) -> None:
        object.__setattr__(self, "lines", tuple(self.lines))
        for name in ("was_total", "now_total"):
            object.__setattr__(self, name, cents(int(getattr(self, name))))
        seen = [line.code for line in self.lines]
        if len(set(seen)) != len(seen):
            raise BadValueError("reprice", seen, "two lines share a code")
        if not self.lines:
            raise BadValueError("reprice", seen, "an amendment charges something")

    @property
    def due(self) -> Money:
        """What the carrier owes for the amendment, negative when refunded."""
        return total(line.amount for line in self.lines)

    @property
    def refund(self) -> bool:
        """Does this amendment give money back rather than take it."""
        return int(self.due) < 0

    @property
    def codes(self) -> tuple[str, ...]:
        """The line codes, in the order they were worked out."""
        return tuple(line.code for line in self.lines)

    def __str__(self) -> str:
        word = "refund" if self.refund else "due"
        return f"amendment {word} {format_money(cents(abs(int(self.due))))}"


def _difference_line(was: Invoice, now: Invoice, tariff: Tariff) -> FeeLine | None:
    """The settle up line, capped so the office keeps its writing fee."""
    gap = int(now.total) - int(was.total)
    if gap == 0:
        return None
    if gap > 0:
        return FeeLine(
            code=DIFFERENCE_CODE,
            detail=f"repriced from {format_money(was.total)} to {format_money(now.total)}",
            amount=cents(gap),
        )
    keeps = int(tariff.trip_base)
    refundable = max(int(was.total) - keeps, 0)
    giving = min(-gap, refundable)
    if giving == 0:
        return None
    return FeeLine(
        code=DIFFERENCE_CODE,
        detail=f"repriced down, {format_money(tariff.trip_base)} retained",
        amount=cents(-giving),
    )


def reprice(
    was: Application,
    now: Application,
    was_invoice: Invoice,
    now_invoice: Invoice,
    material: bool,
    tariff: Tariff = SCHEDULE,
) -> Reprice:
    """Work out what one amendment costs.

    A clerical amendment never touches the permit's own total, so it comes back
    with the handling charge alone and both totals the same. Handing it the new
    invoice anyway keeps the caller from having to know that.
    """
    if not isinstance(material, bool):
        raise BadValueError("material", material, "want true or false")
    for name, value in (("was invoice", was_invoice), ("now invoice", now_invoice)):
        if not isinstance(value, Invoice):
            raise BadValueError(name, value, "want an invoice")
    lines = [
        FeeLine(
            code=AMEND_CODE,
            detail="amendment to an issued permit",
            amount=tariff.amendment_fee,
        )
    ]
    if not material:
        return Reprice(
            lines=tuple(lines), was_total=was_invoice.total, now_total=was_invoice.total
        )
    settle = _difference_line(was_invoice, now_invoice, tariff)
    if settle is not None:
        lines.append(settle)
    credit = day_credit(was, now, was_invoice.total)
    if int(credit) > 0 and settle is None:
        lines.append(
            FeeLine(
                code=CREDIT_CODE,
                detail=f"{was.span.days - now.span.days} days given back",
                amount=cents(-int(credit)),
            )
        )
    return Reprice(lines=tuple(lines), was_total=was_invoice.total, now_total=now_invoice.total)
