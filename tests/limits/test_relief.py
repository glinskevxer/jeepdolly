import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.limits.assess import assess
from jeepdolly.limits.finding import Finding, Severity
from jeepdolly.limits.relief import SPREADABLE, Kind, Remedy, remedies_for, remedy_of
from jeepdolly.limits.statute import INTERSTATE
from jeepdolly.rig.load import Load
from jeepdolly.units.length import feet, feet_inches
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


def a_finding(**over: object) -> Finding:
    kw: dict[str, object] = {
        "rule": "single-axle",
        "subject": "axle 4",
        "severity": Severity.PERMIT,
        "detail": "over the limit",
        "excess": pounds(2300),
    }
    kw.update(over)
    return Finding(**kw)  # type: ignore[arg-type]


def test_a_single_axle_overage_says_shed_the_weight():
    made = remedy_of(a_finding(), INTERSTATE)
    assert made.kind is Kind.SHED
    assert "2,300 lb" in made.detail


def test_a_single_axle_remedy_names_the_limit():
    assert "20,000 lb" in remedy_of(a_finding(), INTERSTATE).detail


def test_a_single_axle_remedy_carries_the_weight():
    assert int(remedy_of(a_finding(), INTERSTATE).weight) == 2300


def test_a_tandem_overage_says_spread_the_pair():
    made = remedy_of(a_finding(rule="tandem"), INTERSTATE)
    assert made.kind is Kind.SPREAD
    assert "8'" in made.detail


def test_a_tandem_remedy_carries_the_spread():
    made = remedy_of(a_finding(rule="tandem"), INTERSTATE)
    assert made.length == INTERSTATE.tandem_high


def test_a_bridge_overage_says_add_an_axle():
    made = remedy_of(a_finding(rule="bridge-formula"), INTERSTATE)
    assert made.kind is Kind.SPREAD
    assert "another" in made.detail


def test_a_tire_overage_says_wider_rubber():
    made = remedy_of(a_finding(rule="tire-width"), INTERSTATE)
    assert made.kind is Kind.RUBBER


def test_a_divisible_load_says_split_it():
    made = remedy_of(
        a_finding(rule="divisible", severity=Severity.REFUSE, excess=pounds(0)), INTERSTATE
    )
    assert made.kind is Kind.DISMANTLE
    assert "two trips" in made.detail


def test_a_posted_bridge_says_go_another_way():
    made = remedy_of(
        a_finding(rule="posted-bridge", severity=Severity.REFUSE, excess=pounds(0)),
        INTERSTATE,
    )
    assert made.kind is Kind.REROUTE


def test_a_clearance_says_go_another_way():
    made = remedy_of(
        a_finding(rule="clearance", severity=Severity.REFUSE, excess=pounds(0)), INTERSTATE
    )
    assert made.kind is Kind.REROUTE


def test_a_local_order_says_go_another_way():
    made = remedy_of(
        a_finding(rule="local-order", severity=Severity.REFUSE, excess=pounds(0)), INTERSTATE
    )
    assert made.kind is Kind.REROUTE


def test_a_blocking_over_width_says_engineering():
    made = remedy_of(
        a_finding(rule="over-width", severity=Severity.REFUSE, excess=pounds(0)), INTERSTATE
    )
    assert made.kind is Kind.REVIEW


def test_an_ordinary_over_width_says_the_permit_covers_it():
    made = remedy_of(a_finding(rule="over-width", excess=pounds(0)), INTERSTATE)
    assert made.kind is Kind.NOTHING
    assert "fee" in made.detail


def test_a_rule_with_no_remedy_repeats_the_finding():
    made = remedy_of(a_finding(rule="gross", excess=pounds(0)), INTERSTATE)
    assert made.kind is Kind.NOTHING
    assert made.detail == "over the limit"


def test_every_spreadable_rule_gets_a_remedy_that_moves_weight():
    for rule in SPREADABLE:
        made = remedy_of(a_finding(rule=rule), INTERSTATE)
        assert made.kind in {Kind.SHED, Kind.SPREAD, Kind.RUBBER}


def test_a_remedy_refuses_an_empty_subject():
    with pytest.raises(BadValueError):
        Remedy(kind=Kind.SHED, subject="  ", detail="do something")


def test_a_remedy_refuses_an_empty_detail():
    with pytest.raises(BadValueError):
        Remedy(kind=Kind.SHED, subject="axle 4", detail="")


def test_a_remedy_collapses_whitespace():
    made = Remedy(kind=Kind.SHED, subject="axle 4", detail="shed   weight")
    assert made.detail == "shed weight"


def test_a_remedy_prints_its_subject_and_detail():
    made = Remedy(kind=Kind.SHED, subject="axle 4", detail="shed weight")
    assert str(made) == "axle 4: shed weight"


def test_a_heavy_rig_gets_one_remedy_per_finding():
    heavy = rig(
        "HEAVY",
        [steer(14000), drive(23000), drive(23000), drive(22000), drive(22000)],
        [feet(15), feet(4), feet(30), feet(4)],
    )
    seen = assess(heavy, a_load())
    made = remedies_for(seen, INTERSTATE)
    assert len(made) == len([f for f in seen.findings if f.severity is not Severity.NOTE])


def test_a_note_gets_no_remedy():
    seen = assess(
        rig("PLAIN", [steer(), drive(), drive()], [feet(15), feet(4)]),
        a_load(rear_overhang=feet(6), length=feet(40)),
    )
    assert [f.rule for f in seen.findings] == ["rear-overhang", "flags"]
    assert len(remedies_for(seen, INTERSTATE)) == 1


def test_a_clean_rig_needs_no_remedy():
    clean = rig(
        "CLEAN",
        [steer(), drive(), drive(), drive(), drive()],
        [feet(15), feet(4), feet(30), feet(4)],
    )
    assert remedies_for(assess(clean, a_load()), INTERSTATE) == []


def test_the_remedies_come_out_in_the_findings_order():
    heavy = rig(
        "HEAVY",
        [steer(14000), drive(23000), drive(23000), drive(22000), drive(22000)],
        [feet(15), feet(4), feet(30), feet(4)],
    )
    seen = assess(heavy, a_load())
    made = remedies_for(seen, INTERSTATE)
    wanted = [f.subject for f in seen.findings if f.severity is not Severity.NOTE]
    assert [one.subject for one in made] == wanted
