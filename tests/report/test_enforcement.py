import datetime as dt

import pytest

from jeepdolly.enforce.ticket import Discrepancy
from jeepdolly.enforce.violation import Violation
from jeepdolly.errors import BadValueError
from jeepdolly.report.enforcement import (
    Repeat,
    by_kind,
    enforcement_sheet,
    repeats,
    within,
)
from jeepdolly.units.clock import DaySpan
from jeepdolly.units.mass import pounds
from jeepdolly.units.money import cents

JUNE = DaySpan(dt.date(2025, 6, 1), dt.date(2025, 6, 30))
WEIGHED = dt.date(2025, 6, 19)


def a_violation(**over: object) -> Violation:
    kw: dict[str, object] = {
        "on": WEIGHED,
        "ticket": "WT-00001",
        "permit": "P-000123",
        "carrier": "VANCE",
        "kind": Discrepancy.GROSS,
        "over": pounds(4000),
        "penalty": cents(5000),
    }
    kw.update(over)
    return Violation(**kw)  # type: ignore[arg-type]


def test_a_violation_inside_the_period_is_kept():
    assert len(within([a_violation()], JUNE)) == 1


def test_a_violation_outside_the_period_is_dropped():
    assert within([a_violation(on=dt.date(2025, 5, 1))], JUNE) == []


def test_a_violation_on_the_first_day_is_kept():
    assert len(within([a_violation(on=JUNE.first)], JUNE)) == 1


def test_a_violation_on_the_last_day_is_kept():
    assert len(within([a_violation(on=JUNE.last)], JUNE)) == 1


def test_the_period_comes_back_oldest_first():
    early = a_violation(on=dt.date(2025, 6, 2), ticket="WT-00002")
    found = within([a_violation(), early], JUNE)
    assert str(found[0].ticket) == "WT-00002"


def test_something_that_is_not_a_span_is_refused():
    with pytest.raises(BadValueError):
        within([a_violation()], (JUNE.first, JUNE.last))  # type: ignore[arg-type]


def test_nothing_counts_as_nothing_by_kind():
    assert by_kind([]) == {}


def test_two_of_a_kind_count_as_two():
    counted = by_kind([a_violation(), a_violation(ticket="WT-00002")])
    assert counted[Discrepancy.GROSS] == 2


def test_two_kinds_are_counted_apart():
    axle = a_violation(kind=Discrepancy.AXLE)
    counted = by_kind([a_violation(), axle])
    assert counted == {Discrepancy.GROSS: 1, Discrepancy.AXLE: 1}


def test_a_carrier_seen_once_is_not_a_repeat():
    assert repeats([a_violation()]) == []


def test_a_carrier_seen_twice_is_a_repeat():
    found = repeats([a_violation(), a_violation(ticket="WT-00002")])
    assert [one.carrier for one in found] == ["VANCE"]


def test_the_worst_offender_comes_first():
    summit = [a_violation(carrier="SUMMIT", ticket=f"WT-0000{i}") for i in (2, 3, 4)]
    vance = [a_violation(), a_violation(ticket="WT-00005")]
    found = repeats(vance + summit)
    assert found[0].carrier == "SUMMIT"


def test_a_repeat_adds_up_the_penalties():
    found = repeats([a_violation(), a_violation(ticket="WT-00002")])
    assert int(found[0].penalties) == 10000


def test_a_repeat_keeps_the_worst_single_overage():
    heavy = a_violation(ticket="WT-00002", over=pounds(30000))
    found = repeats([a_violation(), heavy])
    assert int(found[0].worst) == 30000


def test_a_higher_threshold_finds_fewer():
    both = [a_violation(), a_violation(ticket="WT-00002")]
    assert repeats(both, 3) == []


def test_a_threshold_of_nothing_is_refused():
    with pytest.raises(BadValueError):
        repeats([a_violation()], 0)


def test_a_repeat_prints_its_count():
    assert "2 violations" in str(
        Repeat(count=2, carrier="VANCE", penalties=cents(1), worst=pounds(1))
    )


def test_one_violation_prints_in_the_singular():
    assert "1 violation," in str(
        Repeat(count=1, carrier="VANCE", penalties=cents(1), worst=pounds(1))
    )


def test_a_quiet_period_says_nothing_was_weighed():
    assert any("nothing weighed" in line for line in enforcement_sheet([], JUNE))


def test_a_period_of_clean_stops_says_so():
    lines = enforcement_sheet([], JUNE, stops=8)
    assert any("8 stops and nothing over" in line for line in lines)


def test_the_sheet_names_the_period():
    assert any("2025" in line for line in enforcement_sheet([], JUNE))


def test_the_sheet_lists_what_was_found():
    body = "\n".join(enforcement_sheet([a_violation()], JUNE))
    assert "VANCE" in body
    assert "P-000123" in body


def test_the_sheet_leaves_out_a_single_offender_table():
    lines = enforcement_sheet([a_violation()], JUNE)
    assert [line for line in lines if line.strip() == "carriers back more than once"] == []


def test_the_sheet_calls_out_a_repeat_offender():
    both = [a_violation(), a_violation(ticket="WT-00002")]
    body = "\n".join(enforcement_sheet(both, JUNE))
    assert "carriers back more than once" in body


def test_the_sheet_totals_the_penalties():
    assert any("penalties" in line for line in enforcement_sheet([a_violation()], JUNE))


def test_the_sheet_counts_the_carriers():
    both = [a_violation(), a_violation(carrier="SUMMIT", ticket="WT-00002")]
    lines = enforcement_sheet(both, JUNE)
    assert any("carriers" in line and "2" in line for line in lines)


def test_the_sheet_breaks_the_count_down_by_kind():
    body = "\n".join(enforcement_sheet([a_violation()], JUNE))
    assert "gross over permit" in body


def test_a_datetime_day_is_refused():
    with pytest.raises(BadValueError):
        enforcement_sheet([], JUNE, on=dt.datetime(2025, 6, 19, tzinfo=dt.UTC))
