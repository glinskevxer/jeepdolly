import datetime as dt

import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.party.surety import (
    CALLABLE,
    MAX_INSURER,
    Certificate,
    Cover,
    in_force,
    lapsing,
)
from jeepdolly.units.clock import DaySpan
from jeepdolly.units.money import cents

JAN = dt.date(2025, 1, 1)
JUN = dt.date(2025, 6, 30)
DEC = dt.date(2025, 12, 31)


def a_certificate(**over: object) -> Certificate:
    """A lodged bond with everything filled in, overridable field by field."""
    kw: dict[str, object] = {
        "carrier": "ACME",
        "cover": Cover.BOND,
        "insurer": "Cascade Surety",
        "policy": "SB-4471",
        "amount": cents(100_000_00),
        "span": DaySpan(JAN, DEC),
    }
    kw.update(over)
    return Certificate(**kw)  # type: ignore[arg-type]


def test_a_lodged_bond_reads_back():
    made = a_certificate()
    assert made.carrier == "ACME"
    assert made.cover is Cover.BOND
    assert int(made.amount) == 100_000_00


def test_a_carrier_code_is_normalised():
    assert a_certificate(carrier="acme").carrier == "ACME"


def test_an_insurer_name_loses_its_extra_spaces():
    assert a_certificate(insurer="  Cascade   Surety ").insurer == "Cascade Surety"


def test_an_insurer_name_that_runs_long_is_refused():
    with pytest.raises(BadValueError):
        a_certificate(insurer="x" * (MAX_INSURER + 1))


def test_an_empty_policy_number_is_refused():
    with pytest.raises(BadValueError):
        a_certificate(policy="   ")


def test_a_certificate_for_no_money_is_refused():
    with pytest.raises(BadValueError):
        a_certificate(amount=cents(0))


def test_a_certificate_for_negative_money_is_refused():
    with pytest.raises(BadValueError):
        a_certificate(amount=cents(-1))


def test_something_that_is_not_a_span_is_refused():
    with pytest.raises(BadValueError):
        a_certificate(span=(JAN, DEC))


def test_only_a_bond_can_be_called_by_the_state():
    assert a_certificate().callable_on_default
    assert not a_certificate(cover=Cover.LIABILITY).callable_on_default
    assert {Cover.BOND} == CALLABLE


def test_a_day_inside_the_span_is_in_force():
    assert a_certificate().in_force(JUN)


def test_the_last_day_of_the_span_is_still_in_force():
    assert a_certificate().in_force(DEC)


def test_the_day_after_the_span_is_not_in_force():
    assert not a_certificate().in_force(DEC + dt.timedelta(days=1))


def test_asking_in_force_with_a_datetime_is_refused():
    with pytest.raises(BadValueError):
        a_certificate().in_force(dt.datetime(2025, 6, 30, tzinfo=dt.UTC))


def test_the_last_day_counts_as_one_day_left():
    assert a_certificate().days_left(DEC) == 1


def test_days_left_goes_negative_once_it_has_lapsed():
    assert a_certificate().days_left(DEC + dt.timedelta(days=4)) == -3


def test_the_face_amount_meets_a_smaller_requirement():
    assert a_certificate().covers_at_least(cents(50_000_00))


def test_the_face_amount_meets_a_requirement_it_equals():
    assert a_certificate().covers_at_least(cents(100_000_00))


def test_a_bigger_requirement_is_not_covered():
    assert not a_certificate().covers_at_least(cents(250_000_00))


def test_the_shortfall_is_the_gap_to_the_requirement():
    assert int(a_certificate().shortfall(cents(250_000_00))) == 150_000_00


def test_there_is_no_shortfall_against_a_smaller_requirement():
    assert int(a_certificate().shortfall(cents(1_000_00))) == 0


def test_renewing_keeps_the_cover_and_the_amount():
    fresh = a_certificate().renewed(DaySpan(dt.date(2026, 1, 1), dt.date(2026, 12, 31)))
    assert fresh.cover is Cover.BOND
    assert int(fresh.amount) == 100_000_00
    assert fresh.policy == "SB-4471"


def test_renewing_takes_a_new_policy_number():
    fresh = a_certificate().renewed(DaySpan(JAN, DEC), policy="SB-9000")
    assert fresh.policy == "SB-9000"


def test_only_the_ones_good_that_day_come_back():
    held = [
        a_certificate(),
        a_certificate(
            cover=Cover.CARGO,
            span=DaySpan(dt.date(2024, 1, 1), dt.date(2024, 12, 31)),
        ),
    ]
    assert [one.cover for one in in_force(held, JUN)] == [Cover.BOND]


def test_a_certificate_lapsing_inside_the_window_is_listed():
    held = [a_certificate(span=DaySpan(JAN, JUN))]
    assert lapsing(held, dt.date(2025, 6, 20), 30) == held


def test_one_lapsing_after_the_window_is_left_out():
    assert lapsing([a_certificate()], dt.date(2025, 6, 20), 30) == []


def test_one_that_already_lapsed_is_not_called_lapsing():
    held = [a_certificate(span=DaySpan(dt.date(2024, 1, 1), dt.date(2024, 3, 1)))]
    assert lapsing(held, JUN, 400) == []


def test_the_chase_list_comes_back_soonest_first():
    early = a_certificate(cover=Cover.CARGO, span=DaySpan(JAN, dt.date(2025, 7, 4)))
    late = a_certificate(span=DaySpan(JAN, dt.date(2025, 7, 20)))
    assert lapsing([late, early], JUN, 40) == [early, late]


def test_a_negative_window_is_refused():
    with pytest.raises(BadValueError):
        lapsing([a_certificate()], JUN, -1)


def test_a_window_that_is_not_a_number_is_refused():
    with pytest.raises(BadValueError):
        lapsing([a_certificate()], JUN, True)


def test_the_printed_line_names_the_insurer_and_the_end():
    line = str(a_certificate())
    assert "Cascade Surety" in line
    assert "SB-4471" in line
    assert "2025" in line
