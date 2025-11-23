import datetime as dt

import pytest

from jeepdolly.errors import NotAllowedError, NotFoundError
from jeepdolly.party.carrier import Carrier
from jeepdolly.permit.application import ANNUAL_DAYS, Application, Kind
from jeepdolly.permit.decision import Outcome
from jeepdolly.permit.desk import Desk
from jeepdolly.permit.permit import State
from jeepdolly.rig.axle import Axle
from jeepdolly.rig.config import Configuration
from jeepdolly.rig.load import Load
from jeepdolly.roadway.node import Node
from jeepdolly.roadway.segment import Segment
from jeepdolly.roadway.structure import Structure, StructureKind
from jeepdolly.store.office import opened_new_office
from jeepdolly.units.clock import DaySpan
from jeepdolly.units.distance import miles
from jeepdolly.units.length import feet, feet_inches, inches
from jeepdolly.units.mass import pounds

FILED = dt.date(2025, 6, 16)
DECIDED = dt.date(2025, 6, 17)
TRIP = DaySpan(dt.date(2025, 6, 18), dt.date(2025, 6, 20))
YEAR = DaySpan(dt.date(2025, 7, 1), dt.date(2025, 7, 1) + dt.timedelta(days=ANNUAL_DAYS - 1))


def steer(weight: int = 12000) -> Axle:
    return Axle(weight=pounds(weight), tires=2, tire_width=inches(11), steering=True)


def drive(weight: int = 17000) -> Axle:
    return Axle(weight=pounds(weight), tires=4, tire_width=inches(11))


def a_config(weight: int = 17000) -> Configuration:
    return Configuration(
        name="3S2",  # type: ignore[arg-type]
        axles=(steer(), drive(weight), drive(weight), drive(weight), drive(weight)),
        spacings=(feet(15), feet(4), feet(30), feet(4)),
    )


def a_load(**over: object) -> Load:
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
    kw: dict[str, object] = {
        "carrier": "VANCE",
        "rig": "R-00001",
        "load": a_load(),
        "span": TRIP,
        "filed_on": FILED,
        "kind": Kind.TRIP,
        "origin": "JCT-A",
        "destination": "JCT-D",
    }
    kw.update(over)
    return Application(**kw)  # type: ignore[arg-type]


@pytest.fixture
def desk():
    """A desk over a stocked office: one carrier, one rig, the corridor map."""
    with opened_new_office() as office:
        office.carriers.add(
            Carrier(code="VANCE", name="Vance Heavy Haul", usdot=1184062, home_state="MT")  # type: ignore[arg-type]
        )
        office.rigs.add("VANCE", a_config(), FILED)
        road = office.roadway
        for key in ("JCT-A", "JCT-B", "JCT-C", "JCT-D"):
            road.add_node(Node(code=key, name=key.lower(), county="Missoula"))  # type: ignore[arg-type]
        for key, start_node, end_node, route, length, posted in (
            ("SEG-AB", "JCT-A", "JCT-B", "US-12", "12.00", None),
            ("SEG-BC", "JCT-B", "JCT-C", "US-12", "8.50", None),
            ("SEG-CD", "JCT-C", "JCT-D", "US-12", "6.00", pounds(48000)),
            ("SEG-BD", "JCT-B", "JCT-D", "SR-200", "31.00", None),
        ):
            road.add_segment(
                Segment(
                    code=key,  # type: ignore[arg-type]
                    start=start_node,  # type: ignore[arg-type]
                    end=end_node,  # type: ignore[arg-type]
                    route=route,
                    distance=miles(length),
                    posted_gross=posted,
                )
            )
        road.add_structure(
            Structure(
                reference=road.next_structure(),
                segment="SEG-BC",  # type: ignore[arg-type]
                name="MRL overhead",
                kind=StructureKind.OVERHEAD,
                milepost=miles("1.10"),
                clearance=feet_inches(15, 2),
            )
        )
        yield Desk(office=office)


def test_filing_puts_the_application_on_file(desk):
    filed = desk.file(an_application())
    assert desk.office.applications.count() == 1
    assert filed.key == 1


def test_filing_refuses_a_retired_carrier(desk):
    desk.office.carriers.save(desk.office.carriers.get("VANCE").retired())
    with pytest.raises(NotAllowedError):
        desk.file(an_application())


def test_filing_refuses_a_carrier_that_is_not_there(desk):
    with pytest.raises(NotFoundError):
        desk.file(an_application(carrier="NOBODY"))


def test_assessing_finds_a_route_around_the_local_order(desk):
    filed = desk.file(an_application())
    seen = desk.assess(filed.key)
    assert seen.route is not None
    assert [s.code for s in seen.route.segments] == ["SEG-AB", "SEG-BD"]


def test_assessing_reports_the_distance(desk):
    filed = desk.file(an_application())
    assert int(desk.assess(filed.key).distance or 0) == 4300


