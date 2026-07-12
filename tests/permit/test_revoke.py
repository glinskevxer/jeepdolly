import datetime as dt

import pytest

from jeepdolly.billing.tariff import SCHEDULE
from jeepdolly.errors import BadValueError, NotAllowedError
from jeepdolly.permit.decision import decide
from jeepdolly.permit.permit import Permit, State, issue
from jeepdolly.permit.revoke import (
    BLOCK_DAYS,
    FULL_REFUND,
    MAX_DETAIL,
    NO_REFUND,
    Cause,
    Revocation,
    blocked_on,
    refund_due,
    revoke,
)
from jeepdolly.units.distance import miles
from jeepdolly.units.money import cents
from tests.permit.conftest import TRIP, an_application

DECIDED = dt.date(2025, 6, 17)
BEFORE = dt.date(2025, 6, 17)
DURING = TRIP.first


def a_permit(**over: object) -> Permit:
    """An issued single trip permit."""
    application = an_application(**over)
    decision = decide(application, (), DECIDED, miles("400.00"))
    return issue("P-000123", decision, DECIDED)  # type: ignore[arg-type]


def a_revocation(**over: object) -> Revocation:
    """A recorded revocation, field by field overridable."""
    kw: dict[str, object] = {
        "number": "P-000123",
        "cause": Cause.CANCELLED,
        "on": BEFORE,
        "refunded": cents(0),
        "detail": "",
    }
    kw.update(over)
    return Revocation(**kw)  # type: ignore[arg-type]


def test_every_cause_falls_into_one_treatment():
    for cause in Cause:
        buckets = sum(cause in group for group in (FULL_REFUND, NO_REFUND))
        assert buckets <= 1


def test_an_office_error_gives_the_whole_fee_back():
    permit = a_permit()
    assert int(refund_due(permit, Cause.OFFICE_ERROR, BEFORE)) == int(permit.fee)


def test_a_closed_route_gives_the_whole_fee_back():
    permit = a_permit()
    assert int(refund_due(permit, Cause.ROUTE_CLOSED, BEFORE)) == int(permit.fee)


def test_an_office_error_refunds_even_once_the_move_started():
    permit = a_permit()
    assert int(refund_due(permit, Cause.OFFICE_ERROR, DURING)) == int(permit.fee)


def test_an_undeclared_load_gives_nothing_back():
    assert int(refund_due(a_permit(), Cause.FALSE_LOAD, BEFORE)) == 0


def test_an_unsafe_move_gives_nothing_back():
    assert int(refund_due(a_permit(), Cause.UNSAFE_MOVE, BEFORE)) == 0


def test_cancelling_early_keeps_the_writing_fee():
    permit = a_permit()
    back = refund_due(permit, Cause.CANCELLED, BEFORE)
    assert int(back) == int(permit.fee) - int(SCHEDULE.trip_base)


def test_cancelling_once_the_permit_is_good_gives_nothing_back():
    assert int(refund_due(a_permit(), Cause.CANCELLED, DURING)) == 0


def test_a_rig_that_failed_inspection_is_treated_as_a_cancellation():
    permit = a_permit()
    early = refund_due(permit, Cause.RIG_FAILED, BEFORE)
    assert int(early) == int(permit.fee) - int(SCHEDULE.trip_base)


def test_a_refund_never_goes_below_nothing():
    cheap = a_permit()
    assert int(refund_due(cheap, Cause.CANCELLED, BEFORE)) >= 0


def test_a_datetime_day_is_refused():
    with pytest.raises(BadValueError):
        refund_due(a_permit(), Cause.CANCELLED, dt.datetime(2025, 6, 17, tzinfo=dt.UTC))


def test_something_that_is_not_a_permit_is_refused():
    with pytest.raises(BadValueError):
        refund_due("P-000123", Cause.CANCELLED, BEFORE)  # type: ignore[arg-type]


def test_revoking_voids_the_permit():
    pulled, _ = revoke(a_permit(), Cause.CANCELLED, BEFORE)
    assert pulled.state is State.VOID


def test_the_void_reason_is_the_cause():
    pulled, _ = revoke(a_permit(), Cause.ROUTE_CLOSED, BEFORE)
    assert pulled.reason == str(Cause.ROUTE_CLOSED)


def test_revoking_records_what_went_back():
    permit = a_permit()
    _, made = revoke(permit, Cause.OFFICE_ERROR, BEFORE)
    assert int(made.refunded) == int(permit.fee)


def test_revoking_a_void_permit_is_refused():
    pulled, _ = revoke(a_permit(), Cause.CANCELLED, BEFORE)
    with pytest.raises(NotAllowedError):
        revoke(pulled, Cause.CANCELLED, BEFORE)


def test_revoking_something_that_is_not_a_permit_is_refused():
    with pytest.raises(BadValueError):
        revoke("P-000123", Cause.CANCELLED, BEFORE)  # type: ignore[arg-type]


def test_an_undeclared_load_counts_against_the_carrier():
    assert a_revocation(cause=Cause.FALSE_LOAD, detail="steel not a transformer").at_fault


def test_a_cancellation_does_not_count_against_the_carrier():
    assert not a_revocation().at_fault


def test_an_at_fault_revocation_needs_a_detail():
    with pytest.raises(BadValueError):
        a_revocation(cause=Cause.UNSAFE_MOVE)


def test_a_detail_that_runs_long_is_refused():
    with pytest.raises(BadValueError):
        a_revocation(detail="x" * (MAX_DETAIL + 1))


def test_a_negative_refund_is_refused():
    with pytest.raises(BadValueError):
        a_revocation(refunded=cents(-1))


def test_an_at_fault_revocation_blocks_for_the_stated_run():
    made = a_revocation(cause=Cause.FALSE_LOAD, detail="steel")
    assert made.blocks_until == BEFORE + dt.timedelta(days=BLOCK_DAYS)


def test_an_ordinary_revocation_blocks_nothing():
    assert a_revocation().blocks_until is None


def test_the_last_blocked_day_still_blocks():
    made = a_revocation(cause=Cause.FALSE_LOAD, detail="steel")
    assert made.blocks_on(BEFORE + dt.timedelta(days=BLOCK_DAYS))


def test_the_day_after_the_block_does_not():
    made = a_revocation(cause=Cause.FALSE_LOAD, detail="steel")
    assert not made.blocks_on(BEFORE + dt.timedelta(days=BLOCK_DAYS + 1))


def test_a_day_before_the_revocation_is_not_blocked():
    made = a_revocation(cause=Cause.FALSE_LOAD, detail="steel")
    assert not made.blocks_on(BEFORE - dt.timedelta(days=1))


def test_a_carrier_with_nothing_against_it_is_not_blocked():
    assert blocked_on([], BEFORE) is None


def test_a_carrier_with_an_at_fault_revocation_is_blocked():
    made = a_revocation(cause=Cause.FALSE_LOAD, detail="steel")
    assert blocked_on([made], BEFORE) is made


def test_the_longest_running_block_is_the_one_reported():
    early = a_revocation(cause=Cause.FALSE_LOAD, detail="steel", on=BEFORE)
    late = a_revocation(
        cause=Cause.UNSAFE_MOVE, detail="no escorts", on=BEFORE + dt.timedelta(days=10)
    )
    assert blocked_on([early, late], BEFORE + dt.timedelta(days=20)) is late


def test_an_ordinary_revocation_blocks_nobody():
    assert blocked_on([a_revocation()], BEFORE) is None


def test_a_revocation_prints_its_cause_and_day():
    line = str(a_revocation())
    assert "P-000123" in line
    assert "carrier cancelled" in line
