"""The flat statutory limits.

Three numbers do most of the work: twenty thousand on a single axle, thirty four
thousand on a tandem, eighty thousand gross. They are flat, they do not depend
on spacing beyond deciding what counts as a tandem, and a rig that clears all
three still has the bridge formula to get past.

The numbers are held in a value rather than as module constants because they are
not the same on every road. The interstate set is federal and fixed. A state
route set is the office's own, and a handful of routes carry a lower gross by
local order, so the limits have to be something a route can hand over.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from jeepdolly.errors import BadValueError
from jeepdolly.limits.finding import Finding, Severity
from jeepdolly.rig.config import Configuration, Run
from jeepdolly.units.length import Inches, inches
from jeepdolly.units.mass import Pounds, format_weight, pounds

__all__ = ["INTERSTATE", "STATE_ROUTE", "Statute", "check_statute", "tandem_runs"]


@dataclass(frozen=True, slots=True)
class Statute:
    """One road's flat limits.

    ``tandem_low`` and ``tandem_high`` bracket the spacing that makes two axles
    a tandem. Below the low figure they are treated as a single axle with two
    sets of rubber, which is much worse for the carrier. Above the high figure
    they are two separate single axles, which is much better. Carriers know
    this, and the bracket is the reason a trailer's axle spread is adjustable.
    """

    name: str
    single: Pounds
    tandem: Pounds
    gross: Pounds
    tandem_low: Inches
    tandem_high: Inches

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise BadValueError("name", self.name, "want some text")
        for field in ("single", "tandem", "gross"):
            object.__setattr__(self, field, pounds(int(getattr(self, field))))
        for field in ("tandem_low", "tandem_high"):
            object.__setattr__(self, field, inches(int(getattr(self, field))))
        if int(self.tandem) < int(self.single):
            raise BadValueError("tandem", int(self.tandem), "below the single axle limit")
        if int(self.gross) < int(self.tandem):
            raise BadValueError("gross", int(self.gross), "below the tandem limit")
        if int(self.tandem_high) <= int(self.tandem_low):
            raise BadValueError("tandem_high", int(self.tandem_high), "not above the low end")

    def is_tandem(self, run: Run) -> bool:
        """Do these two axles count as a tandem on this road."""
        if run.count != 2:
            return False
        return int(self.tandem_low) <= int(run.extreme) <= int(self.tandem_high)

    def flat_limit(self, run: Run) -> Pounds | None:
        """The flat limit for a run, or ``None`` if no flat limit applies.

        Only singles and tandems have one. Everything wider is the bridge
        formula's business, and returning ``None`` rather than the gross limit
        keeps the two rules from quietly agreeing on a wrong answer.
        """
        if run.single:
            return self.single
        if self.is_tandem(run):
            return self.tandem
        return None


#: The federal numbers, which apply on the interstate system.
INTERSTATE = Statute(
    name="interstate",
    single=pounds(20_000),
    tandem=pounds(34_000),
    gross=pounds(80_000),
    tandem_low=inches(40),
    tandem_high=inches(96),
)

#: The office's own numbers for state routes, which run a little heavier on the
#: single axle and a little lighter overall.
STATE_ROUTE = Statute(
    name="state route",
    single=pounds(21_500),
    tandem=pounds(34_000),
    gross=pounds(80_000),
    tandem_low=inches(40),
    tandem_high=inches(108),
)


def tandem_runs(config: Configuration, statute: Statute) -> Iterator[Run]:
    """Every pair of axles this road would call a tandem."""
    for run in config.runs():
        if statute.is_tandem(run):
            yield run


def check_statute(config: Configuration, statute: Statute) -> list[Finding]:
    """Every flat limit this rig is over, one finding each.

    Singles first, then tandems, then the gross, which is the order a clerk
    reads them off and the order the fee schedule wants them in.
    """
    findings: list[Finding] = []
    for index, axle in enumerate(config.axles):
        run = config.run(index, index)
        limit = statute.single
        if int(axle.weight) > int(limit):
            findings.append(
                Finding(
                    rule="single-axle",
                    subject=str(run),
                    severity=Severity.PERMIT,
                    detail=f"over the {format_weight(limit)} single axle limit",
                    excess=pounds(int(axle.weight) - int(limit)),
                )
            )
    for run in tandem_runs(config, statute):
        if int(run.weight) > int(statute.tandem):
            findings.append(
                Finding(
                    rule="tandem",
                    subject=str(run),
                    severity=Severity.PERMIT,
                    detail=f"over the {format_weight(statute.tandem)} tandem limit",
                    excess=pounds(int(run.weight) - int(statute.tandem)),
                )
            )
    if int(config.gross) > int(statute.gross):
        findings.append(
            Finding(
                rule="gross",
                subject="the rig",
                severity=Severity.PERMIT,
                detail=f"over the {format_weight(statute.gross)} gross limit",
                excess=pounds(int(config.gross) - int(statute.gross)),
            )
        )
    return findings
