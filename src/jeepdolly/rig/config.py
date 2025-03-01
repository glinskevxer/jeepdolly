"""The arrangement: which axles, in what order, how far apart.

The limits are not written about axles, they are written about *runs* of
consecutive axles and the distance from the first to the last of the run. So
the arrangement has to be able to hand out every such run cheaply, and it has to
measure the distance the same way every time.

Distance is measured centre to centre, first axle of the run to last. A single
axle is a run of length one and its extreme is zero inches, which is the answer
the bridge formula wants and is worth stating because zero looks like a bug.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from jeepdolly.errors import BadValueError
from jeepdolly.ids.reference import Code, code
from jeepdolly.rig.axle import Axle
from jeepdolly.units.length import Inches, format_length, inches
from jeepdolly.units.mass import Pounds, pounds

__all__ = ["MAX_AXLES", "MIN_AXLES", "MIN_SPACING", "Configuration", "Run"]

#: A tractor alone is two axles. Anything less is not a rig.
MIN_AXLES = 2

#: The longest thing the office has permitted ran twenty six axles.
MAX_AXLES = 40

#: Axles closer together than this are one axle with two sets of rubber, and the
#: office refuses the ticket rather than guessing which the carrier meant.
MIN_SPACING = inches(24)


@dataclass(frozen=True, slots=True, order=True)
class Run:
    """A consecutive stretch of axles, given as a half open index range.

    ``Run(0, 2)`` is the first two axles. The extreme and the weight are carried
    rather than recomputed, because the limits ask for both of every run and
    there are a lot of runs.
    """

    first: int
    last: int
    extreme: Inches
    weight: Pounds

    @property
    def count(self) -> int:
        """How many axles are in the run."""
        return self.last - self.first + 1

    @property
    def single(self) -> bool:
        """Is this a run of one axle."""
        return self.first == self.last

    def __str__(self) -> str:
        if self.single:
            return f"axle {self.first + 1}"
        return f"axles {self.first + 1}-{self.last + 1} over {format_length(self.extreme)}"


@dataclass(frozen=True, slots=True)
class Configuration:
    """A rig as presented at the counter.

    ``spacings[i]`` is the distance from axle ``i`` to axle ``i + 1``, so there
    is always exactly one fewer spacing than axle. The name is the carrier's
    shorthand for the arrangement, ``3S2`` or ``9-AXLE-DOUBLE-DROP``, and it is
    a label only. Nothing is derived from it, because carriers do not agree on
    what the shorthand means and the axles are right there.
    """

    name: Code
    axles: tuple[Axle, ...]
    spacings: tuple[Inches, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", code(str(self.name)))
        object.__setattr__(self, "axles", tuple(self.axles))
        object.__setattr__(self, "spacings", tuple(inches(int(s)) for s in self.spacings))
        count = len(self.axles)
        if count < MIN_AXLES:
            raise BadValueError("axles", count, f"want at least {MIN_AXLES}")
        if count > MAX_AXLES:
            raise BadValueError("axles", count, f"want at most {MAX_AXLES}")
        if len(self.spacings) != count - 1:
            raise BadValueError(
                "spacings", len(self.spacings), f"want {count - 1} for {count} axles"
            )
        for index, gap in enumerate(self.spacings):
            if int(gap) < int(MIN_SPACING):
                raise BadValueError(
                    "spacing",
                    format_length(gap),
                    f"axles {index + 1} and {index + 2} are too close",
                )
        if not self.axles[0].steering:
            raise BadValueError("axles", self.name, "the first axle is the steer axle")
        for axle in self.axles[1:]:
            if axle.steering:
                raise BadValueError("axles", self.name, "only the first axle steers")

    @property
    def count(self) -> int:
        """How many axles the rig has."""
        return len(self.axles)

    @property
    def gross(self) -> Pounds:
        """Everything the rig puts on the road."""
        return pounds(sum(int(a.weight) for a in self.axles))

    @property
    def wheelbase(self) -> Inches:
        """First axle to last, centre to centre."""
        return inches(sum(int(s) for s in self.spacings))

    def extreme(self, first: int, last: int) -> Inches:
        """Distance from axle ``first`` to axle ``last``, both inclusive."""
        self._check_range(first, last)
        return inches(sum(int(s) for s in self.spacings[first:last]))

    def weight_of(self, first: int, last: int) -> Pounds:
        """What axles ``first`` through ``last`` carry between them."""
        self._check_range(first, last)
        return pounds(sum(int(a.weight) for a in self.axles[first : last + 1]))

    def run(self, first: int, last: int) -> Run:
        """One run, with its extreme and weight already worked out."""
        return Run(
            first=first,
            last=last,
            extreme=self.extreme(first, last),
            weight=self.weight_of(first, last),
        )

    def runs(self) -> Iterator[Run]:
        """Every consecutive run of axles, shortest first, then left to right.

        For an n axle rig this yields n(n+1)/2 runs. That is quadratic and it is
        fine: the biggest rig the office permits has forty axles, which is eight
        hundred and twenty runs, and the limits have to look at all of them.
        """
        for length in range(1, self.count + 1):
            for first in range(self.count - length + 1):
                yield self.run(first, first + length - 1)

    def groups(self, within: Inches) -> Iterator[Run]:
        """Maximal runs whose neighbouring axles are all within a distance.

        This is how a tandem or a tridem is picked out of the rig. Neighbouring
        means each adjacent pair, not first to last, so four axles at four feet
        apart are one group of four and not two groups of two.
        """
        limit = int(within)
        first = 0
        for index, gap in enumerate(self.spacings):
            if int(gap) > limit:
                yield self.run(first, index)
                first = index + 1
        yield self.run(first, self.count - 1)

    def _check_range(self, first: int, last: int) -> None:
        if isinstance(first, bool) or isinstance(last, bool):
            raise BadValueError("axle index", (first, last), "want whole numbers")
        if not isinstance(first, int) or not isinstance(last, int):
            raise BadValueError("axle index", (first, last), "want whole numbers")
        if not 0 <= first < self.count or not 0 <= last < self.count:
            raise BadValueError("axle index", (first, last), f"the rig has {self.count} axles")
        if last < first:
            raise BadValueError("axle range", (first, last), "ends before it starts")

    def __str__(self) -> str:
        return f"{self.name} {self.count} axles over {format_length(self.wheelbase)}"