def test_assessing_an_annual_finds_no_route(desk):
    annual = an_application(kind=Kind.ANNUAL, span=YEAR, origin=None, destination=None)
    filed = desk.file(annual)
    seen = desk.assess(filed.key)
    assert seen.route is None
    assert seen.distance is None


def test_assessing_raises_when_nothing_connects(desk):
    desk.office.roadway.add_node(Node(code="JCT-X", name="x", county="Ravalli"))  # type: ignore[arg-type]
    filed = desk.file(an_application(destination="JCT-X"))
    with pytest.raises(NotFoundError):
        desk.assess(filed.key)


def test_a_clean_application_is_issued(desk):
    filed = desk.file(an_application())
    _, made = desk.decide(filed.key, DECIDED)
    assert made.outcome is Outcome.ISSUE


def test_issuing_writes_a_permit(desk):
    filed = desk.file(an_application())
    permit = desk.issue(filed.key, DECIDED)
    assert permit.number == "P-000001"
    assert desk.office.permits.count() == 1


def test_the_permit_carries_a_fee(desk):
    filed = desk.file(an_application())
    assert int(desk.issue(filed.key, DECIDED).fee) > 0


def test_the_permit_bills_the_route_it_was_given(desk):
    filed = desk.file(an_application())
    permit = desk.issue(filed.key, DECIDED)
    assert permit.decision.invoice is not None
    assert "43.00 mi" in permit.decision.invoice.line("MILES").detail


def test_a_tall_load_falls_back_to_the_shortest_route_and_is_refused(desk):
    filed = desk.file(an_application(load=a_load(height=feet(18))))
    seen = desk.assess(filed.key)
    assert seen.blocked


def test_a_blocked_application_will_not_issue(desk):
    filed = desk.file(an_application(load=a_load(height=feet(18))))
    with pytest.raises(NotAllowedError):
        desk.issue(filed.key, DECIDED)


def test_blockers_of_names_the_rules(desk):
    filed = desk.file(an_application(load=a_load(height=feet(18))))
    assert "over-height" in [f.rule for f in desk.blockers_of(filed.key)]


def test_a_superload_is_referred_and_not_issued(desk):
    filed = desk.file(an_application(kind=Kind.SUPERLOAD))
    _, made = desk.decide(filed.key, DECIDED)
    assert made.outcome is Outcome.REFER
    with pytest.raises(NotAllowedError):
        desk.issue(filed.key, DECIDED)


def test_voiding_refunds_a_charged_permit(desk):
    from jeepdolly.units.money import cents

    filed = desk.file(an_application())
    permit = desk.issue(filed.key, DECIDED)
    desk.office.accounts.deposit("VANCE", DECIDED, cents(100000))
    desk.office.accounts.charge("VANCE", DECIDED, permit.fee, str(permit.number))
    before = desk.office.accounts.balance("VANCE")
    desk.void(str(permit.number), "carrier cancelled", DECIDED)
    after = desk.office.accounts.balance("VANCE")
    assert int(after) - int(before) == int(permit.fee)


def test_voiding_an_uncharged_permit_refunds_nothing(desk):
    filed = desk.file(an_application())
    permit = desk.issue(filed.key, DECIDED)
    desk.void(str(permit.number), "carrier cancelled", DECIDED)
    assert int(desk.office.accounts.balance("VANCE")) == 0


def test_a_refund_is_posted_once_even_if_asked_twice(desk):
    from jeepdolly.errors import NotAllowedError
    from jeepdolly.units.money import cents

    filed = desk.file(an_application())
    permit = desk.issue(filed.key, DECIDED)
    desk.office.accounts.deposit("VANCE", DECIDED, cents(100000))
    desk.office.accounts.charge("VANCE", DECIDED, permit.fee, str(permit.number))
    desk.void(str(permit.number), "cancelled", DECIDED)
    with pytest.raises(NotAllowedError):
        desk.void(str(permit.number), "cancelled again", DECIDED)
    refunds = [e for e in desk.office.accounts.entries("VANCE") if str(e.kind) == "refund"]
    assert len(refunds) == 1


def test_voiding_may_be_told_not_to_refund(desk):
    from jeepdolly.units.money import cents

    filed = desk.file(an_application())
    permit = desk.issue(filed.key, DECIDED)
    desk.office.accounts.deposit("VANCE", DECIDED, cents(100000))
    desk.office.accounts.charge("VANCE", DECIDED, permit.fee, str(permit.number))
    before = desk.office.accounts.balance("VANCE")
    desk.void(str(permit.number), "cancelled", DECIDED, refund=False)
    assert desk.office.accounts.balance("VANCE") == before


