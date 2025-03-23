"""One pass over a rig and its load, producing everything that is wrong.

Nothing here decides anything. The assessment says what the rig is over and by
how much; whether that becomes a permit, a refusal or a trip to engineering is
the permit desk's problem and depends on things this layer does not know, like
whether the carrier's account is in good standing.

Order matters and is fixed: divisibility, tires, flat limits, bridge formula,
size. A clerk reads them in that order off the screen, the printed permit lists
them in that order, and a test that pins the order is pinning something the
office actually depends on.
"""

from __future__ import annotations

from dataclasses import dataclass

from jeepdolly.limits.bridge import check_bridge
from jeepdolly.limits.dimension import LEGAL, SizeRule, check_size
from jeepdolly.limits.finding import Finding, Severity, excess_of, worst
from jeepdolly.limits.statute import INTERSTATE, Statute, check_statute
from jeepdolly.rig.config import Configuration
from jeepdolly.rig.load import Load
from jeepdolly.units.mass import Pounds

__all__ = ["Assessment", "assess", "check_divisible", "check_tires"]


def check_divisible(load: Load) -> list[Finding]:
    """The one refusal that no route and no fee can get around."""
    reason = load.refusal()
    if not reason:
        return []
    return [
        Finding(
            rule="divisible",
            subject="the load",
            severity=Severity.REFUSE,
            detail=reason,
        )
    ]


def check_tires(config: Configuration) -> list[Finding]:
    """Every axle carrying more than its rubber is rated for."""
    findings: list[Finding] = []
    for index, axle in enumerate(config.axles):
        if not axle.over_tires:
            continue
        findings.append(
            Finding(
                rule="tire-width",
                subject=str(config.run(index, index)),
                severity=Severity.PERMIT,
                detail=(
                    f"{axle.tires} tires at {int(axle.tire_width)} inches"
                    f" carry {int(axle.tire_limit)} lb"
                ),
                excess=Pounds(int(axle.weight) - int(axle.tire_limit)),
            )
        )
    return findings


@dataclass(frozen=True, slots=True)
class Assessment:
    """Everything wrong with one rig and load on one road."""

    findings: tuple[Finding, ...]

    @property
    def severity(self) -> Severity:
        """The worst thing found."""
        return worst(self.findings)

    @property
    def clean(self) -> bool:
        """Is the rig legal as presented, with nothing to permit."""
        return all(f.severity is Severity.NOTE for f in self.findings)

    @property
    def blocked(self) -> bool:
        """Is there something no permit can fix."""
        return any(f.blocking for f in self.findings)

    @property
    def blockers(self) -> tuple[Finding, ...]:
        """The findings that stop a permit being written."""
        return tuple(f for f in self.findings if f.blocking)

    @property
    def excess(self) -> Pounds:
        """The largest single billable overage, which is what the fee uses."""
        return excess_of(self.findings)

    @property
    def rules(self) -> tuple[str, ...]:
        """The rule names in the order they were found."""
        return tuple(f.rule for f in self.findings)

    def by_rule(self, rule: str) -> tuple[Finding, ...]:
        """Just the findings from one check."""
        return tuple(f for f in self.findings if f.rule == rule)

    def __len__(self) -> int:
        return len(self.findings)


def assess(
    config: Configuration,
    load: Load,
    statute: Statute = INTERSTATE,
    size_rule: SizeRule = LEGAL,
) -> Assessment:
    """Run every check against a rig, in the office's reading order."""
    findings: list[Finding] = []
    findings.extend(check_divisible(load))
    findings.extend(check_tires(config))
    findings.extend(check_statute(config, statute))
    findings.extend(check_bridge(config, statute))
    findings.extend(check_size(load, size_rule))
    return Assessment(findings=tuple(findings))
