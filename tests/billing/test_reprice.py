import datetime as dt

import pytest

from jeepdolly.billing.invoice import Invoice, price
from jeepdolly.billing.reprice import (
    AMEND_CODE,
    CREDIT_CODE,
    DIFFERENCE_CODE,
    Reprice,
    day_credit,
    reprice,
)
from jeepdolly.billing.tariff import SCHEDULE, FeeLine
from jeepdolly.errors import BadValueError
from jeepdolly.permit.application import ANNUAL_DAYS, Kind
from jeepdolly.units.clock import DaySpan
from jeepdolly.units.distance import miles
from jeepdolly.units.mass import pounds
from jeepdolly.units.money import cents
from tests.permit.conftest import TRIP, an_application

LONGER = DaySpan(TRIP.first, TRIP.last + dt.timedelta(days=2))
SHORTER = DaySpan(TRIP.first, TRIP.first)


def an_invoice(**over: object) -> Invoice:
    """A priced single trip permit, with the pricing inputs overridable."""
    kw: dict[str, object] = {
        "application": an_application(),
        "excess": pounds(0),
        "distance": miles("42.00"),
    }
    kw.update(over)
    return price(**kw)  # type: ignore[arg-type]


def a_reprice(**over: object) -> Reprice:
    """A material amendment that repriced to the same figure."""
    kw: dict[str, object] = {
        "was": an_application(),
        "now": an_application(rig="R-00002"),
        "was_invoice": an_invoice(),
        "now_invoice": an_invoice(),
        "material": True,
    }
    kw.update(over)
    return reprice(**kw)  # type: ignore[arg-type]


def test_the_schedule_carries_an_amendment_fee():
    assert int(SCHEDULE.amendment_fee) > 0


def test_a_clerical_amendment_charges_the_handling_fee_alone():
    made = a_reprice(material=False)
    assert made.codes == (AMEND_CODE,)
    assert int(made.due) == int(SCHEDULE.amendment_fee)


def test_a_clerical_amendment_leaves_the_permit_total_alone():
    made = a_reprice(material=False, now_invoice=an_invoice(distance=miles("400.00")))
    assert made.was_total == made.now_total


def test_a_material_amendment_that_prices_the_same_charges_handling_only():
    assert a_reprice().codes == (AMEND_CODE,)


def test_a_costlier_amendment_bills_the_difference():
    made = a_reprice(now_invoice=an_invoice(distance=miles("400.00")))
    assert DIFFERENCE_CODE in made.codes
    assert not made.refund


def test_the_difference_is_the_gap_and_not_the_new_total():
    dearer = an_invoice(distance=miles("400.00"))
    made = a_reprice(now_invoice=dearer)
    gap = int(dearer.total) - int(an_invoice().total)
    assert int(made.due) == gap + int(SCHEDULE.amendment_fee)


def test_a_cheaper_amendment_gives_money_back():
    dear = an_invoice(distance=miles("900.00"))
    made = a_reprice(was_invoice=dear, now_invoice=an_invoice())
    assert made.refund


def test_the_refund_never_takes_back_the_writing_fee():
    dear = an_invoice(distance=miles("900.00"))
    made = a_reprice(was_invoice=dear, now_invoice=an_invoice())
    kept = int(dear.total) + int(made.due) - int(SCHEDULE.amendment_fee)
    assert kept >= int(SCHEDULE.trip_base)


def test_a_permit_already_at_the_base_fee_gets_nothing_back():
    cheap = price(an_application(), pounds(0), miles("0.10"))
    made = a_reprice(was_invoice=cheap, now_invoice=cheap)
    assert made.codes == (AMEND_CODE,)


def test_giving_back_days_is_worth_a_share_of_what_was_paid():
    was = an_application()
    now = an_application(span=SHORTER)
    paid = cents(300_00)
    assert int(day_credit(was, now, paid)) == 200_00


def test_giving_back_no_days_is_worth_nothing():
    assert int(day_credit(an_application(), an_application(), cents(300_00))) == 0


def test_stretching_the_dates_is_worth_nothing_back():
    longer = an_application(span=LONGER)
    assert int(day_credit(an_application(), longer, cents(300_00))) == 0


def test_an_annual_never_gives_days_back():
    start = dt.date(2025, 7, 1)
    year = DaySpan(start, start + dt.timedelta(days=ANNUAL_DAYS - 1))
    annual = an_application(kind=Kind.ANNUAL, span=year, origin=None, destination=None)
    assert int(day_credit(annual, annual, cents(500_00))) == 0


def test_the_day_share_rounds_down():
    was = an_application()
    now = an_application(span=SHORTER)
    assert int(day_credit(was, now, cents(100))) == 66


def test_a_shortened_permit_that_prices_the_same_gives_days_back():
    made = a_reprice(now=an_application(span=SHORTER))
    assert CREDIT_CODE in made.codes


def test_the_day_credit_stands_down_when_the_reprice_already_settled():
    made = a_reprice(
        now=an_application(span=SHORTER),
        now_invoice=an_invoice(distance=miles("400.00")),
    )
    assert CREDIT_CODE not in made.codes


def test_something_that_is_not_an_application_is_refused():
    with pytest.raises(BadValueError):
        day_credit("trip", an_application(), cents(1))  # type: ignore[arg-type]


def test_something_that_is_not_an_invoice_is_refused():
    with pytest.raises(BadValueError):
        a_reprice(was_invoice="paid")


def test_a_flag_that_is_not_a_boolean_is_refused():
    with pytest.raises(BadValueError):
        a_reprice(material="yes")


def test_a_reprice_with_no_lines_is_refused():
    with pytest.raises(BadValueError):
        Reprice(lines=(), was_total=cents(1), now_total=cents(1))


def test_a_reprice_with_two_lines_alike_is_refused():
    line = FeeLine(code=AMEND_CODE, detail="x", amount=cents(1))
    with pytest.raises(BadValueError):
        Reprice(lines=(line, line), was_total=cents(1), now_total=cents(1))


def test_a_refund_prints_as_a_refund():
    dear = an_invoice(distance=miles("900.00"))
    made = a_reprice(was_invoice=dear, now_invoice=an_invoice())
    assert "refund" in str(made)


def test_a_charge_prints_as_due():
    assert "due" in str(a_reprice())
