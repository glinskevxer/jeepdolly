"""A year at the counter, run through the package rather than the command line.

Every other test in this suite holds one thing still and pokes at another. This
one does not: it opens a file, builds a map, takes carriers on, records rigs,
loads a year of holidays and a frost law, and then works a season of applications
through to permits, amendments, voids and a revenue return.

It is here for the wiring. Each layer is already tested on its own and the thing
that breaks in practice is two of them meeting: a decision made against the wrong
day's frost law, a permit issued and never charged, a journal line written
outside the transaction it belongs to. None of those fails a unit test.

It is deliberately one long test rather than twenty short ones. The order is the
point, and splitting it into fixtures would hide exactly the coupling it is here
to exercise.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator

import pytest

from jeepdolly.almanac.season import Season
from jeepdolly.party.carrier import Carrier
from jeepdolly.permit.amendment import Change
from jeepdolly.permit.application import Application, Kind
from jeepdolly.permit.decision import Outcome
from jeepdolly.permit.desk import Desk
from jeepdolly.permit.permit import State
from jeepdolly.permit.revoke import Cause
from jeepdolly.report.audit import audit
from jeepdolly.report.revenue import by_month, counted, revenue_sheet
from jeepdolly.rig.axle import Axle
from jeepdolly.rig.config import Configuration
from jeepdolly.rig.load import Load
from jeepdolly.roadway.node import Node
from jeepdolly.roadway.segment import RoadClass, Segment
from jeepdolly.roadway.structure import Structure, StructureKind
from jeepdolly.store.office import Office, opened_new_office
from jeepdolly.units.clock import DaySpan
from jeepdolly.units.distance import miles
from jeepdolly.units.length import feet, feet_inches, inches
from jeepdolly.units.mass import pounds
from jeepdolly.units.money import cents, total

SPRING = dt.date(2026, 3, 10)
SUMMER = dt.date(2026, 7, 6)


def steer(weight: int = 12000) -> Axle:
    """The front axle."""
    return Axle(weight=pounds(weight), tires=2, tire_width=inches(11), steering=True)


def drive(weight: int = 17000) -> Axle:
    """A load carrying axle."""
    return Axle(weight=pounds(weight), tires=4, tire_width=inches(11))


def a_rig(name: str, weight: int = 17000) -> Configuration:
    """A five axle tractor semitrailer at a given axle weight."""
    return Configuration(
        name=name,  # type: ignore[arg-type]
        axles=(steer(), drive(weight), drive(weight), drive(weight), drive(weight)),
        spacings=(feet(15), feet(4), feet(30), feet(4)),
    )


def a_load(**over: object) -> Load:
    """A nondivisible load."""
    kw: dict[str, object] = {
        "description": "step-up transformer",
        "weight": pounds(148000),
        "width": feet_inches(12, 6),
        "height": feet_inches(14, 2),
        "length": feet(48),
        "divisible": False,
        "reason": "single-piece",
    }
    kw.update(over)
    return Load(**kw)  # type: ignore[arg-type]


def an_application(**over: object) -> Application:
    """A single trip application from Vance."""
    kw: dict[str, object] = {
        "carrier": "VANCE",
        "rig": "R-00001",
        "load": a_load(),
        "span": DaySpan(SUMMER + dt.timedelta(days=2), SUMMER + dt.timedelta(days=4)),
        "filed_on": SUMMER,
        "kind": Kind.TRIP,
        "origin": "JCT-A",
        "destination": "JCT-D",
    }
    kw.update(over)
    return Application(**kw)  # type: ignore[arg-type]


def stock(office: Office) -> None:
    """Build the office's whole standing record: carriers, map, rigs, almanac."""
    office.carriers.add(
        Carrier(code="VANCE", name="Vance Heavy Haul", usdot=1184062, home_state="MT")  # type: ignore[arg-type]
    )
    office.carriers.add(
        Carrier(code="SUMMIT", name="Summit Rigging", usdot=2277431, home_state="ID")  # type: ignore[arg-type]
    )
    for key, county in (
        ("JCT-A", "Missoula"),
        ("JCT-B", "Missoula"),
        ("JCT-C", "Granite"),
        ("JCT-D", "Deer Lodge"),
    ):
        office.roadway.add_node(Node(code=key, name=key.lower(), county=county))  # type: ignore[arg-type]
    for key, start, end, route, length, road_class, posted in (
        ("SEG-AB", "JCT-A", "JCT-B", "US-12", "12.00", RoadClass.STATE, None),
        ("SEG-BC", "JCT-B", "JCT-C", "US-12", "8.50", RoadClass.STATE, None),
        ("SEG-CD", "JCT-C", "JCT-D", "US-12", "6.00", RoadClass.LOCAL, pounds(48000)),
        ("SEG-BD", "JCT-B", "JCT-D", "SR-200", "31.00", RoadClass.STATE, None),
    ):
        office.roadway.add_segment(
            Segment(
                code=key,  # type: ignore[arg-type]
                start=start,  # type: ignore[arg-type]
                end=end,  # type: ignore[arg-type]
                route=route,
                distance=miles(length),
                road_class=road_class,
                posted_gross=posted,
            )
        )
    office.roadway.add_structure(
        Structure(
            reference=office.roadway.next_structure(),
            segment="SEG-BC",  # type: ignore[arg-type]
            name="MRL overhead",
            kind=StructureKind.OVERHEAD,
            milepost=miles("1.10"),
            clearance=feet_inches(15, 2),
        )
    )
    office.rigs.add("VANCE", a_rig("3S2"), SPRING)
    office.rigs.add("SUMMIT", a_rig("3S2H", 22000), SPRING)
    office.almanac.load_holidays(2026)
    office.almanac.add_season(
        Season(
            code="THAW-26",  # type: ignore[arg-type]
            span=DaySpan(dt.date(2026, 3, 1), dt.date(2026, 4, 15)),
            percent=60,
            counties=frozenset({"Missoula", "Granite"}),
            note="spring thaw",
        )
    )
    office.accounts.deposit("VANCE", SPRING, cents(500000), "opening deposit")
    office.accounts.deposit("SUMMIT", SPRING, cents(200000))


