"""Working out which dolly would get a load under the limits.

A carrier turns up over on the drives and asks what to do about it. The answer is
usually a jeep, sometimes a booster, occasionally both, and which one depends on
where the weight is and how far the trailer spreads. Doing it by hand takes a
clerk ten minutes and a scrap of paper.

This does the same search the scrap of paper does: try each dolly the office
keeps on its list, at each hitch point, at each transfer the dolly is rated for,
and see which combination leaves the fewest pounds over. It is a small brute
force and it stays small because the list is short and the transfer steps are
coarse. Two thousand pound steps are what a carrier can actually load to.

Nothing here decides anything. It hands back an ordered list of suggestions and
the clerk reads the top one out.
"""

from __future__ import annotations

from dataclasses import dataclass

from jeepdolly.errors import BadValueError
from jeepdolly.limits.assess import assess
from jeepdolly.limits.bridge import bridge_limit
from jeepdolly.limits.dimension import LEGAL, SizeRule
from jeepdolly.limits.statute import INTERSTATE, Statute
from jeepdolly.rig.axle import Axle
from jeepdolly.rig.config import Configuration
from jeepdolly.rig.dolly import Dolly, Hitch, attach
from jeepdolly.rig.load import Load
from jeepdolly.units.length import feet, inches
from jeepdolly.units.mass import format_weight, pounds

__all__ = [
    "CATALOGUE",
    "STEP",
    "Suggestion",
    "already_legal",
    "best",
    "spread_options",
    "spread_score",
    "suggest",
]

#: Transfers are tried in steps of this many pounds. Finer steps find answers a
#: carrier cannot actually load to.
STEP = 2000


def _dolly_axle(weight: int) -> Axle:
    """One axle of a dolly, on eight tires at eleven inches."""
    return Axle(weight=pounds(weight), tires=8, tire_width=inches(11))


#: The dollies the office keeps on its list, lightest first.
CATALOGUE: tuple[tuple[str, Dolly], ...] = (
    (
        "single axle jeep",
        Dolly(
            kind=Hitch.JEEP,
            axles=(_dolly_axle(3200),),
            spacings=(),
            hitch=feet(9),
            capacity=pounds(20_000),
        ),
    ),
    (
        "two axle jeep",
        Dolly(
            kind=Hitch.JEEP,
            axles=(_dolly_axle(3200), _dolly_axle(3200)),
            spacings=(feet(4),),
            hitch=feet(9),
            capacity=pounds(40_000),
        ),
    ),
    (
        "three axle jeep",
        Dolly(
            kind=Hitch.JEEP,
            axles=(_dolly_axle(3200), _dolly_axle(3200), _dolly_axle(3200)),
            spacings=(feet(4), feet(4)),
            hitch=feet(9),
            capacity=pounds(60_000),
        ),
    ),
    (
        "single axle booster",
        Dolly(
            kind=Hitch.BOOSTER,
            axles=(_dolly_axle(2800),),
            spacings=(),
            hitch=feet(10),
            capacity=pounds(18_000),
        ),
    ),
    (
        "two axle booster",
        Dolly(
            kind=Hitch.BOOSTER,
            axles=(_dolly_axle(2800), _dolly_axle(2800)),
            spacings=(feet(4),),
            hitch=feet(10),
            capacity=pounds(36_000),
        ),
    ),
)


@dataclass(frozen=True, slots=True, order=True)
class Suggestion:
    """One dolly, at one hitch point, taking one transfer.

    Ordered worst overage first so a plain sort puts the best answer at the
    front. The tie breaks run excess, then finding count, then transfer, then
    the name, which keeps the same question answering the same way.
    """

    excess: int
    findings: int
    transfer: int
    name: str
    at: int
    made: Configuration

    @property
    def clears(self) -> bool:
        """Does this arrangement leave nothing over."""
        return self.excess == 0 and self.findings == 0

    def __str__(self) -> str:
        tail = "clears" if self.clears else f"{format_weight(pounds(self.excess))} over"
        return (
            f"{self.name} behind axle {self.at + 1} taking"
            f" {format_weight(pounds(self.transfer))}: {tail}"
        )


