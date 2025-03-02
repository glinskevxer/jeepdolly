"""What is on the trailer.

The load carries its own dimensions rather than the trailer's, because the
permit is written about the widest and tallest point of the whole thing and that
is nearly always the load. Overhang is measured from the trailer deck, front and
rear, and adds to the overall length.

The one rule that lives here rather than in the limits is divisibility. A load
that can be taken apart and hauled in two trips does not get an overweight
permit at all, at any fee, and no route will save it. That is a property of the
cargo and not of the route, so it is checked as soon as the load is described.
"""

from __future__ import annotations

from dataclasses import dataclass

from jeepdolly.errors import BadValueError
from jeepdolly.units.length import NO_LENGTH, Inches, format_length, inches
from jeepdolly.units.mass import Pounds, format_weight, pounds

__all__ = ["MAX_DESCRIPTION", "NONDIVISIBLE_REASONS", "Load"]

#: The reasons the office will accept for calling a load nondivisible. A clerk
#: picks one off the list; free text was tried and produced "customer says so"
#: four hundred times.
NONDIVISIBLE_REASONS = (
    "single-piece",
    "would-destroy-value",
    "would-destroy-use",
    "emergency-response",
    "cannot-dismantle-in-eight-hours",
)

MAX_DESCRIPTION = 120


@dataclass(frozen=True, slots=True)
class Load:
    """The cargo, as described on the application.

    ``divisible`` is the honest state of the cargo. ``reason`` is only set when
    the load is nondivisible, and it must be one the office recognises. A
    divisible load carrying a reason is a contradiction and is refused, because
    it is how a clerk records a load they have not actually asked about.
    """

    description: str
    weight: Pounds
    width: Inches
    height: Inches
    length: Inches
    front_overhang: Inches = NO_LENGTH
    rear_overhang: Inches = NO_LENGTH
    divisible: bool = True
    reason: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.description, str) or not self.description.strip():
            raise BadValueError("description", self.description, "want some text")
        if len(self.description.strip()) > MAX_DESCRIPTION:
            raise BadValueError("description", self.description, f"over {MAX_DESCRIPTION}")
        object.__setattr__(self, "description", " ".join(self.description.split()))
        object.__setattr__(self, "weight", pounds(int(self.weight)))
        for name in ("width", "height", "length", "front_overhang", "rear_overhang"):
            object.__setattr__(self, name, inches(int(getattr(self, name))))
        for name in ("width", "height", "length"):
            if int(getattr(self, name)) < 1:
                raise BadValueError(name, getattr(self, name), "want at least one inch")
        if not isinstance(self.divisible, bool):
            raise BadValueError("divisible", self.divisible, "want true or false")
        if self.divisible and self.reason:
            raise BadValueError("reason", self.reason, "a divisible load has no reason")
        if not self.divisible and self.reason not in NONDIVISIBLE_REASONS:
            raise BadValueError("reason", self.reason, "not a reason the office accepts")

    @property
    def overall_length(self) -> Inches:
        """Deck length plus both overhangs."""
        return inches(int(self.length) + int(self.front_overhang) + int(self.rear_overhang))

    @property
    def overhang(self) -> Inches:
        """Front and rear overhang together."""
        return inches(int(self.front_overhang) + int(self.rear_overhang))

    @property
    def permittable_overweight(self) -> bool:
        """May this load be permitted above the statutory weight at all."""
        return not self.divisible

    def refusal(self) -> str:
        """Why an overweight permit cannot be written, or an empty string."""
        if self.divisible:
            return "the load is divisible and cannot be permitted overweight"
        return ""

    def __str__(self) -> str:
        return (
            f"{self.description}, {format_weight(self.weight)}, "
            f"{format_length(self.width)} wide by {format_length(self.height)} high"
        )