@pytest.fixture
def desk() -> Iterator[Desk]:
    """A desk over a fully stocked office."""
    with opened_new_office() as office:
        stock(office)
        yield Desk.at(office, clerk="jhalloran")


def test_a_season_at_the_counter(desk):
    office = desk.office

    # The map holds together and the almanac is loaded.
    assert office.roadway.network().connected
    assert office.almanac.counts() == (1, 11)

    # A summer application takes the bypass around the local order and issues.
    first = desk.file(an_application())
    seen = desk.assess(first.key)
    assert seen.route is not None
    assert [str(s.code) for s in seen.route.segments] == ["SEG-AB", "SEG-BD"]
    permit = desk.issue(first.key, SUMMER)
    assert permit.number == "P-000001"
    office.accounts.charge("VANCE", SUMMER, permit.fee, str(permit.number))

    # The same rig in the thaw is over on the frost law's reduced gross.
    thaw_span = DaySpan(SPRING + dt.timedelta(days=2), SPRING + dt.timedelta(days=3))
    second = desk.file(an_application(span=thaw_span, filed_on=SPRING))
    _, thawed = desk.decide(second.key, SPRING)
    assert thawed.outcome is Outcome.ISSUE
    rules = [f.rule for f in thawed.findings]
    assert "gross" in rules
    thaw_permit = desk.issue(second.key, SPRING)
    assert int(thaw_permit.fee) > int(permit.fee)
    office.accounts.charge("VANCE", SPRING, thaw_permit.fee, str(thaw_permit.number))

    # Summit's heavier rig is over on the axles and pays more again.
    third = desk.file(
        an_application(carrier="SUMMIT", rig="R-00002", filed_on=SUMMER, load=a_load())
    )
    summit = desk.issue(third.key, SUMMER)
    assert int(summit.fee) > int(permit.fee)
    office.accounts.charge("SUMMIT", SUMMER, summit.fee, str(summit.number))

    # A divisible load is refused outright, whatever route it is offered.
    fourth = desk.file(
        an_application(
            load=a_load(description="washed gravel", divisible=True, reason=""),
            filed_on=SUMMER,
        )
    )
    _, splittable = desk.decide(fourth.key, SUMMER)
    assert splittable.outcome is Outcome.REFUSE
    assert "divisible" in [f.rule for f in splittable.blockers]

    # A load taller than a clerk may write is referred rather than refused, and
    # the router has already taken it away from the overhead on SEG-BC.
    tall_key = desk.file(an_application(load=a_load(height=feet(19)), filed_on=SUMMER))
    _, tall = desk.decide(tall_key.key, SUMMER)
    assert tall.outcome is Outcome.REFER
    assert [f.rule for f in tall.blockers] == ["over-height"]

    # A superload goes to an engineer, who clears it with a condition.
    fifth = desk.file(
        an_application(kind=Kind.SUPERLOAD, load=a_load(width=feet(17)), filed_on=SUMMER)
    )
    review = desk.refer(fifth.key, SUMMER)
    with pytest.raises(Exception, match="cannot issue"):
        desk.issue(fifth.key, SUMMER)
    desk.approve(str(review.reference), "R Halloran", SUMMER, ("walking pace over the bridge",))
    cleared = desk.issue(fifth.key, SUMMER)
    conditions = [f for f in cleared.decision.findings if f.rule == "review-condition"]
    assert [f.detail for f in conditions] == ["walking pace over the bridge"]
    office.accounts.charge("VANCE", SUMMER, cleared.fee, str(cleared.number))

    # An amendment keeps the number, reprices, and settles the difference on
    # the account. The permit itself still stands at what it was issued for.
    amended = desk.amend(
        str(permit.number), an_application(load=a_load(width=feet(15))), SUMMER
    )
    assert office.permits.get(str(permit.number)).state is State.ACTIVE
    assert amended.number == permit.number
    assert amended.changes == (Change.LOAD,)
    assert int(office.permits.get(str(permit.number)).fee) == int(permit.fee)
    assert desk.current(str(permit.number)).load.width == feet(15)
    assert int(amended.charged) != 0

    # A void refunds the account and lands in the journal.
    before = office.accounts.balance("SUMMIT")
    desk.void(str(summit.number), Cause.CANCELLED, SUMMER)
    after = office.accounts.balance("SUMMIT")
    assert int(after) - int(before) == int(summit.fee) - int(desk.tariff.trip_base)
    kinds = [str(e.kind) for e in office.history.about(str(summit.number))]
    assert kinds == ["issued", "voided", "refunded"]

    # Every journal line names the clerk who was at the counter.
    assert {e.clerk for e in office.history.all()} == {"jhalloran"}

    # The permits, the accounts and the journal agree.
    for code in ("VANCE", "SUMMIT"):
        moved = {
            str(one.number): total(
                filed.charged for filed in office.amendments.for_permit(str(one.number))
            )
            for one in office.permits.for_carrier(code)
        }
        checked = audit(
            code,
            office.permits.for_carrier(code),
            office.accounts.account(code),
            office.history.all(),
            moved,
        )
        assert checked.clean, checked.findings

    # The revenue return counts what was kept and not what was voided.
    every = office.permits.all()
    assert len(every) == 4
    assert len(counted(every)) == 3
    months = by_month(every)
    assert {one.key for one in months} == {"2026-03", "2026-07"}
    assert "revenue return" in "\n".join(revenue_sheet(every))

    # A renewal of the still live thaw permit files a fresh application.
    renewed = desk.renew(str(thaw_permit.number), thaw_permit.span.last)
    assert renewed.application.span.first == thaw_permit.span.last + dt.timedelta(days=1)

    # The file still reads back sound after all of it.
    assert office.current
    assert office.carriers.count() == 2
    assert office.applications.count() == 8
