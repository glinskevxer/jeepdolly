"""What a carrier has to have lodged before each sort of permit may be written.

The amounts are the office's, not the statute's. The statute names one bond
figure and leaves the rest to the issuing authority, which is how a trip permit
for a backhoe and an annual for a fleet of lowboys ended up behind the same fifty
thousand dollar bond for years. They are not the same risk and they no longer sit
behind the same number.

A gap is not a refusal. It is a thing the clerk can read out over the counter,
and most of them are cleared the same morning by a carrier's insurer faxing a
fresh certificate. The decision to refuse belongs in ``decision`` and takes these
as one input among several.

Escort cover is asked for only when the move actually needs escorts, which is why
``requirements`` takes a flag rather than reading it off the permit kind. A
superload that fits down the road on its own does not need the office holding a
certificate against a pilot car that is not there.
"""

from __future__ import annotations

from dataclasses import dataclass

from jeepdolly.errors import BadValueError
from jeepdolly.party.surety import Certificate, Cover, in_force
from jeepdolly.permit.application import Kind
from jeepdolly.units.clock import Day
from jeepdolly.units.money import Money, cents, format_money

__all__ = [
    "ESCORT_COVER",
    "REQUIRED",
    "Gap",
    "Requirement",
    "clear_to_issue",
    "gaps",
    "requirements",
]


@dataclass(frozen=True, slots=True, order=True)
class Requirement:
    """One cover a permit needs, and how much of it."""

    cover: Cover
    amount: Money
    because: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "cover", Cover(self.cover))
        object.__setattr__(self, "amount", cents(int(self.amount)))
        if int(self.amount) <= 0:
            raise BadValueError("amount", int(self.amount), "a requirement is for some money")
        if not isinstance(self.because, str) or not self.because.strip():
            raise BadValueError("because", self.because, "want some text")
        object.__setattr__(self, "because", " ".join(self.because.split()))

    def __str__(self) -> str:
        return f"{self.cover} of {format_money(self.amount)}"


#: What each sort of permit needs behind it before a clerk may write it.
REQUIRED: dict[Kind, tuple[Requirement, ...]] = {
    Kind.TRIP: (
        Requirement(
            cover=Cover.BOND,
            amount=cents(50_000_00),
            because="one move, and the damage is one structure at worst",
        ),
        Requirement(
            cover=Cover.LIABILITY,
            amount=cents(750_000_00),
            because="the federal floor for a for hire carrier",
        ),
    ),
    Kind.ANNUAL: (
        Requirement(
            cover=Cover.BOND,
            amount=cents(100_000_00),
            because="a year of moves against one certificate",
        ),
        Requirement(
            cover=Cover.LIABILITY,
            amount=cents(1_000_000_00),
            because="a year of moves against one certificate",
        ),
    ),
    Kind.SUPERLOAD: (
        Requirement(
            cover=Cover.BOND,
            amount=cents(250_000_00),
            because="a superload that drops a span is not a fifty thousand dollar repair",
        ),
        Requirement(
            cover=Cover.LIABILITY,
            amount=cents(5_000_000_00),
            because="a superload that drops a span is not a fifty thousand dollar repair",
        ),
        Requirement(
            cover=Cover.CARGO,
            amount=cents(250_000_00),
            because="the piece on the trailer is usually worth more than the trailer",
        ),
    ),
}

#: Asked for on top of the rest when the move is escorted.
ESCORT_COVER = Requirement(
    cover=Cover.ESCORT,
    amount=cents(1_000_000_00),
    because="the pilot car is the carrier's contractor and drives on the office's word",
)


def requirements(kind: Kind, escorted: bool = False) -> tuple[Requirement, ...]:
    """Everything one permit needs lodged behind it."""
    found = REQUIRED.get(Kind(kind))
    if found is None:
        raise BadValueError("kind", kind, "no cover schedule for that sort of permit")
    if not isinstance(escorted, bool):
        raise BadValueError("escorted", escorted, "want true or false")
    return (*found, ESCORT_COVER) if escorted else found


@dataclass(frozen=True, slots=True)
class Gap:
    """One requirement a carrier does not currently meet."""

    requirement: Requirement
    held: Certificate | None
    short: Money

    def __post_init__(self) -> None:
        if not isinstance(self.requirement, Requirement):
            raise BadValueError("requirement", self.requirement, "want a requirement")
        object.__setattr__(self, "short", cents(int(self.short)))
        if int(self.short) <= 0:
            raise BadValueError("short", int(self.short), "a gap is short by something")
        if self.held is not None and not isinstance(self.held, Certificate):
            raise BadValueError("held", self.held, "want a certificate or nothing")

    @property
    def nothing_lodged(self) -> bool:
        """Is the cover missing outright rather than merely too small."""
        return self.held is None

    def __str__(self) -> str:
        if self.held is None:
            want = format_money(self.requirement.amount)
            return f"no {self.requirement.cover} on file, needs {want}"
        return (
            f"{self.requirement.cover} is {format_money(self.short)} short of"
            f" {format_money(self.requirement.amount)}"
        )


def gaps(held: list[Certificate], kind: Kind, on: Day, escorted: bool = False) -> list[Gap]:
    """Every requirement this carrier does not meet on a day.

    Only certificates good on the day count. A bond that ran out yesterday is
    the same as no bond, and treating it as cover because the row is still on
    file is the mistake this whole module exists to stop.
    """
    good = {str(one.cover): one for one in in_force(held, on)}
    found: list[Gap] = []
    for need in requirements(kind, escorted):
        have = good.get(str(need.cover))
        if have is None:
            found.append(Gap(requirement=need, held=None, short=need.amount))
            continue
        short = have.shortfall(need.amount)
        if int(short) > 0:
            found.append(Gap(requirement=need, held=have, short=short))
    return found


def clear_to_issue(
    held: list[Certificate], kind: Kind, on: Day, escorted: bool = False
) -> bool:
    """Does this carrier meet every requirement for this sort of permit."""
    return not gaps(held, kind, on, escorted)
