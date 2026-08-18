"""The sheet the clerk works off when chasing certificates.

Two lists on one sheet, and the order they come in is the whole point. What has
already lapsed goes first, because every one of those is a carrier that cannot be
issued anything this morning and will ring up about it. What is about to lapse
goes second, because that is next week's problem and nobody is standing at the
counter about it yet.

The gap list is separate again. A carrier can hold every cover the office asks
for and still be short, because the amounts went up in twenty twenty four and
nothing forced the old certificates to be replaced. Those carriers look fine on
the chase list and are not fine, which is the case this sheet was written for.
"""

from __future__ import annotations

from dataclasses import dataclass

from jeepdolly.party.surety import Certificate, lapsing
from jeepdolly.permit.application import Kind
from jeepdolly.permit.cover import gaps
from jeepdolly.report.layout import LEFT, RIGHT
from jeepdolly.report.sheet import Sheet
from jeepdolly.units.clock import Day, format_day, only_a_day
from jeepdolly.units.money import format_money

__all__ = ["CHASE_WITHIN", "Chase", "chases", "cover_sheet", "lapsed"]

#: How far ahead the office chases a certificate as a matter of course.
CHASE_WITHIN = 30


@dataclass(frozen=True, slots=True, order=True)
class Chase:
    """One certificate and how long it has left."""

    days_left: int
    carrier: str
    cover: str
    policy: str
    insurer: str
    last_day: Day

    @property
    def gone(self) -> bool:
        """Has it already lapsed."""
        return self.days_left < 1

    def __str__(self) -> str:
        if self.gone:
            return f"{self.carrier} {self.cover} lapsed {1 - self.days_left} days ago"
        return f"{self.carrier} {self.cover} has {self.days_left} days left"


def _chase(certificate: Certificate, on: Day) -> Chase:
    """One certificate's standing as at a day."""
    return Chase(
        days_left=certificate.days_left(on),
        carrier=str(certificate.carrier),
        cover=str(certificate.cover),
        policy=certificate.policy,
        insurer=certificate.insurer,
        last_day=certificate.span.last,
    )


def _day(on: Day) -> Day:
    """Refuse anything that is not a plain date."""
    only_a_day(on, "day")
    return on


def chases(held: list[Certificate], on: Day, within: int = CHASE_WITHIN) -> list[Chase]:
    """Every certificate still good that runs out inside the window."""
    return sorted(_chase(one, only_a_day(on)) for one in lapsing(held, on, within))


def lapsed(held: list[Certificate], on: Day) -> list[Chase]:
    """Every certificate on file that has already run out, longest gone first."""
    found = [_chase(one, only_a_day(on)) for one in held]
    return sorted(one for one in found if one.gone)


def cover_sheet(
    held: list[Certificate],
    on: Day,
    within: int = CHASE_WITHIN,
    against: Kind | None = None,
) -> list[str]:
    """The whole certificate chase list, ready to print.

    Passing ``against`` adds the shortfall section, which reads the amounts a
    permit of that sort would need. Leaving it out gives the plain calendar view
    the front counter uses.
    """
    soon = chases(held, on, within)
    gone = lapsed(held, on)
    sheet = Sheet().title(f"certificates as at {format_day(on)}")
    headings = ["carrier", "cover", "policy", "insurer", "last day", "days"]
    aligns = [LEFT, LEFT, LEFT, LEFT, LEFT, RIGHT]
    for name, batch in (("already lapsed", gone), ("running out", soon)):
        if not batch:
            continue
        sheet.section(name).rows(
            headings,
            [
                [
                    one.carrier,
                    one.cover,
                    one.policy,
                    one.insurer,
                    format_day(one.last_day),
                    str(one.days_left),
                ]
                for one in batch
            ],
            aligns=aligns,
        )
    short = gaps(held, against, on) if against is not None else []
    if short:
        sheet.section(f"short for a {against} permit").rows(
            ["cover", "needs", "short by"],
            [
                [
                    str(one.requirement.cover),
                    format_money(one.requirement.amount),
                    format_money(one.short),
                ]
                for one in short
            ],
            aligns=[LEFT, RIGHT, RIGHT],
        )
    if sheet.empty or (not soon and not gone and not short):
        return sheet.note("nothing to chase").done()
    return sheet.summary(
        [
            ("lapsed", str(len(gone))),
            ("running out", str(len(soon))),
            ("short on amount", str(len(short))),
        ]
    ).done()