def test_voiding_is_kept_in_the_file(desk):
    filed = desk.file(an_application())
    permit = desk.issue(filed.key, DECIDED)
    desk.void(str(permit.number), "carrier cancelled", DECIDED)
    assert not desk.office.permits.get(str(permit.number)).live


def test_extending_is_kept_in_the_file(desk):
    filed = desk.file(an_application())
    permit = desk.issue(filed.key, DECIDED)
    desk.extend(str(permit.number), dt.date(2025, 6, 22))
    assert desk.office.permits.get(str(permit.number)).span.last == dt.date(2025, 6, 22)


def test_amending_writes_a_new_permit(desk):
    filed = desk.file(an_application())
    old = desk.issue(filed.key, DECIDED)
    new = desk.amend(str(old.number), an_application(load=a_load(width=feet(13))), DECIDED)
    assert new.number == "P-000002"


def test_amending_supersedes_the_old_permit(desk):
    filed = desk.file(an_application())
    old = desk.issue(filed.key, DECIDED)
    new = desk.amend(str(old.number), an_application(load=a_load(width=feet(13))), DECIDED)
    read = desk.office.permits.get(str(old.number))
    assert read.state is State.SUPERSEDED
    assert read.replaced_by == new.number


def test_amending_prices_the_new_permit_from_scratch(desk):
    filed = desk.file(an_application())
    old = desk.issue(filed.key, DECIDED)
    new = desk.amend(str(old.number), an_application(load=a_load(width=feet(15))), DECIDED)
    assert int(new.fee) != int(old.fee)


def test_amending_a_void_permit_is_refused(desk):
    filed = desk.file(an_application())
    old = desk.issue(filed.key, DECIDED)
    desk.void(str(old.number), "cancelled", DECIDED)
    with pytest.raises(NotAllowedError):
        desk.amend(str(old.number), an_application(), DECIDED)


def test_an_annual_permit_is_issued_without_a_route(desk):
    annual = an_application(kind=Kind.ANNUAL, span=YEAR, origin=None, destination=None)
    filed = desk.file(annual)
    permit = desk.issue(filed.key, DECIDED)
    assert permit.decision.invoice is not None
    assert not permit.decision.invoice.has("MILES")


def test_the_escorts_reach_the_permit(desk):
    filed = desk.file(an_application())
    permit = desk.issue(filed.key, DECIDED)
    assert permit.decision.escort_count == 1


def test_a_heavy_rig_is_still_issued_with_a_weight_line(desk):
    desk.office.rigs.add("VANCE", a_config(23000), FILED)
    filed = desk.file(an_application(rig="R-00002"))
    permit = desk.issue(filed.key, DECIDED)
    assert permit.decision.invoice is not None
    assert permit.decision.invoice.has("WEIGHT")


def test_the_permit_reads_back_the_same_after_a_reopen(desk):
    filed = desk.file(an_application())
    permit = desk.issue(filed.key, DECIDED)
    read = desk.office.permits.get(str(permit.number))
    assert read.fee == permit.fee
    assert read.decision.findings == permit.decision.findings


def a_superload(**over: object) -> Application:
    """An application wide enough to need an engineer."""
    return an_application(kind=Kind.SUPERLOAD, load=a_load(width=feet(17)), **over)


def test_referring_opens_a_review(desk):
    filed = desk.file(a_superload())
    made = desk.refer(filed.key, DECIDED)
    assert made.open
    assert made.reference == "E-00001"


def test_referring_an_application_that_would_issue_is_refused(desk):
    filed = desk.file(an_application())
    with pytest.raises(NotAllowedError):
        desk.refer(filed.key, DECIDED)


def test_referring_twice_is_refused_while_one_is_open(desk):
    from jeepdolly.errors import ConflictError

    filed = desk.file(a_superload())
    desk.refer(filed.key, DECIDED)
    with pytest.raises(ConflictError):
        desk.refer(filed.key, DECIDED)


def test_a_referred_application_will_not_issue(desk):
    filed = desk.file(a_superload())
    desk.refer(filed.key, DECIDED)
    with pytest.raises(NotAllowedError):
        desk.issue(filed.key, DECIDED)


def test_an_approved_review_lets_the_permit_issue(desk):
    filed = desk.file(a_superload())
    review = desk.refer(filed.key, DECIDED)
    desk.approve(str(review.reference), "R Halloran", DECIDED)
    permit = desk.issue(filed.key, DECIDED)
    assert permit.number == "P-000001"


def test_the_engineers_conditions_reach_the_permit(desk):
    filed = desk.file(a_superload())
    review = desk.refer(filed.key, DECIDED)
    desk.approve(
        str(review.reference), "R Halloran", DECIDED, ("walking pace over the bridge",)
    )
    permit = desk.issue(filed.key, DECIDED)
    details = [f.detail for f in permit.decision.findings if f.rule == "review-condition"]
    assert details == ["walking pace over the bridge"]


