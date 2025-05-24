import datetime as dt

import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.permit.application import (
    ANNUAL_DAYS,
    MAX_LEAD_DAYS,
    MAX_TRIP_DAYS,
    Kind,
)
from jeepdolly.units.clock import DaySpan

from .conftest import FILED, TRIP, an_application

ANNUAL = DaySpan(dt.date(2025, 7, 1), dt.date(2025, 7, 1) + dt.timedelta(days=ANNUAL_DAYS - 1))


def test_an_application_normalises_its_keys():
    made = an_application(carrier="vance", rig="r-00001")
    assert (made.carrier, made.rig) == ("VANCE", "R-00001")


def test_a_trip_application_is_routed(trip):
    assert trip.routed


def test_a_trip_counts_its_days(trip):
    assert trip.days == 3


def test_a_trip_covers_its_span(trip):
    assert trip.covers(dt.date(2025, 6, 18))
    assert trip.covers(dt.date(2025, 6, 20))
    assert not trip.covers(dt.date(2025, 6, 21))


def test_a_trip_is_not_reviewed(trip):
    assert not trip.reviewed


def test_a_superload_is_reviewed():
    assert an_application(kind=Kind.SUPERLOAD).reviewed


def test_a_superload_still_names_a_route():
    assert an_application(kind=Kind.SUPERLOAD).routed


def test_an_annual_names_no_route():
    made = an_application(kind=Kind.ANNUAL, span=ANNUAL, origin=None, destination=None)
    assert not made.routed


def test_an_annual_runs_a_full_year():
    made = an_application(kind=Kind.ANNUAL, span=ANNUAL, origin=None, destination=None)
    assert made.days == ANNUAL_DAYS


def test_an_annual_refuses_a_shorter_span():
    with pytest.raises(BadValueError):
        an_application(kind=Kind.ANNUAL, span=TRIP, origin=None, destination=None)


def test_an_annual_refuses_a_route():
    with pytest.raises(BadValueError):
        an_application(kind=Kind.ANNUAL, span=ANNUAL)


def test_a_trip_refuses_a_span_that_is_too_long():
    long = DaySpan(TRIP.first, TRIP.first + dt.timedelta(days=MAX_TRIP_DAYS))
    with pytest.raises(BadValueError):
        an_application(span=long)


def test_a_trip_takes_the_longest_span():
    edge = DaySpan(TRIP.first, TRIP.first + dt.timedelta(days=MAX_TRIP_DAYS - 1))
    assert an_application(span=edge).days == MAX_TRIP_DAYS


def test_a_trip_refuses_a_missing_origin():
    with pytest.raises(BadValueError):
        an_application(origin=None)


def test_a_trip_refuses_a_missing_destination():
    with pytest.raises(BadValueError):
        an_application(destination=None)


def test_a_trip_refuses_the_same_junction_at_both_ends():
    with pytest.raises(BadValueError):
        an_application(destination="JCT-A")


def test_an_application_refuses_a_span_before_it_was_filed():
    early = DaySpan(dt.date(2025, 6, 1), dt.date(2025, 6, 2))
    with pytest.raises(BadValueError):
        an_application(span=early)


def test_an_application_may_start_on_the_day_it_is_filed():
    same = DaySpan(FILED, FILED)
    assert an_application(span=same).days == 1


def test_an_application_refuses_a_span_too_far_ahead():
    far = FILED + dt.timedelta(days=MAX_LEAD_DAYS + 1)
    with pytest.raises(BadValueError):
        an_application(span=DaySpan(far, far))


def test_an_application_takes_the_furthest_lead():
    edge = FILED + dt.timedelta(days=MAX_LEAD_DAYS)
    assert an_application(span=DaySpan(edge, edge)).days == 1


def test_an_application_refuses_a_load_that_is_not_one():
    with pytest.raises(BadValueError):
        an_application(load="a transformer")


def test_an_application_refuses_a_span_that_is_not_one():
    with pytest.raises(BadValueError):
        an_application(span="next week")


def test_an_application_refuses_a_filed_date_that_is_a_datetime():
    with pytest.raises(BadValueError):
        an_application(filed_on=dt.datetime(2025, 6, 16, tzinfo=dt.UTC))


def test_an_application_refuses_an_unknown_kind():
    with pytest.raises(ValueError, match="not a valid|trip|annual|superload"):
        an_application(kind="weekly")


def test_a_trip_prints_its_ends(trip):
    assert str(trip) == "VANCE R-00001 trip, JCT-A to JCT-D, 2025-06-18..2025-06-20"


def test_an_annual_prints_that_it_has_no_route():
    made = an_application(kind=Kind.ANNUAL, span=ANNUAL, origin=None, destination=None)
    assert "no fixed route" in str(made)


def test_applications_with_the_same_parts_are_equal(trip):
    assert trip == an_application()


def test_an_application_is_frozen(trip):
    with pytest.raises(AttributeError):
        trip.carrier = "OTHER"
