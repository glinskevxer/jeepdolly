"""Finding the same move filed twice.

It happens most weeks. A dispatcher rings the office and then emails the office,
and two clerks take the same application forty minutes apart. Neither of them
sees the other one. The carrier gets two permits, pays twice, and rings up in
three weeks about it.

What makes it hard is that the two applications are almost never identical. The
second one is filed on a different day, the load weight is rounded differently,
and one of them has the origin typed as the yard and the other as the junction
next to the yard. So this does not look for equality. It scores.

Three degrees, and which fields count depends on the sort of permit. A trip
permit is the same move if the carrier, the rig, the route and the days line up.
An annual has no route at all, so the route can never match and demanding it
would mean no annual is ever a duplicate of anything. That is the rule that
matters here: the *kind* decides what the other rules are allowed to look at.

Nothing here refuses anything. It hands back what it found and the desk decides,
because a carrier genuinely does sometimes move two identical transformers to
the same substation in the same week.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from jeepdolly.errors import BadValueError
from jeepdolly.permit.application import Application, Kind
from jeepdolly.units.length import Inches
from jeepdolly.units.mass import Pounds

__all__ = [
    "HEIGHT_SLACK",
    "WEIGHT_SLACK",
    "Likeness",
    "Match",
    "duplicates_of",
    "likeness",
]

#: Two loads within this of each other are the same load as far as this is
#: concerned. Dispatchers round, and they round differently every time.
WEIGHT_SLACK = 2000

#: Same idea for the dimensions, in inches.
HEIGHT_SLACK = 6


class Likeness(StrEnum):
    """How alike two applications are."""

    SAME = "the same move"
    CLOSE = "probably the same move"
    APART = "a different move"


def _near(one: Pounds | Inches, other: Pounds | Inches, slack: int) -> bool:
    """Are two figures within a tolerance of each other."""
    return abs(int(one) - int(other)) <= slack


def _same_load(one: Application, other: Application) -> bool:
    """Is this the same thing on the trailer, allowing for rounding."""
    return (
        _near(one.load.weight, other.load.weight, WEIGHT_SLACK)
        and _near(one.load.width, other.load.width, HEIGHT_SLACK)
        and _near(one.load.height, other.load.height, HEIGHT_SLACK)
    )


def _same_route(one: Application, other: Application) -> bool:
    """Do the two run between the same two junctions.

    An annual names no route, so two annuals are treated as running the same
    one. That is not a fudge: an annual covers the whole system and two annuals
    for one rig genuinely do overlap everywhere.
    """
    if one.kind is Kind.ANNUAL and other.kind is Kind.ANNUAL:
        return True
    return (one.origin, one.destination) == (other.origin, other.destination)


def likeness(one: Application, other: Application) -> Likeness:
    """How alike two applications are.

    ``SAME`` needs the carrier, the rig, the kind, the route, the days and the
    load to line up. ``CLOSE`` drops the load, because the commonest real
    duplicate is the same move with the weight typed twice from two emails.
    """
    for name, value in (("one", one), ("other", other)):
        if not isinstance(value, Application):
            raise BadValueError(name, value, "want an application")
    if one.carrier != other.carrier or one.rig != other.rig:
        return Likeness.APART
    if one.kind is not other.kind:
        return Likeness.APART
    if not one.span.overlaps(other.span):
        return Likeness.APART
    if not _same_route(one, other):
        return Likeness.APART
    return Likeness.SAME if _same_load(one, other) else Likeness.CLOSE


@dataclass(frozen=True, slots=True, order=True)
class Match:
    """One application already on file that looks like this one."""

    likeness: Likeness
    key: int
    application: Application

    def __post_init__(self) -> None:
        object.__setattr__(self, "likeness", Likeness(self.likeness))
        if isinstance(self.key, bool) or not isinstance(self.key, int):
            raise BadValueError("key", self.key, "want a whole number")
        if self.key < 1:
            raise BadValueError("key", self.key, "application keys start at one")
        if not isinstance(self.application, Application):
            raise BadValueError("application", self.application, "want an application")
        if self.likeness is Likeness.APART:
            raise BadValueError("likeness", self.likeness, "not a match at all")

    @property
    def certain(self) -> bool:
        """Is this one the office would stop rather than warn about."""
        return self.likeness is Likeness.SAME

    def __str__(self) -> str:
        return f"application {self.key} looks like {self.likeness}: {self.application.span}"


def duplicates_of(wanted: Application, filed: list[tuple[int, Application]]) -> list[Match]:
    """Everything already on file that looks like this application.

    Certain matches come first, and within a degree the newest key first, so the
    clerk sees the one taken forty minutes ago rather than the one from March.
    """
    found = [
        Match(likeness=how, key=key, application=one)
        for key, one in filed
        if (how := likeness(wanted, one)) is not Likeness.APART
    ]
    return sorted(found, key=lambda m: (m.likeness is not Likeness.SAME, -m.key))
