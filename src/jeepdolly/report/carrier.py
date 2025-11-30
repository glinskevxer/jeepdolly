"""The carrier file: everything the office holds about one company, on one sheet.

This is what a clerk prints before a difficult phone call. It is not a new query,
it is the five existing ones laid out together, and that is the point: a carrier
asking why their permit was refused wants to hear about their account, their
rigs and their last three permits in one breath rather than in four.

Nothing here computes. Every number on the sheet is read from a store, and if a
number on this sheet disagrees with the same number elsewhere the sheet is wrong,
not the store.
"""

from __future__ import annotations

from dataclasses import dataclass

from jeepdolly.billing.account import Account
from jeepdolly.party.carrier import Carrier
from jeepdolly.permit.permit import Permit, State
from jeepdolly.report.layout import LEFT, RIGHT, banner, pairs, table
from jeepdolly.store.history import Event
from jeepdolly.store.rigs import FiledRig
from jeepdolly.units.clock import format_day
from jeepdolly.units.length import format_length
from jeepdolly.units.mass import format_weight
from jeepdolly.units.money import Money, format_money, total

__all__ = ["RECENT", "CarrierFile", "carrier_sheet"]

#: How many permits and journal entries the sheet shows.
RECENT = 8


@dataclass(frozen=True, slots=True)
class CarrierFile:
    """Everything the office holds about one carrier."""

    carrier: Carrier
    rigs: tuple[FiledRig, ...]
    permits: tuple[Permit, ...]
    account: Account
    events: tuple[Event, ...]

    @property
    def live_permits(self) -> tuple[Permit, ...]:
        """The permits the office still stands behind."""
        return tuple(p for p in self.permits if p.state is State.ACTIVE)

    @property
    def spent(self) -> Money:
        """What this carrier has been charged for permits that were not voided."""
        return total(p.fee for p in self.permits if p.state is not State.VOID)

    @property
    def voided(self) -> int:
        """How many of their permits were voided."""
        return sum(1 for p in self.permits if p.state is State.VOID)

    def __str__(self) -> str:
        return (
            f"{self.carrier.code}: {len(self.rigs)} rigs,"
            f" {len(self.permits)} permits, {format_money(self.account.balance)}"
        )


def carrier_sheet(file: CarrierFile) -> list[str]:
    """The whole carrier file, ready to print."""
    carrier = file.carrier
    lines = banner(f"carrier file {carrier.code}")
    lines.extend(
        pairs(
            [
                ("name", carrier.name),
                ("usdot", str(carrier.usdot)),
                ("home state", carrier.home_state),
                ("standing", "active" if carrier.active else "retired"),
                ("balance", format_money(file.account.balance)),
                ("headroom", format_money(file.account.headroom)),
            ]
        )
    )
    lines.append("")
    lines.extend(banner("rigs"))
    if not file.rigs:
        lines.append("none on file")
    else:
        lines.extend(
            table(
                ["reference", "name", "axles", "gross", "wheelbase"],
                [
                    [
                        str(one.reference),
                        str(one.config.name),
                        str(one.config.count),
                        format_weight(one.config.gross),
                        format_length(one.config.wheelbase),
                    ]
                    for one in file.rigs
                ],
                aligns=[LEFT, LEFT, RIGHT, RIGHT, RIGHT],
            )
        )
    lines.append("")
    lines.extend(banner("permits"))
    if not file.permits:
        lines.append("none issued")
    else:
        lines.extend(
            table(
                ["number", "good", "state", "fee"],
                [
                    [str(one.number), str(one.span), str(one.state), format_money(one.fee)]
                    for one in file.permits[-RECENT:]
                ],
                aligns=[LEFT, LEFT, LEFT, RIGHT],
            )
        )
        lines.append("")
        lines.extend(
            pairs(
                [
                    ("issued", str(len(file.permits))),
                    ("still live", str(len(file.live_permits))),
                    ("voided", str(file.voided)),
                    ("charged", format_money(file.spent)),
                ]
            )
        )
    if file.events:
        lines.append("")
        lines.extend(banner("recent activity"))
        lines.extend(
            table(
                ["day", "subject", "what", "detail"],
                [
                    [format_day(e.day), e.subject, str(e.kind), e.detail or "-"]
                    for e in file.events[-RECENT:]
                ],
            )
        )
    return lines
