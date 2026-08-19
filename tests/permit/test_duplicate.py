import datetime as dt

import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.permit.application import ANNUAL_DAYS, Application, Kind
from jeepdolly.permit.duplicate import (
    HEIGHT_SLACK,
    WEIGHT_SLACK,
    Likeness,
    Match,
    duplicates_of,
    likeness,
)
from jeepdolly.units.clock import DaySpan
from jeepdolly.units.length import feet_inches
from jeepdolly.units.mass import pounds
from tests.permit.conftest import TRIP, a_load, an_application

LATER = DaySpan(TRIP.last, TRIP.last + dt.timedelta(days=2))
APART = DaySpan(TRIP.last + dt.timedelta(days=5), TRIP.last + dt.timedelta(days=6))


def an_annual(**over: object) -> Application:
    """An annual application, which names no route at all."""
    start = dt.date(2025, 7, 1)
    year = DaySpan(start, start + dt.timedelta(days=ANNUAL_DAYS - 1))
    kw: dict[str, object] = {
        "kind": Kind.ANNUAL,
        "span": year,
        "origin": None,
        "destination": None,
    }
    kw.update(over)
    return an_application(**kw)


def test_an_application_matches_itself_exactly():
    assert likeness(an_application(), an_application()) is Likeness.SAME


def test_another_carrier_is_a_different_move():
    assert likeness(an_application(), an_application(carrier="SUMMIT")) is Likeness.APART


def test_another_rig_is_a_different_move():
    assert likeness(an_application(), an_application(rig="R-00002")) is Likeness.APART


def test_another_kind_of_permit_is_a_different_move():
    assert likeness(an_application(), an_annual()) is Likeness.APART


def test_days_that_do_not_overlap_are_a_different_move():
    assert likeness(an_application(), an_application(span=APART)) is Likeness.APART


def test_days_that_touch_at_one_end_still_overlap():
    assert likeness(an_application(), an_application(span=LATER)) is not Likeness.APART


def test_another_destination_is_a_different_move():
    assert likeness(an_application(), an_application(destination="JCT-C")) is Likeness.APART


def test_a_rounded_weight_is_still_the_same_move():
    heavier = an_application(load=a_load(weight=pounds(148000 + WEIGHT_SLACK)))
    assert likeness(an_application(), heavier) is Likeness.SAME


def test_a_much_heavier_load_is_only_probably_the_same():
    heavier = an_application(load=a_load(weight=pounds(148000 + WEIGHT_SLACK + 1)))
    assert likeness(an_application(), heavier) is Likeness.CLOSE


def test_a_rounded_width_is_still_the_same_move():
    wider = an_application(load=a_load(width=feet_inches(13, HEIGHT_SLACK - 6)))
    assert likeness(an_application(), wider) is Likeness.SAME


def test_a_much_taller_load_is_only_probably_the_same():
    taller = an_application(load=a_load(height=feet_inches(15, 0)))
    assert likeness(an_application(), taller) is Likeness.CLOSE


def test_two_annuals_for_one_rig_are_the_same_move():
    assert likeness(an_annual(), an_annual()) is Likeness.SAME


def test_next_years_annual_is_a_different_move():
    start = dt.date(2026, 7, 1)
    later = an_annual(
        span=DaySpan(start, start + dt.timedelta(days=ANNUAL_DAYS - 1)),
        filed_on=dt.date(2026, 6, 1),
    )
    assert likeness(an_annual(), later) is Likeness.APART


def test_something_that_is_not_an_application_is_refused():
    with pytest.raises(BadValueError):
        likeness(an_application(), "the same one")  # type: ignore[arg-type]


def test_an_empty_file_turns_up_no_duplicates():
    assert duplicates_of(an_application(), []) == []


def test_a_matching_application_on_file_is_found():
    found = duplicates_of(an_application(), [(1, an_application())])
    assert len(found) == 1
    assert found[0].certain


def test_a_different_move_on_file_is_not_found():
    assert duplicates_of(an_application(), [(1, an_application(carrier="SUMMIT"))]) == []


def test_a_certain_match_comes_before_a_probable_one():
    heavier = an_application(load=a_load(weight=pounds(160000)))
    found = duplicates_of(an_application(), [(1, heavier), (2, an_application())])
    assert [one.key for one in found] == [2, 1]


def test_the_newest_certain_match_comes_first():
    found = duplicates_of(an_application(), [(1, an_application()), (7, an_application())])
    assert [one.key for one in found] == [7, 1]


def test_every_match_carries_the_application_it_found():
    found = duplicates_of(an_application(), [(1, an_application())])
    assert found[0].application.carrier == "VANCE"


def test_a_match_that_is_apart_is_refused():
    with pytest.raises(BadValueError):
        Match(likeness=Likeness.APART, key=1, application=an_application())


def test_a_match_on_key_zero_is_refused():
    with pytest.raises(BadValueError):
        Match(likeness=Likeness.SAME, key=0, application=an_application())


def test_a_match_on_something_that_is_not_an_application_is_refused():
    with pytest.raises(BadValueError):
        Match(likeness=Likeness.SAME, key=1, application="the other one")  # type: ignore[arg-type]


def test_a_probable_match_is_not_certain():
    heavier = an_application(load=a_load(weight=pounds(160000)))
    found = duplicates_of(an_application(), [(1, heavier)])
    assert not found[0].certain


def test_a_match_prints_its_key_and_its_days():
    line = str(duplicates_of(an_application(), [(3, an_application())])[0])
    assert "application 3" in line
    assert "2025" in line
