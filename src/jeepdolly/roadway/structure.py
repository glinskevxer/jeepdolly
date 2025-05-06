"""Bridges, overheads, tunnels and the culverts that get forgotten.

A structure is the reason a route is refused rather than priced. A posted bridge
does not care what the permit fee is, and neither does a railroad overhead at
fifteen feet two.

Every structure carries at most two numbers that matter: a vertical clearance
and a load rating. Which of the two it carries depends on what it is, and the
type enforces that rather than leaving a bridge with a clearance of ``None``
meaning "unlimited" and an overhead with a rating of ``None`` meaning the same
thing in a different direction.

Clearance is stored as the posted figure, which is already the measured height
less the safety allowance the bridge crew works to. Nothing here subtracts a
second allowance.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from jeepdolly.errors import BadValueError
from jeepdolly.ids.reference import Code, Serial, code, serial
from jeepdolly.limits.finding import Finding, Severity
from jeepdolly.units.distance import Miles, hundredths
from jeepdolly.units.length import Inches, format_length, inches
from jeepdolly.units.mass import Pounds, format_weight, pounds

__all__ = ["CARRYING_KINDS", "OVERHEAD_KINDS", "Structure", "StructureKind"]


class StructureKind(StrEnum):
    """What sort of thing is in the way."""

    BRIDGE = "bridge"
    CULVERT = "culvert"
    OVERHEAD = "overhead"
    TUNNEL = "tunnel"


#: These limit how tall the load may be.
OVERHEAD_KINDS = frozenset({StructureKind.OVERHEAD, StructureKind.TUNNEL})

#: These carry the rig and limit how heavy it may be.
CARRYING_KINDS = frozenset({StructureKind.BRIDGE, StructureKind.CULVERT})


@dataclass(frozen=True, slots=True, order=True)
class Structure:
    """One thing on a segment that a load has to get past.

    A tunnel is both: it carries nothing and it limits height, so it sits in the
    overhead set. A bridge with a clearance beneath it is recorded twice, once
    as the bridge and once as the overhead, because the two have different
    inspection records and different owners.
    """

    reference: Serial
    segment: Code
    name: str
    kind: StructureKind
    milepost: Miles
    clearance: Inches | None = None
    rating: Pounds | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "reference", serial(str(self.reference)))
        object.__setattr__(self, "segment", code(str(self.segment)))
        object.__setattr__(self, "kind", StructureKind(self.kind))
        object.__setattr__(self, "milepost", hundredths(int(self.milepost)))
        if not isinstance(self.name, str) or not self.name.strip():
            raise BadValueError("name", self.name, "want some text")
        object.__setattr__(self, "name", " ".join(self.name.split()))
        if self.clearance is not None:
            object.__setattr__(self, "clearance", inches(int(self.clearance)))
            if int(self.clearance) < 1:
                raise BadValueError("clearance", self.clearance, "want at least one inch")
        if self.rating is not None:
            object.__setattr__(self, "rating", pounds(int(self.rating)))
            if int(self.rating) < 1:
                raise BadValueError("rating", self.rating, "want at least one pound")
        if self.kind in OVERHEAD_KINDS and self.clearance is None:
            raise BadValueError("clearance", self.kind, "an overhead has a posted clearance")
        if self.kind in OVERHEAD_KINDS and self.rating is not None:
            raise BadValueError("rating", self.kind, "an overhead carries nothing")
        if self.kind in CARRYING_KINDS and self.clearance is not None:
            raise BadValueError("clearance", self.kind, "a bridge is not an overhead")

    @property
    def limits_height(self) -> bool:
        """Does this structure cap how tall the load may be."""
        return self.clearance is not None

    @property
    def limits_weight(self) -> bool:
        """Does this structure cap how heavy the rig may be."""
        return self.rating is not None

    @property
    def unposted(self) -> bool:
        """A carrying structure with no rating, which the statute covers."""
        return self.kind in CARRYING_KINDS and self.rating is None

    def clears_height(self, height: Inches) -> bool:
        """Will a load of this height get under."""
        if self.clearance is None:
            return True
        return int(height) <= int(self.clearance)

    def carries(self, gross: Pounds) -> bool:
        """Will this structure take a rig of this gross weight."""
        if self.rating is None:
            return True
        return int(gross) <= int(self.rating)

    def check(self, height: Inches, gross: Pounds) -> list[Finding]:
        """What this structure has to say about one load."""
        found: list[Finding] = []
        if not self.clears_height(height):
            assert self.clearance is not None
            found.append(
                Finding(
                    rule="clearance",
                    subject=f"{self.reference} {self.name}",
                    severity=Severity.REFUSE,
                    detail=(
                        f"posted at {format_length(self.clearance)} and the load"
                        f" is {format_length(height)}"
                    ),
                )
            )
        if not self.carries(gross):
            assert self.rating is not None
            found.append(
                Finding(
                    rule="posted-bridge",
                    subject=f"{self.reference} {self.name}",
                    severity=Severity.REFUSE,
                    detail=(
                        f"rated at {format_weight(self.rating)} and the rig"
                        f" grosses {format_weight(gross)}"
                    ),
                )
            )
        return found

    def __str__(self) -> str:
        if self.clearance is not None:
            posted = f"clearance {format_length(self.clearance)}"
        elif self.rating is not None:
            posted = f"rated {format_weight(self.rating)}"
        else:
            posted = "unposted"
        return f"{self.reference} {self.name} on {self.segment}, {posted}"
