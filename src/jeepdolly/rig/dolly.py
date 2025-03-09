"""Jeeps and boosters, the axle sets bolted on to spread gross weight.

A jeep goes between the tractor and the trailer. A booster goes on the back. Both
do the same job, which is to put more axles under the same load so that no single
axle and no group of axles is over its limit, and both cost the carrier money and
manoeuvring room, so nobody adds one for fun.

The office does not do statics. It takes the transfer the carrier declares,
checks it against what the dolly is rated for, removes it from the axles on the
load side of the hitch in proportion to what they are already carrying, and puts
it on the dolly axles evenly. That is a simplification and it is the one written
into the office manual, so a permit recalculated during an audit lands on the
same numbers as the permit that was issued.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from jeepdolly.errors import BadValueError
from jeepdolly.ids.reference import code
from jeepdolly.rig.axle import Axle
from jeepdolly.rig.config import MIN_SPACING, Configuration
from jeepdolly.units.length import Inches, inches
from jeepdolly.units.mass import Pounds, pounds
from jeepdolly.units.share import divide_by_weight, divide_evenly

__all__ = ["Dolly", "Hitch", "attach"]


class Hitch(StrEnum):
    """Which end of the rig the dolly bolts to."""

    JEEP = "jeep"
    BOOSTER = "booster"


@dataclass(frozen=True, slots=True)
class Dolly:
    """An axle set that can be added to a rig.

    ``axles`` carry the dolly's own tare weight as presented. Whatever transfer
    is put on it is added to that, so a two axle jeep weighing six thousand
    pounds empty and taking twenty thousand pounds of transfer ends up carrying
    twenty six thousand across its axles.
    """

    kind: Hitch
    axles: tuple[Axle, ...]
    spacings: tuple[Inches, ...]
    hitch: Inches
    capacity: Pounds

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", Hitch(self.kind))
        object.__setattr__(self, "axles", tuple(self.axles))
        object.__setattr__(self, "spacings", tuple(inches(int(s)) for s in self.spacings))
        object.__setattr__(self, "hitch", inches(int(self.hitch)))
        object.__setattr__(self, "capacity", pounds(int(self.capacity)))
        if not self.axles:
            raise BadValueError("dolly", self.kind, "wants at least one axle")
        if len(self.spacings) != len(self.axles) - 1:
            raise BadValueError("spacings", len(self.spacings), f"want {len(self.axles) - 1}")
        for gap in (*self.spacings, self.hitch):
            if int(gap) < int(MIN_SPACING):
                raise BadValueError("spacing", int(gap), "too close to the next axle")
        for axle in self.axles:
            if axle.steering:
                raise BadValueError("dolly", self.kind, "a dolly axle does not steer")

    @property
    def count(self) -> int:
        """How many axles the dolly adds."""
        return len(self.axles)

    @property
    def tare(self) -> Pounds:
        """What the dolly weighs before anything is put on it."""
        return pounds(sum(int(a.weight) for a in self.axles))

    @property
    def length(self) -> Inches:
        """First dolly axle to last."""
        return inches(sum(int(s) for s in self.spacings))


def _donors(config: Configuration, kind: Hitch, at: int) -> list[int]:
    """The axle positions that give up weight to the dolly.

    For a jeep that is everything behind the hitch, which is the trailer. For a
    booster it is everything ahead of the hitch except the steer axle, which is
    never relieved because relieving it is how a rig loses its steering.
    """
    if kind is Hitch.JEEP:
        return list(range(at + 1, config.count))
    return [i for i in range(at + 1) if not config.axles[i].steering]


def attach(config: Configuration, dolly: Dolly, at: int, transfer: Pounds) -> Configuration:
    """Put a dolly on a rig and move some weight onto it.

    ``at`` is the axle the dolly is hitched behind, so a jeep on a five axle rig
    behind the drives is ``at=2``. A booster on the same rig is ``at=4``.
    """
    if isinstance(at, bool) or not isinstance(at, int):
        raise BadValueError("hitch point", at, "want a whole number")
    if not 0 <= at < config.count:
        raise BadValueError("hitch point", at, f"the rig has {config.count} axles")
    moved = pounds(int(transfer))
    if int(moved) > int(dolly.capacity):
        raise BadValueError("transfer", int(moved), f"over the {int(dolly.capacity)} rating")
    if dolly.kind is Hitch.BOOSTER and at != config.count - 1:
        raise BadValueError("hitch point", at, "a booster goes on the back")

    donors = _donors(config, dolly.kind, at)
    if not donors:
        raise BadValueError("hitch point", at, "nothing on that side to relieve")
    available = sum(int(config.axles[i].weight) for i in donors)
    if int(moved) > available:
        raise BadValueError("transfer", int(moved), f"only {available} on that side")

    taken = divide_by_weight(int(moved), [int(config.axles[i].weight) for i in donors])
    relieved = list(config.axles)
    for position, amount in zip(donors, taken, strict=True):
        axle = relieved[position]
        relieved[position] = axle.reloaded(pounds(int(axle.weight) - amount))

    added = divide_evenly(int(moved), dolly.count)
    carried = [
        axle.reloaded(pounds(int(axle.weight) + amount))
        for axle, amount in zip(dolly.axles, added, strict=True)
    ]

    axles = relieved[: at + 1] + carried + relieved[at + 1 :]
    spacings = (
        list(config.spacings[:at])
        + [dolly.hitch]
        + list(dolly.spacings)
        + ([dolly.hitch] if at + 1 < config.count else [])
        + list(config.spacings[at + 1 :])
    )
    suffix = "J" if dolly.kind is Hitch.JEEP else "B"
    name = code(f"{str(config.name)[:14]}-{suffix}")
    return Configuration(name=name, axles=tuple(axles), spacings=tuple(spacings))
