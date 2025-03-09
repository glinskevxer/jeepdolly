"""One thing wrong with a rig, said once.

A finding is the unit the whole office works in. Every check produces findings,
never booleans, because "the rig is over" is useless at the counter and "axle 4
is 2,300 pounds over its 20,000 pound single axle limit" is a conversation the
clerk can have.

Findings carry the excess as a number so the fee schedule can bill from the same
object the clerk reads, and so nothing recomputes an overage from a printed
string.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from jeepdolly.errors import BadValueError
from jeepdolly.units.mass import NO_WEIGHT, Pounds, format_weight, pounds

__all__ = ["Finding", "Severity", "excess_of", "worst"]


class Severity(StrEnum):
    """How badly the office minds.

    ``REFUSE`` is not a big ``PERMIT``. It means no fee will fix it, which is
    what a divisible load or a bridge that cannot carry the axle group is. The
    difference matters because the fee schedule bills ``PERMIT`` findings and
    silently ignores ``REFUSE`` ones, and a check that picks the wrong severity
    produces a permit that should never have been sold.
    """

    NOTE = "note"
    PERMIT = "permit"
    REFUSE = "refuse"


_ORDER = {Severity.NOTE: 0, Severity.PERMIT: 1, Severity.REFUSE: 2}


@dataclass(frozen=True, slots=True)
class Finding:
    """A single check's answer about a single thing.

    ``subject`` names what was looked at in the words a clerk would use, like
    ``axle 4`` or ``axles 2-5``. ``rule`` names the check, so two findings from
    different rules about the same axle stay separate.
    """

    rule: str
    subject: str
    severity: Severity
    detail: str
    excess: Pounds = NO_WEIGHT

    def __post_init__(self) -> None:
        object.__setattr__(self, "severity", Severity(self.severity))
        object.__setattr__(self, "excess", pounds(int(self.excess)))
        for name in ("rule", "subject", "detail"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise BadValueError(name, value, "want some text")
            object.__setattr__(self, name, " ".join(value.split()))
        if self.severity is Severity.NOTE and int(self.excess) != 0:
            raise BadValueError("excess", int(self.excess), "a note carries no excess")

    @property
    def blocking(self) -> bool:
        """Does this finding stop a permit being written at any price."""
        return self.severity is Severity.REFUSE

    @property
    def billable(self) -> bool:
        """Does this finding put weight on the fee schedule."""
        return self.severity is Severity.PERMIT and int(self.excess) > 0

    def __str__(self) -> str:
        tail = f" by {format_weight(self.excess)}" if int(self.excess) else ""
        return f"{self.subject}: {self.detail}{tail}"


def worst(findings: Iterable[Finding]) -> Severity:
    """The highest severity in a batch, or ``NOTE`` for an empty one."""
    best = Severity.NOTE
    for finding in findings:
        if _ORDER[finding.severity] > _ORDER[best]:
            best = finding.severity
    return best


def excess_of(findings: Iterable[Finding]) -> Pounds:
    """The largest single billable excess in a batch.

    Overages do not add up. A rig that is three thousand over on one axle and
    five thousand over on the group containing it is billed once, at five
    thousand, because it is the same three thousand pounds being counted twice.
    """
    billable = [int(f.excess) for f in findings if f.billable]
    return pounds(max(billable) if billable else 0)
