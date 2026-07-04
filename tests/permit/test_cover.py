import datetime as dt

import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.party.surety import Certificate, Cover
from jeepdolly.permit.application import Kind
from jeepdolly.permit.cover import (
    ESCORT_COVER,
    REQUIRED,
    Gap,
    Requirement,
    clear_to_issue,
    gaps,
    requirements,
)
from jeepdolly.units.clock import DaySpan
from jeepdolly.units.money import cents

JAN = dt.date(2025, 1, 1)
JUN = dt.date(2025, 6, 30)
DEC = dt.date(2025, 12, 31)


def a_certificate(**over: object) -> Certificate:
    kw: dict[str, object] = {
        "carrier": "VANCE",
        "cover": Cover.BOND,
        "insurer": "Cascade Surety",
        "policy": "SB-4471",
        "amount": cents(100_000_00),
        "span": DaySpan(JAN, DEC),
    }
    kw.update(over)
    return Certificate(**kw)  # type: ignore[arg-type]


def a_full_set(over: dict[Cover, int] | None = None) -> list[Certificate]:
    """Enough paper for any permit the office writes, overridable per cover."""
    amounts: dict[Cover, int] = {
        Cover.BOND: 250_000_00,
        Cover.LIABILITY: 5_000_000_00,
        Cover.CARGO: 250_000_00,
        Cover.ESCORT: 1_000_000_00,
    }
    amounts.update(over or {})
    return [
        a_certificate(cover=cover, policy=f"P-{cover}", amount=cents(value))
        for cover, value in amounts.items()
    ]


def test_a_requirement_prints_its_cover_and_amount():
    made = Requirement(cover=Cover.BOND, amount=cents(50_000_00), because="one move")
    assert "surety bond" in str(made)
    assert "$50,000.00" in str(made)


def test_a_requirement_for_no_money_is_refused():
    with pytest.raises(BadValueError):
        Requirement(cover=Cover.BOND, amount=cents(0), because="one move")


def test_a_requirement_with_no_reason_is_refused():
    with pytest.raises(BadValueError):
        Requirement(cover=Cover.BOND, amount=cents(1), because="  ")


def test_every_permit_kind_has_a_schedule():
    for kind in Kind:
        assert requirements(kind)


def test_an_annual_asks_for_more_bond_than_a_trip():
    trip = next(r for r in REQUIRED[Kind.TRIP] if r.cover is Cover.BOND)
    annual = next(r for r in REQUIRED[Kind.ANNUAL] if r.cover is Cover.BOND)
    assert int(annual.amount) > int(trip.amount)


def test_a_superload_asks_for_cargo_cover_as_well():
    assert Cover.CARGO in {r.cover for r in requirements(Kind.SUPERLOAD)}


def test_a_trip_does_not_ask_for_cargo_cover():
    assert Cover.CARGO not in {r.cover for r in requirements(Kind.TRIP)}


def test_an_escorted_move_asks_for_escort_cover():
    assert ESCORT_COVER in requirements(Kind.TRIP, escorted=True)


def test_an_unescorted_move_does_not_ask_for_escort_cover():
    assert ESCORT_COVER not in requirements(Kind.TRIP)


def test_a_flag_that_is_not_a_boolean_is_refused():
    with pytest.raises(BadValueError):
        requirements(Kind.TRIP, escorted="yes")  # type: ignore[arg-type]


def test_a_carrier_with_the_full_set_is_clear():
    assert clear_to_issue(a_full_set(), Kind.SUPERLOAD, JUN)


def test_a_carrier_with_nothing_lodged_is_short_everything():
    found = gaps([], Kind.TRIP, JUN)
    assert len(found) == 2
    assert all(one.nothing_lodged for one in found)


def test_a_missing_cover_is_short_by_the_whole_amount():
    found = gaps(
        [a_certificate(cover=Cover.LIABILITY, amount=cents(5_000_000_00))], Kind.TRIP, JUN
    )
    assert len(found) == 1
    assert int(found[0].short) == 50_000_00


def test_a_small_bond_is_short_by_the_difference():
    held = a_full_set({Cover.BOND: 40_000_00})
    found = gaps(held, Kind.TRIP, JUN)
    assert len(found) == 1
    assert int(found[0].short) == 10_000_00
    assert not found[0].nothing_lodged


def test_a_bond_that_lapsed_counts_as_no_bond():
    held = a_full_set()
    held[0] = a_certificate(
        cover=Cover.BOND,
        policy="P-Cover.BOND",
        amount=cents(250_000_00),
        span=DaySpan(dt.date(2024, 1, 1), dt.date(2024, 12, 31)),
    )
    found = gaps(held, Kind.TRIP, JUN)
    assert [one.requirement.cover for one in found] == [Cover.BOND]
    assert found[0].nothing_lodged


def test_a_bond_exactly_at_the_requirement_is_no_gap():
    held = a_full_set({Cover.BOND: 50_000_00})
    assert clear_to_issue(held, Kind.TRIP, JUN)


def test_a_full_set_still_misses_escort_cover_when_escorted():
    held = [one for one in a_full_set() if one.cover is not Cover.ESCORT]
    assert not clear_to_issue(held, Kind.TRIP, JUN, escorted=True)


def test_a_gap_with_nothing_lodged_says_so():
    line = str(gaps([], Kind.TRIP, JUN)[0])
    assert "no surety bond on file" in line


def test_a_gap_that_is_merely_small_names_the_shortfall():
    held = a_full_set({Cover.BOND: 40_000_00})
    assert "short of" in str(gaps(held, Kind.TRIP, JUN)[0])


def test_a_gap_short_by_nothing_is_refused():
    need = Requirement(cover=Cover.BOND, amount=cents(1), because="x")
    with pytest.raises(BadValueError):
        Gap(requirement=need, held=None, short=cents(0))


def test_a_gap_against_something_that_is_not_a_requirement_is_refused():
    with pytest.raises(BadValueError):
        Gap(requirement="bond", held=None, short=cents(1))  # type: ignore[arg-type]


def test_a_gap_holding_something_that_is_not_a_certificate_is_refused():
    need = Requirement(cover=Cover.BOND, amount=cents(1), because="x")
    with pytest.raises(BadValueError):
        Gap(requirement=need, held="paper", short=cents(1))  # type: ignore[arg-type]


def test_the_superload_bond_is_the_heaviest_of_the_three():
    best = {
        kind: max(int(r.amount) for r in rs if r.cover is Cover.BOND)
        for kind, rs in REQUIRED.items()
    }
    assert best[Kind.SUPERLOAD] == max(best.values())
