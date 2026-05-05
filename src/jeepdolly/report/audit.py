"""Checking the office's three records of the same money against each other.

A permit says what it was charged. An account says what was charged to it. The
journal says a charge happened. Those are three separate writes and they can
disagree in three interesting ways.

* A permit was issued and never charged. The office is out of pocket and nothing
  in the day to day work would ever notice.
* An account was charged for a permit that does not exist. Usually a typo in a
  permit number, which means some other permit is uncharged too.
* A permit was voided, refunded on the account, and the journal has no line
  saying so. That one is only a paperwork gap, but it is the gap an auditor asks
  about.

None of these is fixed here. The audit reports and the clerk decides, because
every automatic fix for these is worse than the problem.
"""

from __future__ import annotations

from dataclasses import dataclass

from jeepdolly.billing.account import Account, EntryKind
from jeepdolly.permit.permit import Permit, State
from jeepdolly.report.layout import LEFT, RIGHT
from jeepdolly.report.sheet import Sheet
from jeepdolly.store.history import Event, EventKind
from jeepdolly.units.money import ZERO, Money, cents, format_money, total

__all__ = ["Audit", "Finding", "audit", "audit_sheet"]


@dataclass(frozen=True, slots=True, order=True)
class Finding:
    """One thing the three records disagree about."""

    subject: str
    problem: str
    amount: Money = ZERO

    def __str__(self) -> str:
        tail = f" {format_money(self.amount)}" if int(self.amount) else ""
        return f"{self.subject}: {self.problem}{tail}"


@dataclass(frozen=True, slots=True)
class Audit:
    """The result of checking one carrier's permits against their account."""

    carrier: str
    findings: tuple[Finding, ...]
    charged: Money
    owed: Money

    @property
    def clean(self) -> bool:
        """Do the three records agree."""
        return not self.findings

    @property
    def gap(self) -> Money:
        """What the permits say less what the account charged."""
        return cents(int(self.owed) - int(self.charged))

    def __str__(self) -> str:
        if self.clean:
            return f"{self.carrier}: the records agree"
        return f"{self.carrier}: {len(self.findings)} problems, {format_money(self.gap)} apart"


def _charge_references(account: Account) -> dict[str, Money]:
    """What the account was charged, by the permit number it names."""
    out: dict[str, Money] = {}
    for entry in account.of_kind(EntryKind.CHARGE):
        out[entry.reference] = cents(
            int(out.get(entry.reference, cents(0))) + int(entry.amount)
        )
    return out


def _refund_references(account: Account) -> set[str]:
    """The permit numbers the account has refunded."""
    return {entry.reference for entry in account.of_kind(EntryKind.REFUND) if entry.reference}


def audit(carrier: str, permits: list[Permit], account: Account, journal: list[Event]) -> Audit:
    """Check one carrier's permits, account and journal against each other."""
    mine = [p for p in permits if p.carrier == carrier]
    charges = _charge_references(account)
    refunds = _refund_references(account)
    logged = {e.subject for e in journal if e.kind is EventKind.VOIDED}
    numbers = {str(p.number) for p in mine}
    findings: list[Finding] = []

    for permit in sorted(mine, key=lambda p: str(p.number)):
        number = str(permit.number)
        if permit.state is State.VOID:
            if number not in refunds and number in charges:
                findings.append(Finding(number, "voided and not refunded", permit.fee))
            if number not in logged:
                findings.append(Finding(number, "voided with no journal line"))
            continue
        if number not in charges:
            findings.append(Finding(number, "issued and never charged", permit.fee))
        elif int(charges[number]) != int(permit.fee):
            findings.append(
                Finding(
                    number,
                    f"charged {format_money(charges[number])} against a fee of",
                    permit.fee,
                )
            )

    for number in sorted(set(charges) - numbers):
        findings.append(
            Finding(number, "charged against no permit of this carrier", charges[number])
        )

    owed = total(p.fee for p in mine if p.state is not State.VOID)
    charged = total(charges.values())
    return Audit(carrier=carrier, findings=tuple(findings), charged=charged, owed=owed)


def audit_sheet(results: list[Audit]) -> list[str]:
    """The whole audit, ready to print."""
    sheet = Sheet().title("account audit")
    if not results:
        return sheet.note("no carriers on file").done()
    dirty = [one for one in results if not one.clean]
    sheet.rows(
        ["carrier", "permits owe", "account charged", "apart", "problems"],
        [
            [
                one.carrier,
                format_money(one.owed),
                format_money(one.charged),
                format_money(one.gap),
                str(len(one.findings)),
            ]
            for one in results
        ],
        aligns=[LEFT, RIGHT, RIGHT, RIGHT, RIGHT],
    )
    for one in dirty:
        sheet.section(f"{one.carrier} problems").notes(
            f"- {finding}" for finding in one.findings
        )
    return sheet.summary(
        [
            ("carriers", str(len(results))),
            ("clean", str(len(results) - len(dirty))),
            ("apart", format_money(total(one.gap for one in results))),
        ]
    ).done()
