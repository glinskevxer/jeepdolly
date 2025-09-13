"""Arithmetic laws the office relies on, written down and checkable.

These are not tests. They are statements about the arithmetic that every test
quietly assumes, gathered in one place so that a change which breaks one of them
breaks something named after the law rather than something named after a permit.

Each law is a function that takes a spread of inputs and returns the cases that
broke it. An empty list means it held everywhere it was asked. The suite runs
each over a wide spread; the office's ``check`` command runs a narrow one.

Writing them as functions over a spread rather than as assertions is what lets
the same law be run over a hundred inputs in a test and over four at the counter.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from jeepdolly.billing.tariff import SCHEDULE, Tariff
from jeepdolly.limits.bridge import formula_weight
from jeepdolly.travel.window import subtract
from jeepdolly.units.clock import Window
from jeepdolly.units.length import feet
from jeepdolly.units.mass import POUNDS_PER_TON, pounds, tons_over
from jeepdolly.units.share import divide_by_weight, divide_evenly

__all__ = [
    "LAWS",
    "crossover",
    "cutting_never_adds_minutes",
    "fees_never_fall",
    "formula_climbs_with_axles",
    "formula_climbs_with_length",
    "run_all",
    "shares_add_back",
    "tons_over_is_zero_at_the_limit",
    "weighted_shares_add_back",
]


def shares_add_back(totals: Iterable[int], parts: Iterable[int]) -> list[str]:
    """An even split always adds back to what was split."""
    broken: list[str] = []
    parts = list(parts)
    for total in totals:
        for count in parts:
            got = divide_evenly(total, count)
            if sum(got) != total:
                broken.append(f"divide_evenly({total}, {count}) sums to {sum(got)}")
    return broken


def weighted_shares_add_back(
    totals: Iterable[int], weights: Sequence[Sequence[int]]
) -> list[str]:
    """A weighted split always adds back to what was split."""
    broken: list[str] = []
    for total in totals:
        for spread in weights:
            got = divide_by_weight(total, spread)
            if sum(got) != total:
                broken.append(f"divide_by_weight({total}, {list(spread)}) sums to {sum(got)}")
    return broken


def formula_climbs_with_length(spans: Sequence[int], axles: Iterable[int]) -> list[str]:
    """More spread never lets a group carry less."""
    broken: list[str] = []
    for count in axles:
        previous = -1
        for span in sorted(spans):
            now = int(formula_weight(feet(span), count))
            if now < previous:
                broken.append(f"{count} axles fell from {previous} to {now} at {span} feet")
            previous = now
    return broken


def crossover(count: int) -> int:
    """The spread past which adding an axle stops helping, in feet.

    The formula is ``500 * (L*N/(N-1) + 12N + 36)``. Going from ``N`` to
    ``N + 1`` adds twelve to the second term and takes ``L / (N * (N - 1))`` off
    the first, so the swap only pays while ``L`` is under ``12 * N * (N - 1)``.

    That is not a defect in the formula and it is not a defect here. It says that
    two axles a hundred feet apart are not a group in any useful sense, and the
    statute never contemplated one. The office does not permit such a group and
    the law below is stated over the range where the group is real.
    """
    return 12 * count * (count - 1)


def formula_climbs_with_axles(spans: Iterable[int], axles: Sequence[int]) -> list[str]:
    """More axles never let a group carry less, inside the useful range.

    Only pairs where the spread is under the crossover are compared. Past it the
    formula genuinely turns over, which ``crossover`` explains.
    """
    broken: list[str] = []
    ordered = sorted(axles)
    for span in spans:
        previous = -1
        for count in ordered:
            if span > crossover(count):
                previous = -1
                continue
            now = int(formula_weight(feet(span), count))
            if now < previous:
                broken.append(f"{span} feet fell from {previous} to {now} at {count} axles")
            previous = now
    return broken


def fees_never_fall(tons: Sequence[int], tariff: Tariff = SCHEDULE) -> list[str]:
    """A heavier overage never costs the carrier less."""
    broken: list[str] = []
    previous = -1
    for count in sorted(tons):
        now = int(tariff.overweight_tons(count))
        if now < previous:
            broken.append(f"the charge fell from {previous} to {now} at {count} tons")
        previous = now
    return broken


def tons_over_is_zero_at_the_limit(limits: Iterable[int]) -> list[str]:
    """Nothing is over when it is exactly at the limit, and one pound is one ton."""
    broken: list[str] = []
    for limit in limits:
        at = tons_over(pounds(limit), pounds(limit))
        just_over = tons_over(pounds(limit + 1), pounds(limit))
        exact = tons_over(pounds(limit + POUNDS_PER_TON), pounds(limit))
        if at != 0:
            broken.append(f"at {limit} the office says {at} tons over")
        if just_over != 1:
            broken.append(f"one pound over {limit} is {just_over} tons")
        if exact != 1:
            broken.append(f"one ton over {limit} is {exact} tons")
    return broken


def cutting_never_adds_minutes(bases: Iterable[Window], cuts: Sequence[Window]) -> list[str]:
    """Cutting holes in a window never leaves more minutes than it started with."""
    broken: list[str] = []
    for base in bases:
        for cut in cuts:
            left = sum(window.minutes for window in subtract(base, (cut,)))
            if left > base.minutes:
                broken.append(f"{base} less {cut} left {left} of {base.minutes}")
    return broken


#: Every law, by the name the office calls it.
LAWS = (
    "shares add back",
    "weighted shares add back",
    "the formula climbs with length",
    "the formula climbs with axles",
    "fees never fall",
    "nothing is over at the limit",
    "cutting never adds minutes",
)


def run_all(wide: bool = False) -> dict[str, list[str]]:
    """Run every law over a spread, and hand back what broke.

    ``wide`` swaps a handful of inputs for a few thousand. The counter runs the
    narrow spread because it runs on every ``check``; the suite runs the wide one.
    """
    totals = range(200 if wide else 12)
    spans = range(0, 150 if wide else 20, 1 if wide else 4)
    axles = range(2, 20 if wide else 6)
    tons = range(400 if wide else 30)
    limits = (20_000, 34_000, 80_000) if not wide else range(1_000, 200_000, 977)
    bases = (Window(0, 1439), Window(360, 1080), Window(1260, 360))
    cuts = (Window(420, 540), Window(0, 60), Window(1200, 30))
    return {
        LAWS[0]: shares_add_back(totals, range(1, 9)),
        LAWS[1]: weighted_shares_add_back(totals, ((5, 3, 2), (1, 1), (0, 1, 1), (7,))),
        LAWS[2]: formula_climbs_with_length(list(spans), axles),
        LAWS[3]: formula_climbs_with_axles(spans, list(axles)),
        LAWS[4]: fees_never_fall(list(tons)),
        LAWS[5]: tons_over_is_zero_at_the_limit(limits),
        LAWS[6]: cutting_never_adds_minutes(bases, cuts),
    }