def spread_score(config: Configuration, statute: Statute) -> tuple[int, int]:
    """How bad an arrangement is on the rules a dolly can actually move.

    Two rules are deliberately left out, and getting both wrong is what this
    search did first.

    The gross limit is not a dolly's business. A jeep cannot reduce gross weight;
    it *adds* its own tare to it. Scoring on gross reported that every dolly made
    things worse, which was arithmetically true and useless.

    Neither is the bridge formula applied to the whole rig, because that run is
    capped at the gross limit and so is the gross limit wearing a hat. Every
    shorter run is counted, and those are exactly the ones another axle helps.
    """
    excesses: list[int] = []
    for axle in config.axles:
        over = int(axle.weight) - int(statute.single)
        if over > 0:
            excesses.append(over)
        if axle.over_tires:
            excesses.append(int(axle.weight) - int(axle.tire_limit))
    for run in config.runs():
        if run.single or run.count == config.count:
            continue
        if statute.is_tandem(run) and int(run.weight) > int(statute.tandem):
            excesses.append(int(run.weight) - int(statute.tandem))
        case = bridge_limit(config, run, statute)
        if int(case.over) > 0:
            excesses.append(int(case.over))
    return (max(excesses, default=0), len(excesses))


def spread_options(
    config: Configuration,
    statute: Statute = INTERSTATE,
    catalogue: tuple[tuple[str, Dolly], ...] = CATALOGUE,
) -> list[Suggestion]:
    """Every arrangement worth trying, best first.

    A transfer of zero is not tried. Adding a dolly and moving nothing onto it
    puts its tare on the road for no benefit, and if that is the answer the
    carrier does not need a dolly at all.
    """
    if not catalogue:
        raise BadValueError("catalogue", catalogue, "want at least one dolly")
    found: list[Suggestion] = []
    for name, dolly in catalogue:
        points = (
            [config.count - 1]
            if dolly.kind is Hitch.BOOSTER
            else list(range(1, config.count - 1))
        )
        for at in points:
            for transfer in range(STEP, int(dolly.capacity) + 1, STEP):
                try:
                    made = attach(config, dolly, at, pounds(transfer))
                except BadValueError:
                    continue
                excess, findings = spread_score(made, statute)
                found.append(
                    Suggestion(
                        excess=excess,
                        findings=findings,
                        transfer=transfer,
                        name=name,
                        at=at,
                        made=made,
                    )
                )
    return sorted(found)


def suggest(
    config: Configuration,
    statute: Statute = INTERSTATE,
    catalogue: tuple[tuple[str, Dolly], ...] = CATALOGUE,
    limit: int = 3,
) -> list[Suggestion]:
    """The best few arrangements, one per dolly so the list is worth reading."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise BadValueError("limit", limit, "want at least one")
    seen: set[str] = set()
    out: list[Suggestion] = []
    for option in spread_options(config, statute, catalogue):
        if option.name in seen:
            continue
        seen.add(option.name)
        out.append(option)
        if len(out) == limit:
            break
    return out


def best(
    config: Configuration,
    statute: Statute = INTERSTATE,
    catalogue: tuple[tuple[str, Dolly], ...] = CATALOGUE,
) -> Suggestion | None:
    """The single best arrangement, or nothing if none was tried."""
    found = suggest(config, statute, catalogue, limit=1)
    return found[0] if found else None


def already_legal(
    config: Configuration,
    load: Load,
    statute: Statute = INTERSTATE,
    size_rule: SizeRule = LEGAL,
) -> bool:
    """Is the rig under every weight limit as presented, gross included.

    This is the honest question, so it looks at everything rather than only at
    what a dolly could move. A rig that is legal on every axle and forty thousand
    pounds over gross is not legal, it is a permit.
    """
    seen = assess(config, load, statute, size_rule)
    return not any(f.billable for f in seen.findings)
