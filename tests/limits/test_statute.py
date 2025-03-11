import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.limits.statute import (
    INTERSTATE,
    STATE_ROUTE,
    Statute,
    check_statute,
    tandem_runs,
)
from jeepdolly.units.length import feet, inches
from jeepdolly.units.mass import pounds

from .conftest import drive, rig, steer


def test_interstate_carries_the_federal_numbers():
    assert int(INTERSTATE.single) == 20000
    assert int(INTERSTATE.tandem) == 34000
    assert int(INTERSTATE.gross) == 80000


def test_state_route_runs_a_heavier_single_axle():
    assert int(STATE_ROUTE.single) > int(INTERSTATE.single)


def test_statute_refuses_a_tandem_below_the_single():
    with pytest.raises(BadValueError):
        Statute(
            name="odd",
            single=pounds(20000),
            tandem=pounds(19000),
            gross=pounds(80000),
            tandem_low=inches(40),
            tandem_high=inches(96),
        )


def test_statute_refuses_a_gross_below_the_tandem():
    with pytest.raises(BadValueError):
        Statute(
            name="odd",
            single=pounds(20000),
            tandem=pounds(34000),
            gross=pounds(30000),
            tandem_low=inches(40),
            tandem_high=inches(96),
        )


def test_statute_refuses_a_backwards_tandem_bracket():
    with pytest.raises(BadValueError):
        Statute(
            name="odd",
            single=pounds(20000),
            tandem=pounds(34000),
            gross=pounds(80000),
            tandem_low=inches(96),
            tandem_high=inches(40),
        )


def test_statute_refuses_an_empty_name():
    with pytest.raises(BadValueError):
        Statute(
            name="  ",
            single=pounds(20000),
            tandem=pounds(34000),
            gross=pounds(80000),
            tandem_low=inches(40),
            tandem_high=inches(96),
        )


def test_a_pair_inside_the_bracket_is_a_tandem(legal_five):
    assert INTERSTATE.is_tandem(legal_five.run(1, 2))


def test_a_pair_too_close_is_not_a_tandem():
    tight = rig("TIGHT", [steer(), drive(), drive()], [feet(15), inches(36)])
    assert not INTERSTATE.is_tandem(tight.run(1, 2))


def test_a_pair_too_far_apart_is_not_a_tandem(legal_five):
    assert not INTERSTATE.is_tandem(legal_five.run(2, 3))


def test_a_pair_exactly_at_the_low_end_is_a_tandem():
    made = rig("EDGE", [steer(), drive(), drive()], [feet(15), inches(40)])
    assert INTERSTATE.is_tandem(made.run(1, 2))


def test_a_pair_exactly_at_the_high_end_is_a_tandem():
    made = rig("EDGE", [steer(), drive(), drive()], [feet(15), inches(96)])
    assert INTERSTATE.is_tandem(made.run(1, 2))


def test_a_single_axle_is_not_a_tandem(legal_five):
    assert not INTERSTATE.is_tandem(legal_five.run(1, 1))


def test_three_axles_are_not_a_tandem(legal_five):
    assert not INTERSTATE.is_tandem(legal_five.run(1, 3))


def test_the_state_bracket_is_wider(legal_five):
    wide = rig("WIDE", [steer(), drive(), drive()], [feet(15), inches(104)])
    assert not INTERSTATE.is_tandem(wide.run(1, 2))
    assert STATE_ROUTE.is_tandem(wide.run(1, 2))


def test_flat_limit_of_a_single_axle(legal_five):
    assert INTERSTATE.flat_limit(legal_five.run(1, 1)) == INTERSTATE.single


def test_flat_limit_of_a_tandem(legal_five):
    assert INTERSTATE.flat_limit(legal_five.run(1, 2)) == INTERSTATE.tandem


def test_flat_limit_of_a_wide_pair_is_none(legal_five):
    assert INTERSTATE.flat_limit(legal_five.run(2, 3)) is None


def test_flat_limit_of_three_axles_is_none(legal_five):
    assert INTERSTATE.flat_limit(legal_five.run(1, 3)) is None


def test_tandem_runs_finds_both_tandems(legal_five):
    found = [(r.first, r.last) for r in tandem_runs(legal_five, INTERSTATE)]
    assert found == [(1, 2), (3, 4)]


def test_a_legal_rig_produces_no_findings(legal_five):
    assert check_statute(legal_five, INTERSTATE) == []


def test_a_heavy_rig_reports_every_single_axle(heavy_five):
    rules = [f.rule for f in check_statute(heavy_five, INTERSTATE)]
    assert rules.count("single-axle") == 4


def test_the_steer_axle_under_the_limit_is_not_reported(heavy_five):
    subjects = [f.subject for f in check_statute(heavy_five, INTERSTATE)]
    assert "axle 1" not in subjects


def test_a_heavy_rig_reports_both_tandems(heavy_five):
    rules = [f.rule for f in check_statute(heavy_five, INTERSTATE)]
    assert rules.count("tandem") == 2


def test_a_heavy_rig_reports_the_gross(heavy_five):
    gross = [f for f in check_statute(heavy_five, INTERSTATE) if f.rule == "gross"]
    assert len(gross) == 1
    assert int(gross[0].excess) == 104000 - 80000


def test_the_single_axle_excess_is_the_difference(heavy_five):
    single = [f for f in check_statute(heavy_five, INTERSTATE) if f.rule == "single-axle"]
    assert int(single[0].excess) == 3000


def test_findings_come_out_singles_then_tandems_then_gross(heavy_five):
    rules = [f.rule for f in check_statute(heavy_five, INTERSTATE)]
    assert rules == ["single-axle"] * 4 + ["tandem"] * 2 + ["gross"]


def test_a_rig_exactly_at_the_limits_is_clean():
    exact = rig(
        "EXACT",
        [steer(12000), drive(17000), drive(17000), drive(17000), drive(17000)],
        [feet(15), feet(4), feet(30), feet(4)],
    )
    assert check_statute(exact, INTERSTATE) == []


def test_one_pound_over_the_gross_is_reported():
    over = rig(
        "OVER",
        [steer(12001), drive(17000), drive(17000), drive(17000), drive(17000)],
        [feet(15), feet(4), feet(30), feet(4)],
    )
    findings = check_statute(over, INTERSTATE)
    assert [f.rule for f in findings] == ["gross"]
    assert int(findings[0].excess) == 1


def test_the_state_route_set_forgives_a_single_axle_the_interstate_does_not():
    made = rig(
        "STATE",
        [steer(), drive(21000), drive(13000), drive(17000), drive(17000)],
        [feet(15), feet(4), feet(30), feet(4)],
    )
    assert [f.rule for f in check_statute(made, INTERSTATE)] == ["single-axle"]
    assert check_statute(made, STATE_ROUTE) == []
