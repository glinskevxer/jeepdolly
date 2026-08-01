import datetime as dt

import pytest

from jeepdolly.enforce.ticket import Discrepancy, Overage
from jeepdolly.enforce.violation import (
    CHARGEABLE,
    LOOK_BACK_DAYS,
    PENALTY_BANDS,
    REPEAT_MULTIPLES,
    Violation,
    multiple_for,
    owed,
    penalty_for,
    repeats_within,
    violations_from,
)
from jeepdolly.errors import BadValueError
from jeepdolly.ids.reference import serial
from jeepdolly.units.mass import pounds
from jeepdolly.units.money import cents

WEIGHED = dt.date(2025, 6, 19)
TICKET = serial("WT-00001")
SECOND = serial("WT-00002")
PERMIT = serial("P-000123")


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


def an_overage(**over: object) -> Overage:
    kw: dict[str, object] = {
        "kind": Discrepancy.GROSS,
        "subject": "gross",
        "over": pounds(4000),
    }
    kw.update(over)
    return Overage(**kw)  # type: ignore[arg-type]


def test_a_first_offence_is_charged_once():
    assert multiple_for(0) == 1


def test_a_second_offence_is_charged_twice():
    assert multiple_for(1) == 2


def test_a_fifth_offence_is_charged_at_the_last_step():
    assert multiple_for(4) == REPEAT_MULTIPLES[-1]


def test_a_negative_history_is_refused():
    with pytest.raises(BadValueError):
        multiple_for(-1)


def test_a_history_that_is_not_a_number_is_refused():
    with pytest.raises(BadValueError):
        multiple_for(True)


def test_an_overage_of_nothing_costs_nothing():
    assert int(penalty_for(pounds(0))) == 0


def test_a_two_ton_overage_is_charged_in_the_first_band():
    assert int(penalty_for(pounds(4000))) == 2 * int(PENALTY_BANDS[0].rate)


def test_a_part_ton_is_charged_as_a_whole_ton():
    assert int(penalty_for(pounds(1))) == int(PENALTY_BANDS[0].rate)


def test_the_penalty_climbs_through_the_bands():
    small = int(penalty_for(pounds(4000)))
    large = int(penalty_for(pounds(40000)))
    assert large > small * 5


def test_a_repeat_costs_a_multiple_of_the_first():
    once = int(penalty_for(pounds(4000), 0))
    twice = int(penalty_for(pounds(4000), 1))
    assert twice == once * 2


def test_an_amended_permit_forgives_the_repeat_multiple():
    assert int(penalty_for(pounds(4000), 3, forgiven=True)) == int(penalty_for(pounds(4000)))


def test_an_amended_permit_still_charges_the_pounds():
    assert int(penalty_for(pounds(4000), 3, forgiven=True)) > 0


def test_a_flag_that_is_not_a_boolean_is_refused():
    with pytest.raises(BadValueError):
        penalty_for(pounds(4000), 0, forgiven="yes")  # type: ignore[arg-type]


def test_a_gross_overage_is_chargeable():
    assert Discrepancy.GROSS in CHARGEABLE


def test_a_light_rig_is_not_chargeable():
    assert Discrepancy.UNDER not in CHARGEABLE


def test_a_violation_of_nothing_is_refused():
    with pytest.raises(BadValueError):
        a_violation(over=pounds(0))


def test_a_violation_of_something_not_chargeable_is_refused():
    with pytest.raises(BadValueError):
        a_violation(kind=Discrepancy.UNDER)


def test_a_violation_with_no_carrier_is_refused():
    with pytest.raises(BadValueError):
        a_violation(carrier="  ")


def test_a_negative_penalty_is_refused():
    with pytest.raises(BadValueError):
        a_violation(penalty=cents(-1))


def test_a_datetime_day_is_refused():
    with pytest.raises(BadValueError):
        a_violation(on=dt.datetime(2025, 6, 19, tzinfo=dt.UTC))


