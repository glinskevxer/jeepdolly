import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.limits.statute import INTERSTATE
from jeepdolly.rig.config import Configuration
from jeepdolly.rig.dolly import Hitch
from jeepdolly.rig.load import Load
from jeepdolly.rig.spread import (
    CATALOGUE,
    STEP,
    Suggestion,
    already_legal,
    best,
    spread_options,
    suggest,
)
from jeepdolly.units.length import feet, feet_inches
from jeepdolly.units.mass import pounds

from .conftest import drive, rig, steer


def a_load(**over: object) -> Load:
    """A transformer that is legal on size and heavy on weight."""
    kw: dict[str, object] = {
        "description": "step-up transformer",
        "weight": pounds(148000),
        "width": feet_inches(8, 6),
        "height": feet_inches(13, 6),
        "length": feet(48),
        "divisible": False,
        "reason": "single-piece",
    }
    kw.update(over)
    return Load(**kw)  # type: ignore[arg-type]


def heavy(weight: int = 24000) -> Configuration:
    """A five axle rig well over on the drives and the trailer."""
    return rig(
        "3S2H",
        [steer(), drive(weight), drive(weight), drive(weight), drive(weight)],
        [feet(15), feet(4), feet(30), feet(4)],
    )


def clearable() -> Configuration:
    """A rig over on the drives that one jeep can get legal."""
    return rig(
        "3S2C",
        [steer(), drive(21000), drive(21000), drive(17000), drive(17000)],
        [feet(15), feet(4), feet(30), feet(4)],
    )


def light() -> Configuration:
    """A five axle rig at the legal weights."""
    return rig(
        "3S2",
        [steer(), drive(), drive(), drive(), drive()],
        [feet(15), feet(4), feet(30), feet(4)],
    )


def test_a_legal_rig_is_already_legal():
    assert already_legal(light(), a_load())


def test_a_heavy_rig_is_not():
    assert not already_legal(heavy(), a_load())


def test_the_catalogue_holds_both_kinds():
    kinds = {dolly.kind for _, dolly in CATALOGUE}
    assert kinds == {Hitch.JEEP, Hitch.BOOSTER}


def test_every_catalogue_entry_is_named():
    assert all(name and name.strip() for name, _ in CATALOGUE)


def test_the_catalogue_names_are_all_different():
    names = [name for name, _ in CATALOGUE]
    assert len(set(names)) == len(names)


def test_the_step_is_a_weight_a_carrier_can_load_to():
    assert STEP == 2000


def test_options_come_back_for_a_heavy_rig():
    assert spread_options(heavy())


def test_options_are_best_first():
    found = spread_options(heavy())
    assert [o.excess for o in found] == sorted(o.excess for o in found)


def test_a_transfer_of_nothing_is_never_offered():
    assert all(o.transfer >= STEP for o in spread_options(heavy()))


def test_every_transfer_is_a_whole_step():
    assert all(o.transfer % STEP == 0 for o in spread_options(heavy()))


def test_a_jeep_is_never_hitched_behind_the_last_axle():
    for option in spread_options(heavy()):
        if "jeep" in option.name:
            assert option.at < 4


def test_a_booster_is_always_hitched_at_the_back():
    for option in spread_options(heavy()):
        if "booster" in option.name:
            assert option.at == 4


def test_options_refuse_an_empty_catalogue():
    with pytest.raises(BadValueError):
        spread_options(heavy(), catalogue=())


def test_the_suggested_arrangement_helps():
    from jeepdolly.rig.spread import spread_score

    before, _ = spread_score(heavy(), INTERSTATE)
    found = best(heavy())
    assert found is not None
    assert found.excess < before


def test_a_rig_that_cannot_be_cleared_still_gets_the_best_on_offer():
    found = best(heavy(30000))
    assert found is not None
    assert not found.clears


def test_one_jeep_clears_a_rig_that_is_over_on_the_drives():
    found = best(clearable())
    assert found is not None
    assert found.excess == 0
    assert found.clears
    assert "jeep" in found.name


def test_the_arrangement_that_clears_says_so_when_printed():
    found = best(clearable())
    assert found is not None
    assert str(found).endswith("clears")


