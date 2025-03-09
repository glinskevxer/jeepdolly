"""Splitting a whole number into whole parts.

Weight comes off a trailer group and lands on a dolly, and both sides are whole
pounds. Fees split across two agencies and both halves are whole cents. In every
case the parts have to add back to the whole exactly, so the split cannot be
done with rounding and has to be done with remainders.

The rule is largest remainder. Everybody gets the floor of their exact share,
then the leftover units go one each to the largest fractional parts, and ties
break toward the earlier position. Ties breaking by position rather than by size
is deliberate: it makes the split reproducible, which matters when the same
permit is recalculated a year later during an audit.
"""

from __future__ import annotations

from collections.abc import Sequence
from fractions import Fraction

from jeepdolly.errors import BadValueError

__all__ = ["divide_by_weight", "divide_evenly", "largest_remainder"]


def _check_total(total: int) -> int:
    if isinstance(total, bool) or not isinstance(total, int):
        raise BadValueError("total", total, "want a whole number")
    if total < 0:
        raise BadValueError("total", total, "negative")
    return total


def divide_evenly(total: int, parts: int) -> tuple[int, ...]:
    """Split a whole number into ``parts`` as evenly as it goes.

    The leftover units go to the earliest positions, so a split of seven into
    three is ``(3, 2, 2)`` and not ``(2, 2, 3)``. The heaviest share sitting at
    the front matches how a loader actually stacks a dolly.
    """
    total = _check_total(total)
    if isinstance(parts, bool) or not isinstance(parts, int):
        raise BadValueError("parts", parts, "want a whole number")
    if parts < 1:
        raise BadValueError("parts", parts, "want at least one part")
    base, extra = divmod(total, parts)
    return tuple(base + (1 if i < extra else 0) for i in range(parts))


def divide_by_weight(total: int, weights: Sequence[int]) -> tuple[int, ...]:
    """Split a whole number in proportion to a sequence of weights.

    Weights are whole numbers and at least one has to be above zero. A weight of
    zero takes nothing, including nothing from the leftover pass, because a
    position that carries no load has no claim on the transfer.
    """
    total = _check_total(total)
    if not isinstance(weights, Sequence) or isinstance(weights, str | bytes):
        raise BadValueError("weights", weights, "want a sequence of whole numbers")
    if not weights:
        raise BadValueError("weights", weights, "want at least one weight")
    for weight in weights:
        if isinstance(weight, bool) or not isinstance(weight, int):
            raise BadValueError("weight", weight, "want a whole number")
        if weight < 0:
            raise BadValueError("weight", weight, "negative")
    pool = sum(weights)
    if pool == 0:
        raise BadValueError("weights", weights, "they are all zero")
    exact = [Fraction(total * weight, pool) for weight in weights]
    return largest_remainder(total, exact, eligible=[w > 0 for w in weights])


def largest_remainder(
    total: int, exact: Sequence[Fraction], eligible: Sequence[bool] | None = None
) -> tuple[int, ...]:
    """Round exact shares to whole units so they still add to the total.

    ``exact`` are the unrounded claims and they are trusted to add to ``total``.
    ``eligible`` marks the positions allowed to pick up a leftover unit; leaving
    it out makes every position eligible.
    """
    if eligible is None:
        eligible = [True] * len(exact)
    if len(eligible) != len(exact):
        raise BadValueError("eligible", len(eligible), f"want {len(exact)} flags")
    floors = [int(claim) for claim in exact]
    leftover = total - sum(floors)
    if leftover < 0:
        raise BadValueError("shares", exact, "they add to more than the total")
    order = sorted(
        (i for i, ok in enumerate(eligible) if ok),
        key=lambda i: (-(exact[i] - floors[i]), i),
    )
    if leftover > len(order):
        raise BadValueError("shares", exact, "no eligible position to take the leftover")
    for i in order[:leftover]:
        floors[i] += 1
    return tuple(floors)
