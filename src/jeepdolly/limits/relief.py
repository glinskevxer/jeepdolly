"""What would have to change to get a rig under the limits.

The assessment says what is wrong. This says what to do about it, in the words a
clerk uses at the counter: shed so many pounds off axle four, spread the trailer
tandem past eight feet, put another axle under it.

Every remedy is worked out from the same numbers the finding carries, so a
remedy that says "shed two thousand three hundred pounds" is the finding's own
excess and not a second opinion. That matters because the carrier will do exactly
what the ticket says and then come back, and the office has to be right the first
time.

Remedies are not ranked and are not a plan. Two of them may be the same three
thousand pounds seen from different angles, which is why they name the axle or
the group they came from rather than adding up.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from jeepdolly.errors import BadValueError
from jeepdolly.limits.assess import Assessment
from jeepdolly.limits.finding import Finding, Severity
from jeepdolly.limits.statute import Statute
from jeepdolly.units.length import NO_LENGTH, Inches, format_length
from jeepdolly.units.mass import NO_WEIGHT, Pounds, format_weight

__all__ = ["SPREADABLE", "Kind", "Remedy", "remedies_for", "remedy_of"]

#: The rules another axle or a wider spread can do something about.
SPREADABLE = frozenset({"single-axle", "tandem", "bridge-formula", "tire-width"})


class Kind(StrEnum):
    """What sort of thing the carrier has to do."""

    SHED = "shed weight"
    SPREAD = "spread the axles"
    RUBBER = "put wider rubber on"
    DISMANTLE = "take the load apart"
    REROUTE = "go another way"
    REVIEW = "take it to engineering"
    NOTHING = "nothing will fix this"


@dataclass(frozen=True, slots=True, order=True)
class Remedy:
    """One thing the carrier could do, and how much of it."""

    kind: Kind
    subject: str
    detail: str
    weight: Pounds = NO_WEIGHT
    length: Inches = NO_LENGTH

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", Kind(self.kind))
        for name in ("subject", "detail"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise BadValueError(name, value, "want some text")
            object.__setattr__(self, name, " ".join(value.split()))

    def __str__(self) -> str:
        return f"{self.subject}: {self.detail}"


def remedy_of(finding: Finding, statute: Statute) -> Remedy:
    """The one thing that would clear a single finding."""
    excess = finding.excess
    if finding.rule == "single-axle":
        return Remedy(
            kind=Kind.SHED,
            subject=finding.subject,
            detail=(
                f"shed {format_weight(excess)}, or put it on a dolly, to get under"
                f" {format_weight(statute.single)}"
            ),
            weight=excess,
        )
    if finding.rule == "tandem":
        return Remedy(
            kind=Kind.SPREAD,
            subject=finding.subject,
            detail=(
                f"shed {format_weight(excess)} or spread the pair past"
                f" {format_length(statute.tandem_high)} so it stops being a tandem"
            ),
            weight=excess,
            length=statute.tandem_high,
        )
    if finding.rule == "bridge-formula":
        return Remedy(
            kind=Kind.SPREAD,
            subject=finding.subject,
            detail=(
                f"shed {format_weight(excess)}, spread the group, or put another axle under it"
            ),
            weight=excess,
        )
    if finding.rule == "tire-width":
        return Remedy(
            kind=Kind.RUBBER,
            subject=finding.subject,
            detail=f"wider tires or more of them, {format_weight(excess)} over the rubber",
            weight=excess,
        )
    if finding.rule == "divisible":
        return Remedy(
            kind=Kind.DISMANTLE,
            subject=finding.subject,
            detail="split the load and haul it in two trips, or it cannot be permitted",
        )
    if finding.rule in {"clearance", "posted-bridge", "local-order"}:
        return Remedy(
            kind=Kind.REROUTE,
            subject=finding.subject,
            detail="this stretch will not take it, so the run has to go another way",
        )
    if finding.rule in {"over-width", "over-height", "over-length"}:
        if finding.severity is Severity.REFUSE:
            return Remedy(
                kind=Kind.REVIEW,
                subject=finding.subject,
                detail="past what a clerk may write, so it goes to engineering",
            )
        return Remedy(
            kind=Kind.NOTHING,
            subject=finding.subject,
            detail="over size, which the permit covers and the fee reflects",
        )
    return Remedy(
        kind=Kind.NOTHING,
        subject=finding.subject,
        detail=finding.detail,
    )


def remedies_for(seen: Assessment, statute: Statute) -> list[Remedy]:
    """One remedy per finding, in the order the findings came out.

    Notes are left out. A note is something the driver has to do rather than
    something the rig has to change, and the permit already prints it.
    """
    return [
        remedy_of(finding, statute)
        for finding in seen.findings
        if finding.severity is not Severity.NOTE
    ]
