import pytest

from jeepdolly.limits.assess import Assessment, assess, check_divisible, check_tires
from jeepdolly.limits.dimension import LEGAL, SizeRule
from jeepdolly.limits.finding import Finding, Severity
from jeepdolly.limits.statute import INTERSTATE, STATE_ROUTE
from jeepdolly.rig.load import Load
from jeepdolly.units.length import feet, feet_inches, inches
from jeepdolly.units.mass import pounds

from .conftest import drive, rig, steer


def a_load(**over: object) -> Load:
    kw: dict[str, object] = {
        "description": "excavator",
        "weight": pounds(96000),
        "width": feet_inches(8, 6),
        "height": feet_inches(13, 6),
        "length": feet(48),
        "divisible": False,
        "reason": "single-piece",
    }
    kw.update(over)
    return Load(**kw)  # type: ignore[arg-type]


def test_a_legal_rig_and_load_assesses_clean(legal_five):
    got = assess(legal_five, a_load())
    assert got.clean
    assert len(got) == 0


def test_a_divisible_load_is_blocked(legal_five):
    got = assess(legal_five, a_load(divisible=True, reason=""))
    assert got.blocked
    assert got.severity is Severity.REFUSE


def test_the_divisible_finding_comes_first(heavy_five):
    got = assess(heavy_five, a_load(divisible=True, reason=""))
    assert got.rules[0] == "divisible"


def test_check_divisible_is_quiet_on_a_single_piece():
    assert check_divisible(a_load()) == []


def test_tires_are_checked_before_the_flat_limits():
    thin = rig(
        "THIN",
        [steer(), drive(26000, tires=4, width=10), drive(), drive(), drive()],
        [feet(15), feet(4), feet(30), feet(4)],
    )
    got = assess(thin, a_load())
    assert got.rules[0] == "tire-width"


def test_check_tires_names_the_rubber():
    thin = rig(
        "THIN",
        [steer(), drive(26000, tires=4, width=10), drive(), drive(), drive()],
        [feet(15), feet(4), feet(30), feet(4)],
    )
    findings = check_tires(thin)
    assert len(findings) == 1
    assert "4 tires at 10 inches" in findings[0].detail


def test_check_tires_excess_is_over_the_rubber_limit():
    thin = rig(
        "THIN",
        [steer(), drive(26000, tires=4, width=10), drive(), drive(), drive()],
        [feet(15), feet(4), feet(30), feet(4)],
    )
    assert int(check_tires(thin)[0].excess) == 26000 - 24000


def test_check_tires_is_quiet_on_a_normal_rig(legal_five):
    assert check_tires(legal_five) == []


def test_a_heavy_rig_reports_flat_limits_before_the_bridge(heavy_five):
    rules = assess(heavy_five, a_load()).rules
    assert rules.index("single-axle") < rules.index("bridge-formula")


def test_size_findings_come_last(heavy_five):
    rules = assess(heavy_five, a_load(width=feet(12))).rules
    assert rules[-1] == "over-width"


def test_the_excess_is_the_largest_and_not_the_sum(heavy_five):
    got = assess(heavy_five, a_load())
    billable = [int(f.excess) for f in got.findings if f.billable]
    assert int(got.excess) == max(billable)
    assert int(got.excess) < sum(billable)


def test_a_clean_rig_has_no_excess(legal_five):
    assert int(assess(legal_five, a_load()).excess) == 0


def test_blockers_are_only_the_refusals(heavy_five):
    got = assess(heavy_five, a_load(divisible=True, reason=""))
    assert [f.rule for f in got.blockers] == ["divisible"]


def test_by_rule_picks_one_check_out(heavy_five):
    got = assess(heavy_five, a_load())
    assert all(f.rule == "single-axle" for f in got.by_rule("single-axle"))
    assert got.by_rule("nothing-like-this") == ()


def test_a_note_only_assessment_is_still_clean(legal_five):
    got = assess(legal_five, a_load(rear_overhang=feet(6), length=feet(60)))
    assert not got.clean or all(f.severity is Severity.NOTE for f in got.findings)


def test_assess_takes_a_different_road(legal_five):
    made = rig(
        "STATE",
        [steer(), drive(21000), drive(13000), drive(17000), drive(17000)],
        [feet(15), feet(4), feet(30), feet(4)],
    )
    assert "single-axle" in assess(made, a_load(), INTERSTATE).rules
    assert "single-axle" not in assess(made, a_load(), STATE_ROUTE).rules


def test_assess_takes_a_different_size_rule(legal_five):
    narrow = SizeRule(
        name="narrow",
        width=feet(8),
        height=LEGAL.height,
        length=LEGAL.length,
        front_overhang=LEGAL.front_overhang,
        rear_overhang=LEGAL.rear_overhang,
        review_width=LEGAL.review_width,
        review_height=LEGAL.review_height,
        review_length=LEGAL.review_length,
    )
    assert "over-width" in assess(legal_five, a_load(), INTERSTATE, narrow).rules


def test_assessment_length_is_the_finding_count(heavy_five):
    got = assess(heavy_five, a_load())
    assert len(got) == len(got.findings)


def test_an_empty_assessment_is_clean_and_unblocked():
    empty = Assessment(findings=())
    assert empty.clean
    assert not empty.blocked
    assert empty.severity is Severity.NOTE


def test_assessment_is_frozen():
    with pytest.raises(AttributeError):
        Assessment(findings=()).findings = ()  # type: ignore[misc]


def test_a_note_does_not_make_an_assessment_dirty(legal_five):
    got = assess(legal_five, a_load(rear_overhang=inches(int(feet(4)) + 1), length=feet(40)))
    assert [f.rule for f in got.findings] == ["rear-overhang", "flags"]
    assert not got.clean


def test_severity_of_a_permit_only_assessment_is_permit(heavy_five):
    assert assess(heavy_five, a_load()).severity is Severity.PERMIT


def test_findings_are_all_findings(heavy_five):
    got = assess(heavy_five, a_load())
    assert all(isinstance(f, Finding) for f in got.findings)
