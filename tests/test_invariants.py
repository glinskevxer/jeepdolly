from collections.abc import Sequence

from jeepdolly.invariants import (
    LAWS,
    cutting_never_adds_minutes,
    fees_never_fall,
    formula_climbs_with_axles,
    formula_climbs_with_length,
    run_all,
    shares_add_back,
    tons_over_is_zero_at_the_limit,
    weighted_shares_add_back,
)
from jeepdolly.units.clock import Window
from jeepdolly.units.length import Inches
from jeepdolly.units.mass import Pounds, pounds


def test_every_law_holds_over_a_wide_spread():
    broken = {name: cases for name, cases in run_all(wide=True).items() if cases}
    assert broken == {}


def test_every_law_holds_over_the_narrow_spread():
    assert all(cases == [] for cases in run_all().values())


def test_the_narrow_run_covers_every_law():
    assert set(run_all()) == set(LAWS)


def test_shares_add_back_over_a_long_spread():
    assert shares_add_back(range(300), range(1, 12)) == []


def test_weighted_shares_add_back_over_a_long_spread():
    spreads = ((5, 3, 2), (1,), (0, 0, 1), (17, 13, 11, 7))
    assert weighted_shares_add_back(range(300), spreads) == []


def test_the_formula_climbs_with_length_over_a_long_spread():
    assert formula_climbs_with_length(list(range(150)), range(2, 25)) == []


def test_the_formula_climbs_with_axles_over_a_long_spread():
    assert formula_climbs_with_axles(range(150), list(range(2, 25))) == []


def test_fees_never_fall_over_a_long_spread():
    assert fees_never_fall(list(range(1000))) == []


def test_nothing_is_over_at_the_limit_over_a_long_spread():
    assert tons_over_is_zero_at_the_limit(range(1000, 200000, 331)) == []


def test_cutting_never_adds_minutes_over_a_long_spread():
    bases = [Window(start, (start + 600) % 1440) for start in range(0, 1440, 37)]
    cuts = [Window(start, (start + 200) % 1440) for start in range(0, 1440, 53)]
    assert cutting_never_adds_minutes(bases, cuts) == []


def test_a_broken_share_is_reported(monkeypatch):
    from jeepdolly import invariants

    def wrong(total: int, parts: int) -> tuple[int, ...]:
        """A split that loses everything it was given."""
        return (0,) * parts

    monkeypatch.setattr(invariants, "divide_evenly", wrong)
    assert shares_add_back([5], [2])


def test_the_crossover_climbs_with_the_axle_count():
    from jeepdolly.invariants import crossover

    assert crossover(2) < crossover(3) < crossover(4)


def test_past_the_crossover_the_formula_really_does_turn_over():
    from jeepdolly.invariants import crossover
    from jeepdolly.limits.bridge import formula_weight
    from jeepdolly.units.length import feet as as_feet

    span = crossover(2) + 40
    two = int(formula_weight(as_feet(span), 2))
    three = int(formula_weight(as_feet(span), 3))
    assert three < two


def test_a_falling_fee_is_reported():
    class Backwards:
        """A tariff that charges less the heavier the load gets."""

        def overweight_tons(self, tons: int) -> int:
            """The wrong way round on purpose."""
            return -tons

    assert fees_never_fall([1, 2, 3], Backwards())  # type: ignore[arg-type]


def test_every_law_has_a_name():
    assert len(LAWS) == len(set(LAWS))
    assert all(name and name == name.lower() for name in LAWS)


def test_a_broken_weighted_share_is_reported(monkeypatch):
    from jeepdolly import invariants

    def wrong(total: int, weights: Sequence[int]) -> tuple[int, ...]:
        """A weighted split that loses everything it was given."""
        return (0,) * len(weights)

    monkeypatch.setattr(invariants, "divide_by_weight", wrong)
    assert weighted_shares_add_back([5], [(1, 1)])


def test_a_formula_that_falls_with_length_is_reported(monkeypatch):
    from jeepdolly import invariants

    def wrong(length: Inches, axles: int) -> Pounds:
        """A formula that shrinks as the group spreads."""
        return pounds(max(0, 100000 - int(length)))

    monkeypatch.setattr(invariants, "formula_weight", wrong)
    assert formula_climbs_with_length([0, 10, 20], [2])


def test_a_formula_that_falls_with_axles_is_reported(monkeypatch):
    from jeepdolly import invariants

    def wrong(length: Inches, axles: int) -> Pounds:
        """A formula that shrinks as axles are added."""
        assert int(length) >= 0
        return pounds(max(0, 100000 - axles * 1000))

    monkeypatch.setattr(invariants, "formula_weight", wrong)
    assert formula_climbs_with_axles([0], [2, 3, 4])


def test_a_limit_that_is_over_at_the_limit_is_reported(monkeypatch):
    from jeepdolly import invariants

    def wrong(value: Pounds, limit: Pounds) -> int:
        """A ton count that is never zero."""
        assert int(value) >= 0
        assert int(limit) >= 0
        return 7

    monkeypatch.setattr(invariants, "tons_over", wrong)
    assert tons_over_is_zero_at_the_limit([20000])


def test_a_cut_that_adds_minutes_is_reported(monkeypatch):
    from jeepdolly import invariants

    def wrong(base: Window, cuts: tuple[Window, ...]) -> tuple[Window, ...]:
        """A subtraction that hands back more than it was given."""
        assert not base.empty
        assert cuts
        return (Window(0, 1439), Window(0, 1439))

    monkeypatch.setattr(invariants, "subtract", wrong)
    assert cutting_never_adds_minutes([Window(360, 600)], [Window(400, 500)])
