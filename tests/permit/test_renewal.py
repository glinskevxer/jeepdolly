import datetime as dt

import pytest

from jeepdolly.errors import BadValueError, NotAllowedError
from jeepdolly.permit.application import ANNUAL_DAYS, Kind
from jeepdolly.permit.decision import decide
from jeepdolly.permit.permit import Permit, issue
from jeepdolly.permit.renewal import RENEW_WINDOW, renew, renewable
from jeepdolly.units.clock import DaySpan
from jeepdolly.units.distance import miles

from .conftest import TRIP, an_application

DECIDED = dt.date(2025, 6, 17)
YEAR = DaySpan(dt.date(2025, 7, 1), dt.date(2025, 7, 1) + dt.timedelta(days=ANNUAL_DAYS - 1))


def a_permit(**over: object) -> Permit:
    """An issued single trip permit."""
    application = an_application(**over)
    decision = decide(application, (), DECIDED, miles("42.00"))
    return issue("P-000123", decision, DECIDED)  # type: ignore[arg-type]


def an_annual() -> Permit:
    """An issued annual permit."""
    application = an_application(
        kind=Kind.ANNUAL,
        span=YEAR,
        origin=None,
        destination=None,
        filed_on=dt.date(2025, 6, 16),
    )
    decision = decide(application, (), DECIDED)
    return issue("P-000200", decision, DECIDED)  # type: ignore[arg-type]


def test_a_permit_inside_the_window_is_renewable():
    assert renewable(a_permit(), TRIP.last)


def test_a_permit_well_before_the_window_is_not():
    early = TRIP.last - dt.timedelta(days=RENEW_WINDOW + 1)
    assert not renewable(a_permit(), early)


def test_a_permit_exactly_at_the_window_edge_is_renewable():
    edge = TRIP.last - dt.timedelta(days=RENEW_WINDOW)
    assert renewable(a_permit(), edge)


def test_a_permit_that_has_run_out_is_still_renewable():
    assert renewable(a_permit(), TRIP.last + dt.timedelta(days=30))


def test_a_void_permit_is_not_renewable():
    gone = a_permit().voided("cancelled", DECIDED)
    assert not renewable(gone, TRIP.last)


def test_a_renewal_starts_the_day_after_the_old_one_ends():
    made = renew(a_permit(), TRIP.last)
    assert made.span.first == TRIP.last + dt.timedelta(days=1)


def test_a_renewal_runs_the_same_length_as_a_trip():
    made = renew(a_permit(), TRIP.last)
    assert made.span.days == TRIP.days


def test_an_annual_renewal_runs_a_full_year():
    made = renew(an_annual(), YEAR.last)
    assert made.span.days == ANNUAL_DAYS


def test_a_renewal_carries_the_rig_across():
    made = renew(a_permit(), TRIP.last)
    assert made.application.rig == a_permit().application.rig


def test_a_renewal_carries_the_load_across():
    made = renew(a_permit(), TRIP.last)
    assert made.application.load == a_permit().application.load


def test_a_renewal_carries_the_route_across():
    made = renew(a_permit(), TRIP.last)
    assert made.application.origin == "JCT-A"
    assert made.application.destination == "JCT-D"


def test_an_annual_renewal_carries_no_route():
    made = renew(an_annual(), YEAR.last)
    assert made.application.origin is None


def test_a_renewal_is_filed_on_the_day_it_is_taken():
    made = renew(a_permit(), TRIP.last)
    assert made.application.filed_on == TRIP.last


def test_a_renewal_leaves_no_gap_by_default():
    assert renew(a_permit(), TRIP.last).gap == 0


def test_a_renewal_may_be_asked_to_start_later():
    later = TRIP.last + dt.timedelta(days=5)
    made = renew(a_permit(), TRIP.last, first=later)
    assert made.span.first == later
    assert made.gap == 4


def test_a_renewal_may_not_overlap_the_permit_it_replaces():
    with pytest.raises(BadValueError):
        renew(a_permit(), TRIP.last, first=TRIP.last)


def test_a_renewal_too_early_is_refused():
    early = TRIP.last - dt.timedelta(days=RENEW_WINDOW + 1)
    with pytest.raises(NotAllowedError):
        renew(a_permit(), early)


def test_a_void_permit_may_not_be_renewed():
    gone = a_permit().voided("cancelled", DECIDED)
    with pytest.raises(NotAllowedError):
        renew(gone, TRIP.last)


def test_a_superseded_permit_may_not_be_renewed():
    old = a_permit().superseded_by("P-000124")  # type: ignore[arg-type]
    with pytest.raises(NotAllowedError):
        renew(old, TRIP.last)


def test_a_datetime_is_refused():
    with pytest.raises(BadValueError):
        renew(a_permit(), dt.datetime(2025, 6, 20, tzinfo=dt.UTC))


def test_a_renewal_prints_what_it_replaces():
    made = renew(a_permit(), TRIP.last)
    assert str(made).startswith("P-000123 renewed as")


def test_the_window_is_about_six_weeks():
    assert 30 <= RENEW_WINDOW <= 60