def test_an_arrangement_that_does_not_clear_says_how_far_over():
    found = best(heavy(30000))
    assert found is not None
    assert "over" in str(found)


def test_the_suggestion_names_the_dolly_and_the_hitch():
    found = best(clearable())
    assert found is not None
    assert "behind axle" in str(found)


def test_suggest_offers_one_arrangement_per_dolly():
    found = suggest(heavy(), limit=3)
    assert len(found) == 3
    assert len({o.name for o in found}) == 3


def test_suggest_never_offers_more_than_the_catalogue_holds():
    found = suggest(heavy(), limit=99)
    assert len(found) <= len(CATALOGUE)


def test_suggest_refuses_a_limit_of_zero():
    with pytest.raises(BadValueError):
        suggest(heavy(), limit=0)


def test_suggest_refuses_a_bool_limit():
    with pytest.raises(BadValueError):
        suggest(heavy(), limit=True)


def test_the_made_rig_carries_the_dolly_axles():
    found = best(clearable())
    assert found is not None
    assert found.made.count > 5


def test_the_made_rig_weighs_the_dolly_tare_more():
    found = best(clearable())
    assert found is not None
    assert int(found.made.gross) > int(clearable().gross)


def test_the_cleared_rig_is_under_every_axle_limit():
    found = best(clearable())
    assert found is not None
    assert all(int(axle.weight) <= int(INTERSTATE.single) for axle in found.made.axles)


def test_the_same_question_answers_the_same_way():
    first = best(heavy())
    for _ in range(3):
        again = best(heavy())
        assert first is not None
        assert again is not None
        assert (again.name, again.at, again.transfer) == (first.name, first.at, first.transfer)


def test_a_suggestion_orders_by_its_overage():
    worse = Suggestion(excess=9000, findings=2, transfer=2000, name="a", at=1, made=light())
    better = Suggestion(excess=0, findings=0, transfer=2000, name="b", at=1, made=light())
    assert sorted([worse, better])[0] is better


def test_a_rig_already_legal_still_gets_options():
    assert spread_options(light())


def test_a_clearing_arrangement_is_offered_on_its_own():
    from jeepdolly.rig.spread import pairs

    found = pairs(clearable(), limit=1)
    assert found[0][0].clears
    assert found[0][1] is None


def test_a_second_dolly_is_offered_only_when_it_helps():
    from jeepdolly.rig.spread import pairs

    for first, second in pairs(heavy(), limit=3):
        if second is not None:
            assert second.excess < first.excess


def test_a_second_dolly_does_not_help_the_office_catalogue():
    """Measured, and stated in the module docstring.

    Swept over five axle rigs from eighteen to twenty seven thousand pounds an
    axle, no second dolly leaves the rig less over than the first one did. That
    falls out of the donor rule rather than out of the search, and this is here
    so that a change to either is noticed.

    The steps are coarse on purpose. The finer sweep that was run once by hand
    took forty seconds and found the same thing, and a forty second test is one
    somebody eventually stops running.
    """
    from jeepdolly.rig.spread import pairs

    for drives in range(18000, 27001, 3000):
        for trailer in range(18000, 27001, 4500):
            made = rig(
                "SWEEP",
                [steer(), drive(drives), drive(drives), drive(trailer), drive(trailer)],
                [feet(15), feet(4), feet(30), feet(4)],
            )
            for _, second in pairs(made, limit=1):
                assert second is None


def test_the_pairs_list_is_as_long_as_asked_for():
    from jeepdolly.rig.spread import pairs

    assert len(pairs(heavy(), limit=2)) == 2


def test_every_pair_leads_with_a_single_dolly():
    from jeepdolly.rig.spread import pairs

    for first, _ in pairs(heavy(), limit=3):
        assert first.made.count > 5


def test_the_pair_search_answers_the_same_way_twice():
    from jeepdolly.rig.spread import pairs

    first = [(a.name, b.name if b else None) for a, b in pairs(heavy(), limit=3)]
    for _ in range(3):
        again = [(a.name, b.name if b else None) for a, b in pairs(heavy(), limit=3)]
        assert again == first
