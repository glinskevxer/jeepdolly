import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.limits.dimension import FLAG_OVERHANG, LEGAL, SizeRule, check_size, needs_flags
from jeepdolly.limits.finding import Finding, Severity
from jeepdolly.rig.load import Load
from jeepdolly.units.length import feet, feet_inches, inches
from jeepdolly.units.mass import pounds


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


def rules_of(findings: list[Finding]) -> list[str]:
    """The rule name of each finding, in order."""
    return [f.rule for f in findings]


def test_a_legal_load_produces_nothing():
    assert check_size(a_load()) == []


def test_one_inch_over_width_is_a_permit():
    findings = check_size(a_load(width=feet_inches(8, 7)))
    assert rules_of(findings) == ["over-width"]
    assert findings[0].severity is Severity.PERMIT


def test_a_very_wide_load_goes_to_review():
    findings = check_size(a_load(width=feet(17)))
    assert findings[0].severity is Severity.REFUSE


def test_a_load_exactly_at_the_review_width_is_still_a_permit():
    findings = check_size(a_load(width=LEGAL.review_width))
    assert findings[0].severity is Severity.PERMIT


def test_over_height_is_reported():
    findings = check_size(a_load(height=feet(14)))
    assert rules_of(findings) == ["over-height"]


def test_a_very_tall_load_goes_to_review():
    findings = check_size(a_load(height=feet(17)))
    assert findings[0].severity is Severity.REFUSE


def test_over_length_counts_the_overhangs():
    findings = check_size(a_load(length=feet(70), rear_overhang=feet(8)))
    assert "over-length" in rules_of(findings)


def test_length_under_the_limit_with_overhang_is_clean():
    assert check_size(a_load(length=feet(70), rear_overhang=feet(4))) == []


def test_front_overhang_is_reported():
    findings = check_size(a_load(front_overhang=feet(5)))
    assert "front-overhang" in rules_of(findings)


def test_rear_overhang_is_reported():
    findings = check_size(a_load(rear_overhang=feet(6)))
    assert "rear-overhang" in rules_of(findings)


def test_rear_overhang_at_the_limit_needs_no_flags():
    assert not needs_flags(a_load(rear_overhang=FLAG_OVERHANG))


def test_rear_overhang_past_the_limit_needs_flags():
    assert needs_flags(a_load(rear_overhang=inches(int(FLAG_OVERHANG) + 1)))


def test_the_flag_finding_is_only_a_note():
    findings = check_size(a_load(rear_overhang=feet(6)))
    flags = [f for f in findings if f.rule == "flags"]
    assert len(flags) == 1
    assert flags[0].severity is Severity.NOTE


def test_a_note_carries_no_excess():
    findings = check_size(a_load(rear_overhang=feet(6)))
    assert all(int(f.excess) == 0 for f in findings)


def test_findings_come_out_width_then_height_then_length():
    findings = check_size(a_load(width=feet(10), height=feet(14), length=feet(90)))
    assert rules_of(findings) == ["over-width", "over-height", "over-length"]


def test_a_size_rule_refuses_a_review_limit_under_the_plain_one():
    with pytest.raises(BadValueError):
        SizeRule(
            name="odd",
            width=feet(10),
            height=feet(14),
            length=feet(75),
            front_overhang=feet(3),
            rear_overhang=feet(4),
            review_width=feet(9),
            review_height=feet(16),
            review_length=feet(120),
        )


def test_a_size_rule_refuses_an_empty_name():
    with pytest.raises(BadValueError):
        SizeRule(
            name=" ",
            width=feet(10),
            height=feet(14),
            length=feet(75),
            front_overhang=feet(3),
            rear_overhang=feet(4),
            review_width=feet(16),
            review_height=feet(16),
            review_length=feet(120),
        )


def test_the_legal_rule_is_eight_six_by_thirteen_six():
    assert int(LEGAL.width) == 102
    assert int(LEGAL.height) == 162


def test_check_size_takes_a_rule_of_its_own():
    narrow = SizeRule(
        name="narrow",
        width=feet(8),
        height=feet_inches(13, 6),
        length=feet(75),
        front_overhang=feet(3),
        rear_overhang=feet(4),
        review_width=feet(16),
        review_height=feet(16),
        review_length=feet(120),
    )
    assert check_size(a_load(width=feet(8)), narrow) == []
    assert rules_of(check_size(a_load(), narrow)) == ["over-width"]


def test_the_width_finding_names_both_numbers():
    findings = check_size(a_load(width=feet(12)))
    assert "12'" in findings[0].detail
    assert "8'6\"" in findings[0].detail


def test_a_review_finding_says_so():
    findings = check_size(a_load(height=feet(18)))
    assert "engineering review" in findings[0].detail
