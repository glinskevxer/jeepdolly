"""What the office took, and where it came from.

The revenue return is the one report the office is audited on, so it is built
from the permits themselves rather than from the account entries. The two ought
to agree and when they do not the office wants to know, which is what
``reconcile`` is for.

Voided permits are excluded. A permit that was voided was refunded, and counting
it would overstate the take by exactly the amount that went back out. Superseded
permits are *included*, because the fee on a superseded permit was charged and
was not refunded; the amendment was charged separately.

The month key is a plain ``YYYY-MM`` string. It sorts correctly, it is what the
return is filed under, and it does not need a date library to produce.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from jeepdolly.billing.account import Account, EntryKind
from jeepdolly.permit.permit import Permit, State
from jeepdolly.report.layout import LEFT, RIGHT
from jeepdolly.report.sheet import Sheet
from jeepdolly.units.clock import Day, DaySpan
from jeepdolly.units.money import ZERO, Money, cents, format_money, total

__all__ = [
    "Take",
    "by_carrier",
    "by_code",
    "by_month",
    "counted",
    "month_of",
    "reconcile",
    "revenue_sheet",
    "within",
]


def month_of(day: Day) -> str:
    """The month a day falls in, as the return files it."""
    return f"{day.year:04d}-{day.month:02d}"


def counted(permits: list[Permit]) -> list[Permit]:
    """The permits that count toward the take, in number order.

    Voided permits are out. Everything else is in, superseded ones included.
    """
    return sorted(
        (p for p in permits if p.state is not State.VOID), key=lambda p: str(p.number)
    )


@dataclass(frozen=True, slots=True)
class Take:
    """One bucket of the return."""

    key: str
    permits: int
    amount: Money

    def __str__(self) -> str:
        return f"{self.key} {self.permits} permits {format_money(self.amount)}"


def _bucket(pairs_in: list[tuple[str, Money]]) -> list[Take]:
    """Roll a list of key and amount pairs up into sorted buckets."""
    counts: dict[str, int] = defaultdict(int)
    amounts: dict[str, list[Money]] = defaultdict(list)
    for key, amount in pairs_in:
        counts[key] += 1
        amounts[key].append(amount)
    return [
        Take(key=key, permits=counts[key], amount=total(amounts[key])) for key in sorted(counts)
    ]


def by_month(permits: list[Permit]) -> list[Take]:
    """The take by the month the permit was issued."""
    return _bucket([(month_of(p.issued_on), p.fee) for p in counted(permits)])


def by_carrier(permits: list[Permit]) -> list[Take]:
    """The take by carrier."""
    return _bucket([(p.carrier, p.fee) for p in counted(permits)])


def by_code(permits: list[Permit]) -> list[Take]:
    """The take by fee line code.

    The permit count in each bucket is the number of permits carrying that line,
    not the number of permits, so the counts do not add to the permit total and
    are not meant to.
    """
    pairs_in: list[tuple[str, Money]] = []
    for permit in counted(permits):
        invoice = permit.decision.invoice
        assert invoice is not None
        for line in invoice.lines:
            pairs_in.append((line.code, line.amount))
    return _bucket(pairs_in)


def within(permits: list[Permit], span: DaySpan) -> list[Permit]:
    """The permits issued inside a span of days."""
    return [p for p in permits if span.covers(p.issued_on)]


def reconcile(permits: list[Permit], account: Account) -> Money:
    """What the permits say the carrier owes less what the account charged.

    Zero means the two agree. A positive figure means permits were issued and
    never charged, which is the direction that costs the office money.
    """
    mine = [p for p in counted(permits) if p.carrier == str(account.carrier)]
    charged = total(e.amount for e in account.of_kind(EntryKind.CHARGE))
    return cents(int(total(p.fee for p in mine)) - int(charged))


def revenue_sheet(permits: list[Permit], span: DaySpan | None = None) -> list[str]:
    """The whole return, ready to print."""
    held = permits if span is None else within(permits, span)
    heading = "revenue return" if span is None else f"revenue return {span}"
    sheet = Sheet().title(heading)
    kept = counted(held)
    if not kept:
        return sheet.note("nothing to report").done()
    for title, buckets in (
        ("by month", by_month(held)),
        ("by carrier", by_carrier(held)),
        ("by fee line", by_code(held)),
    ):
        sheet.section(title).rows(
            ["key", "count", "amount"],
            [[t.key, str(t.permits), format_money(t.amount)] for t in buckets],
            aligns=[LEFT, RIGHT, RIGHT],
        )
    voided = [p for p in held if p.state is State.VOID]
    return sheet.summary(
        [
            ("permits counted", str(len(kept))),
            ("permits voided", str(len(voided))),
            ("total", format_money(total(p.fee for p in kept) if kept else ZERO)),
        ]
    ).done()