def test_the_cleared_findings_say_which_review_cleared_them(desk):
    filed = desk.file(a_superload())
    review = desk.refer(filed.key, DECIDED)
    desk.approve(str(review.reference), "R Halloran", DECIDED)
    permit = desk.issue(filed.key, DECIDED)
    width = next(f for f in permit.decision.findings if f.rule == "over-width")
    assert "cleared by E-00001" in width.detail


def test_a_cleared_finding_no_longer_blocks(desk):
    filed = desk.file(a_superload())
    review = desk.refer(filed.key, DECIDED)
    desk.approve(str(review.reference), "R Halloran", DECIDED)
    permit = desk.issue(filed.key, DECIDED)
    assert not any(f.blocking for f in permit.decision.findings)


def test_a_refused_review_does_not_let_the_permit_issue(desk):
    filed = desk.file(a_superload())
    review = desk.refer(filed.key, DECIDED)
    desk.refuse(str(review.reference), "R Halloran", DECIDED, "the bridge will not take it")
    with pytest.raises(NotAllowedError):
        desk.issue(filed.key, DECIDED)


def test_a_cleared_permit_is_still_priced(desk):
    filed = desk.file(a_superload())
    review = desk.refer(filed.key, DECIDED)
    desk.approve(str(review.reference), "R Halloran", DECIDED)
    permit = desk.issue(filed.key, DECIDED)
    assert int(permit.fee) > 0
    assert permit.decision.invoice is not None
    assert permit.decision.invoice.has("SUPER")


def test_the_approval_is_found_by_application(desk):
    filed = desk.file(a_superload())
    review = desk.refer(filed.key, DECIDED)
    assert desk.approval_for(filed.key) is None
    desk.approve(str(review.reference), "R Halloran", DECIDED)
    found = desk.approval_for(filed.key)
    assert found is not None
    assert found.reference == review.reference


def test_filing_is_written_to_the_journal(desk):
    filed = desk.file(an_application())
    entries = desk.office.history.about(f"application {filed.key}")
    assert [str(e.kind) for e in entries] == ["filed"]


def test_issuing_is_written_to_the_journal(desk):
    filed = desk.file(an_application())
    permit = desk.issue(filed.key, DECIDED)
    entries = desk.office.history.about(str(permit.number))
    assert [str(e.kind) for e in entries] == ["issued"]


def test_the_journal_records_the_clerk(desk):
    desk.clerk = "jhalloran"
    desk.file(an_application())
    assert desk.office.history.all()[0].clerk == "jhalloran"


def test_voiding_and_refunding_are_both_journalled(desk):
    from jeepdolly.units.money import cents

    filed = desk.file(an_application())
    permit = desk.issue(filed.key, DECIDED)
    desk.office.accounts.deposit("VANCE", DECIDED, cents(100000))
    desk.office.accounts.charge("VANCE", DECIDED, permit.fee, str(permit.number))
    desk.void(str(permit.number), "carrier cancelled", DECIDED)
    kinds = [str(e.kind) for e in desk.office.history.about(str(permit.number))]
    assert kinds == ["issued", "voided", "refunded"]


def test_an_uncharged_void_writes_no_refund_line(desk):
    filed = desk.file(an_application())
    permit = desk.issue(filed.key, DECIDED)
    desk.void(str(permit.number), "cancelled", DECIDED)
    kinds = [str(e.kind) for e in desk.office.history.about(str(permit.number))]
    assert kinds == ["issued", "voided"]


def test_extending_a_permit_is_journalled(desk):
    filed = desk.file(an_application())
    permit = desk.issue(filed.key, DECIDED)
    desk.extend(str(permit.number), dt.date(2025, 6, 22))
    kinds = [str(e.kind) for e in desk.office.history.about(str(permit.number))]
    assert "extended" in kinds


def test_amending_a_permit_is_journalled(desk):
    filed = desk.file(an_application())
    old = desk.issue(filed.key, DECIDED)
    new = desk.amend(str(old.number), an_application(load=a_load(width=feet(13))), DECIDED)
    entries = desk.office.history.about(str(old.number))
    assert any(str(new.number) in e.detail for e in entries)


def test_referring_and_approving_are_journalled(desk):
    filed = desk.file(a_superload())
    review = desk.refer(filed.key, DECIDED)
    desk.approve(str(review.reference), "R Halloran", DECIDED, ("walking pace",))
    kinds = [str(e.kind) for e in desk.office.history.about(str(review.reference))]
    assert kinds == ["referred", "approved"]


def test_a_review_refusal_is_journalled(desk):
    filed = desk.file(a_superload())
    review = desk.refer(filed.key, DECIDED)
    desk.refuse(str(review.reference), "R Halloran", DECIDED, "no")
    kinds = [str(e.kind) for e in desk.office.history.about(str(review.reference))]
    assert kinds == ["referred", "refused"]
