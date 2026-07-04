import datetime as dt

import pytest

from jeepdolly.errors import BadValueError, NotAllowedError
from jeepdolly.permit.amendment import (
    CLERICAL,
    MATERIAL,
    MAX_NOTE,
    Amendment,
    Change,
    amend,
    amendable,
    differences,
)
from jeepdolly.permit.application import ANNUAL_DAYS, Kind
from jeepdolly.permit.decision import decide
from jeepdolly.permit.permit import MAX_EXTENSION_DAYS, Permit, issue
from jeepdolly.units.clock import DaySpan
from jeepdolly.units.distance import miles

from .conftest import TRIP, a_load, an_application

DECIDED = dt.date(2025, 6, 17)


def a_permit(**over: object) -> Permit:
    """An issued single trip permit."""
    application = an_application(**over)
    decision = decide(application, (), DECIDED, miles("42.00"))
    return issue("P-000123", decision, DECIDED)  # type: ignore[arg-type]


def test_two_identical_applications_differ_in_nothing():
    assert differences(an_application(), an_application()) == ()


def test_a_moved_span_reads_as_a_date_change():
    later = an_application(span=DaySpan(dt.date(2025, 6, 18), dt.date(2025, 6, 21)))
    assert differences(an_application(), later) == (Change.DATES,)


def test_a_different_destination_reads_as_a_route_change():
    other = an_application(destination="JCT-C")
    assert differences(an_application(), other) == (Change.ROUTE,)


def test_a_heavier_load_reads_as_a_load_change():
    heavy = an_application(load=a_load(weight=160000))
    assert differences(an_application(), heavy) == (Change.LOAD,)


def test_a_different_rig_reads_as_a_rig_change():
    assert differences(an_application(), an_application(rig="R-00002")) == (Change.RIG,)


def test_several_changes_come_back_in_a_fixed_order():
    other = an_application(
        span=DaySpan(dt.date(2025, 6, 18), dt.date(2025, 6, 21)),
        destination="JCT-C",
        rig="R-00002",
    )
    assert differences(an_application(), other) == (Change.DATES, Change.ROUTE, Change.RIG)


def test_something_that_is_not_an_application_is_refused():
    with pytest.raises(BadValueError):
        differences(an_application(), "later")  # type: ignore[arg-type]


def test_a_route_change_is_material():
    assert Change.ROUTE in MATERIAL


def test_a_date_change_is_only_clerical():
    assert Change.DATES in CLERICAL
    assert Change.DATES not in MATERIAL


def test_every_change_is_material_or_clerical():
    assert set(Change) == MATERIAL | CLERICAL


def test_an_amendment_reads_back_what_moved():
    made = amend(a_permit(), an_application(rig="R-00002"), DECIDED)
    assert made.changes == (Change.RIG,)
    assert made.material


def test_a_date_only_amendment_is_clerical():
    later = an_application(span=DaySpan(dt.date(2025, 6, 18), dt.date(2025, 6, 21)))
    assert amend(a_permit(), later, DECIDED).clerical


def test_an_amendment_that_changes_nothing_is_refused():
    with pytest.raises(BadValueError):
        Amendment(
            number="P-000123",  # type: ignore[arg-type]
            was=an_application(),
            now=an_application(),
            filed_on=DECIDED,
        )


def test_a_note_that_runs_long_is_refused():
    with pytest.raises(BadValueError):
        amend(a_permit(), an_application(rig="R-00002"), DECIDED, note="x" * (MAX_NOTE + 1))


def test_a_note_loses_its_extra_spaces():
    made = amend(a_permit(), an_application(rig="R-00002"), DECIDED, note="  swapped  units ")
    assert made.note == "swapped units"


def test_a_datetime_filing_day_is_refused():
    when = dt.datetime(2025, 6, 17, tzinfo=dt.UTC)
    with pytest.raises(BadValueError):
        amend(a_permit(), an_application(rig="R-00002"), when)


def test_an_active_permit_is_amendable_on_its_last_day():
    assert amendable(a_permit(), TRIP.last)


def test_a_permit_that_has_run_out_is_not_amendable():
    assert not amendable(a_permit(), TRIP.last + dt.timedelta(days=1))


def test_a_void_permit_is_not_amendable():
    voided = a_permit().voided("carrier cancelled", DECIDED)
    assert not amendable(voided, TRIP.first)


def test_amending_a_void_permit_is_refused():
    voided = a_permit().voided("carrier cancelled", DECIDED)
    with pytest.raises(NotAllowedError):
        amend(voided, an_application(rig="R-00002"), TRIP.first)


def test_amending_an_expired_permit_is_refused():
    with pytest.raises(NotAllowedError):
        amend(a_permit(), an_application(rig="R-00002"), TRIP.last + dt.timedelta(days=1))


def test_amending_onto_another_carrier_is_refused():
    with pytest.raises(NotAllowedError):
        amend(a_permit(), an_application(carrier="SUMMIT"), DECIDED)


def test_amending_onto_another_kind_of_permit_is_refused():
    start = dt.date(2025, 7, 1)
    year = DaySpan(start, start + dt.timedelta(days=ANNUAL_DAYS - 1))
    annual = an_application(kind=Kind.ANNUAL, span=year, origin=None, destination=None)
    with pytest.raises(NotAllowedError):
        amend(a_permit(), annual, DECIDED)


def test_a_small_stretch_of_the_dates_is_allowed():
    last = TRIP.last + dt.timedelta(days=MAX_EXTENSION_DAYS)
    made = amend(a_permit(), an_application(span=DaySpan(TRIP.first, last)), DECIDED)
    assert made.days_added == MAX_EXTENSION_DAYS


def test_a_long_stretch_of_the_dates_is_refused():
    last = TRIP.last + dt.timedelta(days=MAX_EXTENSION_DAYS + 1)
    with pytest.raises(NotAllowedError):
        amend(a_permit(), an_application(span=DaySpan(TRIP.first, last)), DECIDED)


def test_a_shortened_permit_adds_negative_days():
    shorter = an_application(span=DaySpan(TRIP.first, TRIP.first))
    assert amend(a_permit(), shorter, DECIDED).days_added < 0


def test_filing_before_the_permit_was_issued_is_refused():
    with pytest.raises(BadValueError):
        amend(a_permit(), an_application(rig="R-00002"), DECIDED - dt.timedelta(days=1))


def test_amending_something_that_is_not_a_permit_is_refused():
    with pytest.raises(BadValueError):
        amend("P-000123", an_application(), DECIDED)  # type: ignore[arg-type]


def test_the_printed_line_names_the_permit_and_what_moved():
    line = str(amend(a_permit(), an_application(rig="R-00002"), DECIDED))
    assert "P-000123" in line
    assert "rig" in line