def test_a_carrier_code_is_upper_cased():
    assert a_violation(carrier="vance").carrier == "VANCE"


def test_a_violation_today_is_inside_the_window():
    assert a_violation().within(WEIGHED)


def test_a_violation_at_the_edge_of_the_window_still_counts():
    assert a_violation().within(WEIGHED + dt.timedelta(days=LOOK_BACK_DAYS))


def test_a_violation_past_the_window_does_not():
    assert not a_violation().within(WEIGHED + dt.timedelta(days=LOOK_BACK_DAYS + 1))


def test_a_violation_in_the_future_does_not_count():
    assert not a_violation().within(WEIGHED - dt.timedelta(days=1))


def test_a_negative_window_is_refused():
    with pytest.raises(BadValueError):
        a_violation().within(WEIGHED, -1)


def test_a_carrier_with_no_history_has_no_repeats():
    assert repeats_within([], WEIGHED) == 0


def test_a_carrier_with_two_recent_violations_has_two():
    history = [a_violation(), a_violation(on=WEIGHED - dt.timedelta(days=10))]
    assert repeats_within(history, WEIGHED) == 2


def test_an_old_violation_is_out_of_the_window():
    old = a_violation(on=WEIGHED - dt.timedelta(days=LOOK_BACK_DAYS + 1))
    assert repeats_within([old], WEIGHED) == 0


def test_a_datetime_day_is_refused_by_the_look_back():
    with pytest.raises(BadValueError):
        repeats_within([], dt.datetime(2025, 6, 19, tzinfo=dt.UTC))


def test_a_chargeable_overage_becomes_a_violation():
    found = violations_from([an_overage()], TICKET, PERMIT, "VANCE", WEIGHED)
    assert len(found) == 1
    assert found[0].kind is Discrepancy.GROSS


def test_a_light_rig_becomes_no_violation():
    light = an_overage(kind=Discrepancy.UNDER)
    assert violations_from([light], TICKET, PERMIT, "VANCE", WEIGHED) == []


def test_an_axle_count_mismatch_becomes_no_violation():
    counted = an_overage(kind=Discrepancy.COUNT, over=pounds(0))
    assert violations_from([counted], TICKET, PERMIT, "VANCE", WEIGHED) == []


def test_two_overages_on_one_stop_are_charged_at_the_same_multiple():
    axle = an_overage(kind=Discrepancy.AXLE, subject="axle 4")
    found = violations_from(
        [an_overage(), axle],
        TICKET,
        PERMIT,
        "VANCE",
        WEIGHED,
    )
    assert int(found[0].penalty) == int(found[1].penalty)


def test_a_carrier_with_history_is_charged_more():
    history = [a_violation(on=WEIGHED - dt.timedelta(days=30))]
    once = violations_from([an_overage()], TICKET, PERMIT, "VANCE", WEIGHED)
    twice = violations_from(
        [an_overage()],
        SECOND,
        PERMIT,
        "VANCE",
        WEIGHED,
        history,
    )
    assert int(twice[0].penalty) > int(once[0].penalty)


def test_an_amended_permit_wipes_the_history_out():
    history = [a_violation(on=WEIGHED - dt.timedelta(days=30))]
    forgiven = violations_from(
        [an_overage()],
        SECOND,
        PERMIT,
        "VANCE",
        WEIGHED,
        history,
        True,
    )
    plain = violations_from([an_overage()], TICKET, PERMIT, "VANCE", WEIGHED)
    assert int(forgiven[0].penalty) == int(plain[0].penalty)


def test_a_batch_of_violations_adds_up():
    assert int(owed([a_violation(), a_violation()])) == 2 * 5000


def test_an_empty_batch_comes_to_nothing():
    assert int(owed([])) == 0


def test_a_violation_prints_the_carrier_and_the_penalty():
    line = str(a_violation())
    assert "VANCE" in line
    assert "$50.00" in line
