"""The bridge formula.

    W = 500 * ( L*N / (N - 1) + 12N + 36 )

``L`` is the distance in feet between the first and last axle of a group and
``N`` is how many axles are in it. The formula asks how much weight a group may
put on a span given how far it spreads that weight, and it is the reason a rig
that clears every flat limit can still be refused.

Three details decide whether an implementation agrees with the published table.

* ``L`` is whole feet, rounded **up**. Twelve foot three inches is thirteen.
* ``W`` is rounded to the nearest five hundred pounds, halves going up.
* The result is capped at the road's gross limit, because the formula keeps
  climbing with length and the gross limit does not.

There is one exception, and it is not a rounding detail. Two consecutive sets of
tandem axles may carry thirty four thousand pounds each even where the formula
says less, as long as the first and last axle of the four are thirty six feet
apart or more. Without it a standard five axle tractor trailer at the legal
eighty thousand pounds fails the formula, which is not the law's intent.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from fractions import Fraction

from jeepdolly.errors import BadValueError
from jeepdolly.limits.finding import Finding, Severity
from jeepdolly.limits.statute import Statute
from jeepdolly.rig.config import Configuration, Run
from jeepdolly.units.length import Inches, feet
from jeepdolly.units.mass import Pounds, format_weight, pounds

__all__ = [
    "STEP",
    "TANDEM_EXCEPTION_SPREAD",
    "TANDEM_EXCEPTION_WEIGHT",
    "BridgeCase",
    "bridge_cases",
    "bridge_limit",
    "check_bridge",
    "formula_weight",
    "round_to_step",
    "tandem_exception",
    "whole_feet",
]

#: The formula's answer is reported to the nearest five hundred pounds.
STEP = 500

#: The exception needs the outer axles this far apart.
TANDEM_EXCEPTION_SPREAD = feet(36)

#: What each of the two tandems may carry under the exception.
TANDEM_EXCEPTION_WEIGHT = pounds(34_000)


def whole_feet(length: Inches) -> int:
    """Inches as whole feet, rounded up, which is what the statute says."""
    value = int(length)
    if value < 0:
        raise BadValueError("length", value, "negative")
    return -(-value // 12)


def round_to_step(weight: int) -> Pounds:
    """Round to the nearest five hundred pounds, halves going up."""
    if isinstance(weight, bool) or not isinstance(weight, int):
        raise BadValueError("weight", weight, "want a whole number")
    if weight < 0:
        raise BadValueError("weight", weight, "negative")
    return pounds((weight + STEP // 2) // STEP * STEP)


def formula_weight(length: Inches, axles: int) -> Pounds:
    """The raw formula answer for a group, before any cap.

    A group of one axle has no answer; the formula divides by ``N - 1``. The
    single axle limit covers that case and this raises rather than returning
    something that looks like a limit.
    """
    if isinstance(axles, bool) or not isinstance(axles, int):
        raise BadValueError("axles", axles, "want a whole number")
    if axles < 2:
        raise BadValueError("axles", axles, "the formula needs at least two axles")
    span = whole_feet(length)
    exact = Fraction(span * axles, axles - 1) + 12 * axles + 36
    return round_to_step(int(500 * exact))


@dataclass(frozen=True, slots=True)
class BridgeCase:
    """One group weighed against the formula, with the working shown.

    The office prints these on the back of a refusal, because a carrier who is
    told only that the group is over will be back at the counter tomorrow with
    the same rig.
    """

    run: Run
    span_feet: int
    formula: Pounds
    limit: Pounds
    excepted: bool

    @property
    def over(self) -> Pounds:
        """How far over the limit the group is, or zero."""
        excess = int(self.run.weight) - int(self.limit)
        return pounds(max(0, excess))


def tandem_exception(config: Configuration, run: Run, statute: Statute) -> bool:
    """Does the four axle tandem pair exception apply to this run.

    The run has to be exactly four axles, the outer two have to be at least
    thirty six feet apart, and the run has to split into two tandems by this
    road's own bracket. Reusing the road's bracket rather than a fixed spacing
    is deliberate: a road that calls a wider pair a tandem also lets that pair
    take the exception.
    """
    if run.count != 4:
        return False
    if int(run.extreme) < int(TANDEM_EXCEPTION_SPREAD):
        return False
    front = config.run(run.first, run.first + 1)
    back = config.run(run.last - 1, run.last)
    return statute.is_tandem(front) and statute.is_tandem(back)


def bridge_limit(config: Configuration, run: Run, statute: Statute) -> BridgeCase:
    """What this group may carry on this road, and why."""
    if run.single:
        raise BadValueError("run", str(run), "a single axle has no bridge limit")
    raw = formula_weight(run.extreme, run.count)
    excepted = tandem_exception(config, run, statute)
    allowed = int(raw)
    if excepted:
        allowed = max(allowed, 2 * int(TANDEM_EXCEPTION_WEIGHT))
    allowed = min(allowed, int(statute.gross))
    return BridgeCase(
        run=run,
        span_feet=whole_feet(run.extreme),
        formula=raw,
        limit=pounds(allowed),
        excepted=excepted,
    )


def bridge_cases(config: Configuration, statute: Statute) -> Iterator[BridgeCase]:
    """Every multi axle group weighed against the formula."""
    for run in config.runs():
        if not run.single:
            yield bridge_limit(config, run, statute)


def check_bridge(config: Configuration, statute: Statute) -> list[Finding]:
    """Every group the formula says is too heavy, one finding each."""
    findings: list[Finding] = []
    for case in bridge_cases(config, statute):
        if int(case.over) == 0:
            continue
        tail = " with the tandem exception" if case.excepted else ""
        findings.append(
            Finding(
                rule="bridge-formula",
                subject=str(case.run),
                severity=Severity.PERMIT,
                detail=(
                    f"the formula allows {format_weight(case.limit)}"
                    f" over {case.span_feet} feet{tail}"
                ),
                excess=case.over,
            )
        )
    return findings
