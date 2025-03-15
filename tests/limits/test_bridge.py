import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.limits.bridge import (
    STEP,
    TANDEM_EXCEPTION_SPREAD,
    bridge_cases,
    bridge_limit,
    check_bridge,
    formula_weight,
    round_to_step,
    tandem_exception,
    whole_feet,
)
from jeepdolly.limits.statute import INTERSTATE
from jeepdolly.units.length import feet, inches

from .conftest import drive, rig, steer


def test_whole_feet_of_an_exact_foot():
    assert whole_feet(feet(12)) == 12


def test_whole_feet_rounds_up():
    assert whole_feet(inches(12 * 12 + 1)) == 13


def test_whole_feet_rounds_eleven_inches_up():
    assert whole_feet(inches(12 * 12 + 11)) == 13


def test_whole_feet_of_zero():
    assert whole_feet(inches(0)) == 0


def test_round_to_step_leaves_a_multiple_alone():
    assert int(round_to_step(34000)) == 34000


def test_round_to_step_rounds_a_half_up():
    assert int(round_to_step(34250)) == 34500


def test_round_to_step_rounds_below_a_half_down():
    assert int(round_to_step(34249)) == 34000


def test_round_to_step_refuses_a_bool():
    with pytest.raises(BadValueError):
        round_to_step(True)


def test_round_to_step_refuses_negative():
    with pytest.raises(BadValueError):
        round_to_step(-1)


def test_step_is_five_hundred():
    assert STEP == 500


def test_formula_needs_two_axles():
    with pytest.raises(BadValueError):
        formula_weight(feet(4), 1)


def test_formula_refuses_a_bool_axle_count():
    with pytest.raises(BadValueError):
        formula_weight(feet(4), True)


@pytest.mark.parametrize(
    ("span", "axles", "want"),
    [
        (4, 2, 34000),
        (8, 2, 38000),
        (4, 3, 39000),
        (8, 3, 42000),
        (36, 4, 66000),
        (40, 4, 68500),
        (51, 5, 80000),
        (60, 6, 90000),
    ],
)
def test_formula_matches_the_published_table(span, axles, want):
    assert int(formula_weight(feet(span), axles)) == want


def test_formula_rounds_the_span_up_before_it_works():
    assert formula_weight(inches(4 * 12 + 1), 2) == formula_weight(feet(5), 2)


def test_formula_climbs_with_length():
    short = int(formula_weight(feet(20), 4))
    long = int(formula_weight(feet(40), 4))
    assert long > short


def test_formula_climbs_with_axle_count():
    few = int(formula_weight(feet(30), 3))
    many = int(formula_weight(feet(30), 5))
    assert many > few


def test_bridge_limit_is_capped_at_the_gross():
    made = rig(
        "LONG",
        [steer(), drive(), drive(), drive(), drive()],
        [feet(15), feet(20), feet(20), feet(20)],
    )
    case = bridge_limit(made, made.run(0, 4), INTERSTATE)
    assert int(case.limit) == int(INTERSTATE.gross)
    assert int(case.formula) > int(INTERSTATE.gross)


def test_bridge_limit_refuses_a_single_axle(legal_five):
    with pytest.raises(BadValueError):
        bridge_limit(legal_five, legal_five.run(2, 2), INTERSTATE)


def test_bridge_limit_reports_the_span_in_feet(legal_five):
    case = bridge_limit(legal_five, legal_five.run(1, 2), INTERSTATE)
    assert case.span_feet == 4


def test_over_is_zero_when_the_group_is_under(legal_five):
    case = bridge_limit(legal_five, legal_five.run(1, 2), INTERSTATE)
    assert int(case.over) == 0


def test_over_is_the_difference_when_the_group_is_heavy():
    heavy = rig("HV", [steer(), drive(25000), drive(25000)], [feet(15), feet(4)])
    case = bridge_limit(heavy, heavy.run(1, 2), INTERSTATE)
    assert int(case.over) == 50000 - 34000


def test_the_tandem_exception_applies_to_the_standard_five_axle(legal_five):
    assert tandem_exception(legal_five, legal_five.run(1, 4), INTERSTATE)


def test_the_exception_needs_thirty_six_feet():
    tight = rig(
        "TIGHT",
        [steer(), drive(), drive(), drive(), drive()],
        [feet(15), feet(4), feet(20), feet(4)],
    )
    assert int(tight.extreme(1, 4)) < int(TANDEM_EXCEPTION_SPREAD)
    assert not tandem_exception(tight, tight.run(1, 4), INTERSTATE)


def test_the_exception_needs_four_axles(legal_five):
    assert not tandem_exception(legal_five, legal_five.run(1, 3), INTERSTATE)


def test_the_exception_needs_both_pairs_to_be_tandems():
    spread = rig(
        "SPREAD",
        [steer(), drive(), drive(), drive(), drive()],
        [feet(15), feet(10), feet(26), feet(4)],
    )
    assert not tandem_exception(spread, spread.run(1, 4), INTERSTATE)


def test_the_exception_lifts_the_group_to_sixty_eight_thousand(legal_five):
    case = bridge_limit(legal_five, legal_five.run(1, 4), INTERSTATE)
    assert case.excepted
    assert int(case.limit) == 68000


def test_without_the_exception_that_group_would_be_over():
    case_span = int(formula_weight(feet(38), 4))
    assert case_span < 68000


def test_the_standard_five_axle_at_eighty_thousand_clears_the_formula(legal_five):
    assert check_bridge(legal_five, INTERSTATE) == []


def test_a_heavy_rig_reports_bridge_findings(heavy_five):
    findings = check_bridge(heavy_five, INTERSTATE)
    assert findings
    assert all(f.rule == "bridge-formula" for f in findings)


def test_bridge_findings_name_the_span(heavy_five):
    findings = check_bridge(heavy_five, INTERSTATE)
    assert any("feet" in f.detail for f in findings)


def test_bridge_cases_cover_every_multi_axle_run(legal_five):
    cases = list(bridge_cases(legal_five, INTERSTATE))
    assert len(cases) == 5 * 6 // 2 - 5


def test_a_bridge_case_mentions_the_exception_in_its_finding():
    heavy = rig(
        "EXC",
        [steer(12000), drive(20000), drive(20000), drive(20000), drive(20000)],
        [feet(15), feet(4), feet(30), feet(4)],
    )
    findings = check_bridge(heavy, INTERSTATE)
    assert any("tandem exception" in f.detail for f in findings)


def test_the_formula_answer_is_always_a_multiple_of_the_step():
    for span in range(0, 60, 3):
        for axles in range(2, 8):
            assert int(formula_weight(feet(span), axles)) % STEP == 0
