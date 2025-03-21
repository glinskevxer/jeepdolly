"""The size limits, which are a different animal from the weight limits.

Weight is a number the road either can or cannot carry. Size is a question about
what the load will hit. That difference shows up in the severities: almost any
weight overage can be sold a permit, and a height overage past the lowest
structure on the route cannot be, at any price.

The office keeps two ceilings for each dimension. The first is where a permit
starts being needed. The second is where the permit stops being routine and the
application goes to engineering review instead of over the counter.
"""

from __future__ import annotations

from dataclasses import dataclass

from jeepdolly.errors import BadValueError
from jeepdolly.limits.finding import Finding, Severity
from jeepdolly.rig.load import Load
from jeepdolly.units.length import Inches, feet, feet_inches, format_length, inches

__all__ = ["FLAG_OVERHANG", "LEGAL", "SizeRule", "check_size", "needs_flags"]

#: Rear overhang past this needs red flags by day and lamps by night.
FLAG_OVERHANG = feet(4)


@dataclass(frozen=True, slots=True)
class SizeRule:
    """One road's size limits and the point where review takes over."""

    name: str
    width: Inches
    height: Inches
    length: Inches
    front_overhang: Inches
    rear_overhang: Inches
    review_width: Inches
    review_height: Inches
    review_length: Inches

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise BadValueError("name", self.name, "want some text")
        for field in (
            "width",
            "height",
            "length",
            "front_overhang",
            "rear_overhang",
            "review_width",
            "review_height",
            "review_length",
        ):
            object.__setattr__(self, field, inches(int(getattr(self, field))))
        for plain, review in (
            ("width", "review_width"),
            ("height", "review_height"),
            ("length", "review_length"),
        ):
            if int(getattr(self, review)) <= int(getattr(self, plain)):
                raise BadValueError(
                    review, int(getattr(self, review)), "not above the plain limit"
                )


#: What may run without a permit at all, and where review starts.
LEGAL = SizeRule(
    name="legal",
    width=feet_inches(8, 6),
    height=feet_inches(13, 6),
    length=feet(75),
    front_overhang=feet(3),
    rear_overhang=feet(4),
    review_width=feet(16),
    review_height=feet_inches(16, 0),
    review_length=feet(120),
)


def needs_flags(load: Load) -> bool:
    """Does the rear overhang need flags and lamps."""
    return int(load.rear_overhang) > int(FLAG_OVERHANG)


def _over(
    rule_name: str,
    subject: str,
    value: Inches,
    limit: Inches,
    review: Inches,
    what: str,
) -> Finding | None:
    """One dimension weighed against its two ceilings."""
    if int(value) <= int(limit):
        return None
    if int(value) > int(review):
        return Finding(
            rule=rule_name,
            subject=subject,
            severity=Severity.REFUSE,
            detail=(
                f"{what} {format_length(value)} is past {format_length(review)}"
                " and goes to engineering review"
            ),
        )
    return Finding(
        rule=rule_name,
        subject=subject,
        severity=Severity.PERMIT,
        detail=f"{what} {format_length(value)} is over {format_length(limit)}",
    )


def check_size(load: Load, rule: SizeRule = LEGAL) -> list[Finding]:
    """Every size limit this load is over, one finding each."""
    findings: list[Finding] = []
    checks = (
        ("over-width", "the load", load.width, rule.width, rule.review_width, "width"),
        ("over-height", "the load", load.height, rule.height, rule.review_height, "height"),
        (
            "over-length",
            "the rig",
            load.overall_length,
            rule.length,
            rule.review_length,
            "overall length",
        ),
    )
    for rule_name, subject, value, limit, review, what in checks:
        found = _over(rule_name, subject, value, limit, review, what)
        if found is not None:
            findings.append(found)
    if int(load.front_overhang) > int(rule.front_overhang):
        findings.append(
            Finding(
                rule="front-overhang",
                subject="the front",
                severity=Severity.PERMIT,
                detail=(
                    f"front overhang {format_length(load.front_overhang)}"
                    f" is over {format_length(rule.front_overhang)}"
                ),
            )
        )
    if int(load.rear_overhang) > int(rule.rear_overhang):
        findings.append(
            Finding(
                rule="rear-overhang",
                subject="the rear",
                severity=Severity.PERMIT,
                detail=(
                    f"rear overhang {format_length(load.rear_overhang)}"
                    f" is over {format_length(rule.rear_overhang)}"
                ),
            )
        )
    if needs_flags(load):
        findings.append(
            Finding(
                rule="flags",
                subject="the rear",
                severity=Severity.NOTE,
                detail="red flags by day and lamps by night on the overhang",
            )
        )
    return findings
