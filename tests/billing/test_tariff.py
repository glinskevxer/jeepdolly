from decimal import Decimal

import pytest

from jeepdolly.billing.tariff import SCHEDULE, Band, FeeLine, Tariff, band_charge
from jeepdolly.errors import BadValueError
from jeepdolly.units.distance import miles
from jeepdolly.units.mass import pounds
from jeepdolly.units.money import cents

BANDS = (
    Band(upper=10, rate=cents(500)),
    Band(upper=25, rate=cents(800)),
    Band(upper=None, rate=cents(1200)),
)


def test_band_charge_of_nothing_is_nothing():
    assert int(band_charge(0, BANDS)) == 0


def test_band_charge_inside_the_first_band():
    assert int(band_charge(4, BANDS)) == 4 * 500


def test_band_charge_at_the_first_edge():
    assert int(band_charge(10, BANDS)) == 10 * 500


def test_band_charge_one_past_the_first_edge():
    assert int(band_charge(11, BANDS)) == 10 * 500 + 800


def test_band_charge_at_the_second_edge():
    assert int(band_charge(25, BANDS)) == 10 * 500 + 15 * 800


def test_band_charge_past_the_last_edge():
    assert int(band_charge(30, BANDS)) == 10 * 500 + 15 * 800 + 5 * 1200


def test_band_charge_climbs_by_one_band_rate_per_ton():
    for tons in range(1, 40):
        step = int(band_charge(tons, BANDS)) - int(band_charge(tons - 1, BANDS))
        assert step in {500, 800, 1200}


def test_band_charge_never_falls():
    previous = 0
    for tons in range(40):
        now = int(band_charge(tons, BANDS))
        assert now >= previous
        previous = now


def test_band_charge_refuses_negative_tons():
    with pytest.raises(BadValueError):
        band_charge(-1, BANDS)


def test_band_charge_refuses_a_bool():
    with pytest.raises(BadValueError):
        band_charge(True, BANDS)


def test_band_charge_refuses_no_bands():
    with pytest.raises(BadValueError):
        band_charge(1, ())


def test_band_charge_refuses_a_last_band_with_an_edge():
    with pytest.raises(BadValueError):
        band_charge(1, (Band(upper=10, rate=cents(500)),))


def test_band_charge_refuses_an_open_band_in_the_middle():
    broken = (Band(upper=None, rate=cents(500)), Band(upper=None, rate=cents(800)))
    with pytest.raises(BadValueError):
        band_charge(1, broken)


def test_band_charge_refuses_edges_that_do_not_climb():
    broken = (
        Band(upper=25, rate=cents(500)),
        Band(upper=10, rate=cents(800)),
        Band(upper=None, rate=cents(1200)),
    )
    with pytest.raises(BadValueError):
        band_charge(1, broken)


def test_a_band_refuses_a_zero_edge():
    with pytest.raises(BadValueError):
        Band(upper=0, rate=cents(500))


def test_a_band_refuses_a_bool_edge():
    with pytest.raises(BadValueError):
        Band(upper=True, rate=cents(500))


def test_a_band_refuses_a_negative_rate():
    with pytest.raises(BadValueError):
        Band(upper=10, rate=cents(-1))


def test_bands_order_by_their_edge():
    assert sorted([BANDS[1], BANDS[0]])[0] is BANDS[0]


def test_mileage_bills_whole_miles():
    assert int(SCHEDULE.mileage(miles("12.00"))) == 12 * 6


def test_mileage_rounds_a_part_mile_up():
    assert int(SCHEDULE.mileage(miles("12.01"))) == 13 * 6


def test_mileage_of_nothing_is_nothing():
    assert int(SCHEDULE.mileage(miles(0))) == 0


def test_overweight_is_zero_at_the_limit():
    assert int(SCHEDULE.overweight(pounds(80000), pounds(80000))) == 0


def test_overweight_charges_a_part_ton_as_a_whole_one():
    assert int(SCHEDULE.overweight(pounds(80001), pounds(80000))) == 500


def test_overweight_agrees_with_the_ton_form():
    assert SCHEDULE.overweight(pounds(100000), pounds(80000)) == SCHEDULE.overweight_tons(10)


def test_escorts_are_charged_each():
    assert int(SCHEDULE.escorts(3)) == 3 * 1500


def test_no_escorts_cost_nothing():
    assert int(SCHEDULE.escorts(0)) == 0


def test_escorts_refuse_a_negative_count():
    with pytest.raises(BadValueError):
        SCHEDULE.escorts(-1)


def test_escorts_refuse_a_bool_count():
    with pytest.raises(BadValueError):
        SCHEDULE.escorts(True)


def test_over_width_is_charged_by_the_foot():
    assert int(SCHEDULE.over_width(4)) == 4000


def test_over_width_takes_a_decimal():
    assert int(SCHEDULE.over_width(Decimal("3.5"))) == 3500


def test_over_height_is_dearer_than_over_width():
    assert int(SCHEDULE.over_height(1)) > int(SCHEDULE.over_width(1))


def test_a_fee_line_collapses_whitespace():
    line = FeeLine(code="MILE", detail="12   miles", amount=cents(72))
    assert line.detail == "12 miles"


def test_a_fee_line_refuses_an_empty_code():
    with pytest.raises(BadValueError):
        FeeLine(code=" ", detail="x", amount=cents(1))


def test_a_fee_line_prints_its_amount():
    line = FeeLine(code="MILE", detail="12 miles", amount=cents(72))
    assert str(line) == "MILE 12 miles $0.72"


def test_a_tariff_refuses_a_negative_rate():
    with pytest.raises(BadValueError):
        Tariff(
            name="odd",
            trip_base=cents(-1),
            annual_base=cents(1),
            superload_base=cents(1),
            per_mile=cents(1),
            per_escort=cents(1),
            per_foot_over_width=cents(1),
            per_foot_over_height=cents(1),
            overweight_bands=BANDS,
        )


def test_a_tariff_refuses_a_broken_band_table():
    with pytest.raises(BadValueError):
        Tariff(
            name="odd",
            trip_base=cents(1),
            annual_base=cents(1),
            superload_base=cents(1),
            per_mile=cents(1),
            per_escort=cents(1),
            per_foot_over_width=cents(1),
            per_foot_over_height=cents(1),
            overweight_bands=(Band(upper=10, rate=cents(1)),),
        )


def test_a_tariff_refuses_an_empty_name():
    with pytest.raises(BadValueError):
        Tariff(
            name=" ",
            trip_base=cents(1),
            annual_base=cents(1),
            superload_base=cents(1),
            per_mile=cents(1),
            per_escort=cents(1),
            per_foot_over_width=cents(1),
            per_foot_over_height=cents(1),
            overweight_bands=BANDS,
        )


def test_the_standing_schedule_charges_an_annual_more_than_a_trip():
    assert int(SCHEDULE.annual_base) > int(SCHEDULE.trip_base)
