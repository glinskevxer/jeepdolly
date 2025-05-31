import datetime as dt

import pytest

from jeepdolly.errors import BadValueError, NotAllowedError
from jeepdolly.limits.finding import Finding, Severity
from jeepdolly.permit.decision import decide
from jeepdolly.permit.permit import MAX_EXTENSION_DAYS, Permit, State, issue
from jeepdolly.units.clock import DaySpan
from jeepdolly.units.distance import miles

from .conftest import TRIP, an_application

DECIDED = dt.date(2025, 6, 17)
ISSUED = dt.date(2025, 6, 17)


def a_permit(**over: object) -> Permit:
    """An issued single trip permit."""
    decision = decide(an_application(), (), DECIDED, miles("42.00"))
    kw: dict[str, object] = {
        "number": "P-000123",
        "decision": decision,
        "issued_on": ISSUED,
        "span": TRIP,
    }
    kw.update(over)
    return Permit(**kw)  # type: ignore[arg-type]


def test_issue_writes_a_permit():
    decision = decide(an_application(), (), DECIDED, miles("42.00"))
    made = issue("P-000123", decision, ISSUED)  # type: ignore[arg-type]
    assert made.number == "P-000123"
    assert made.live


def test_issue_takes_the_span_from_the_application():
    decision = decide(an_application(), (), DECIDED, miles("42.00"))
    assert issue("P-000123", decision, ISSUED).span == TRIP  # type: ignore[arg-type]


def test_issue_refuses_a_refusal():
    blocked = Finding(
        rule="clearance", subject="x", severity=Severity.REFUSE, detail="too tall"
    )
    decision = decide(an_application(), (blocked,), DECIDED, miles("42.00"))
    with pytest.raises(NotAllowedError):
        issue("P-000123", decision, ISSUED)  # type: ignore[arg-type]


def test_a_permit_knows_its_carrier():
    assert a_permit().carrier == "VANCE"


def test_a_permit_carries_the_fee():
    assert int(a_permit().fee) > 0


def test_a_permit_is_good_inside_its_span():
    assert a_permit().good_on(dt.date(2025, 6, 19))


def test_a_permit_is_not_good_before_it_starts():
    assert not a_permit().good_on(dt.date(2025, 6, 17))


def test_a_permit_expires_after_its_last_day():
    made = a_permit()
    assert not made.expired_on(dt.date(2025, 6, 20))
    assert made.expired_on(dt.date(2025, 6, 21))


def test_voiding_marks_it_void():
    gone = a_permit().voided("carrier cancelled the move", ISSUED)
    assert gone.state is State.VOID
    assert not gone.live


def test_voiding_keeps_the_reason():
    gone = a_permit().voided("carrier   cancelled", ISSUED)
    assert gone.reason == "carrier cancelled"


def test_a_void_permit_is_not_good_on_any_day():
    gone = a_permit().voided("cancelled", ISSUED)
    assert not gone.good_on(dt.date(2025, 6, 19))


def test_voiding_twice_is_refused():
    gone = a_permit().voided("cancelled", ISSUED)
    with pytest.raises(NotAllowedError):
        gone.voided("cancelled again", ISSUED)


def test_voiding_needs_a_reason():
    with pytest.raises(BadValueError):
        a_permit().voided("   ", ISSUED)


def test_voiding_before_the_issue_day_is_refused():
    with pytest.raises(BadValueError):
        a_permit().voided("cancelled", ISSUED - dt.timedelta(days=1))


def test_a_permit_with_a_reason_and_no_void_is_refused():
    with pytest.raises(BadValueError):
        a_permit(reason="cancelled")


def test_a_void_permit_with_no_reason_is_refused():
    with pytest.raises(BadValueError):
        a_permit(state=State.VOID)


def test_superseding_names_the_successor():
    old = a_permit().superseded_by("P-000124")  # type: ignore[arg-type]
    assert old.state is State.SUPERSEDED
    assert old.replaced_by == "P-000124"


def test_a_superseded_permit_is_not_live():
    assert not a_permit().superseded_by("P-000124").live  # type: ignore[arg-type]


def test_superseding_twice_is_refused():
    old = a_permit().superseded_by("P-000124")  # type: ignore[arg-type]
    with pytest.raises(NotAllowedError):
        old.superseded_by("P-000125")  # type: ignore[arg-type]


def test_superseding_a_void_permit_is_refused():
    gone = a_permit().voided("cancelled", ISSUED)
    with pytest.raises(NotAllowedError):
        gone.superseded_by("P-000124")  # type: ignore[arg-type]


def test_voiding_a_superseded_permit_is_refused():
    old = a_permit().superseded_by("P-000124")  # type: ignore[arg-type]
    with pytest.raises(NotAllowedError):
        old.voided("cancelled", ISSUED)


def test_a_permit_may_not_replace_itself():
    with pytest.raises(BadValueError):
        a_permit().superseded_by("P-000123")  # type: ignore[arg-type]


def test_a_successor_without_the_state_is_refused():
    with pytest.raises(BadValueError):
        a_permit(replaced_by="P-000124")


def test_a_superseded_permit_without_a_successor_is_refused():
    with pytest.raises(BadValueError):
        a_permit(state=State.SUPERSEDED)


def test_extending_moves_the_last_day():
    longer = a_permit().extended(dt.date(2025, 6, 23))
    assert longer.span.last == dt.date(2025, 6, 23)
    assert longer.live


def test_extending_leaves_the_first_day_alone():
    longer = a_permit().extended(dt.date(2025, 6, 23))
    assert longer.span.first == TRIP.first


def test_extending_leaves_the_fee_alone():
    assert a_permit().extended(dt.date(2025, 6, 23)).fee == a_permit().fee


def test_extending_to_the_same_day_is_refused():
    with pytest.raises(BadValueError):
        a_permit().extended(TRIP.last)


def test_extending_backwards_is_refused():
    with pytest.raises(BadValueError):
        a_permit().extended(dt.date(2025, 6, 19))


def test_extending_too_far_is_refused():
    too_far = TRIP.last + dt.timedelta(days=MAX_EXTENSION_DAYS + 1)
    with pytest.raises(BadValueError):
        a_permit().extended(too_far)


def test_extending_to_the_limit_is_allowed():
    edge = TRIP.last + dt.timedelta(days=MAX_EXTENSION_DAYS)
    assert a_permit().extended(edge).span.last == edge


def test_extending_a_void_permit_is_refused():
    gone = a_permit().voided("cancelled", ISSUED)
    with pytest.raises(NotAllowedError):
        gone.extended(dt.date(2025, 6, 23))


def test_a_permit_refuses_a_span_starting_before_the_application():
    early = DaySpan(dt.date(2025, 6, 17), dt.date(2025, 6, 20))
    with pytest.raises(BadValueError):
        a_permit(span=early)


def test_a_permit_refuses_a_datetime_issue_day():
    with pytest.raises(BadValueError):
        a_permit(issued_on=dt.datetime(2025, 6, 17, tzinfo=dt.UTC))


def test_a_permit_refuses_a_decision_that_is_not_one():
    with pytest.raises(BadValueError):
        a_permit(decision="issued")


def test_a_permit_prints_its_state_and_span():
    assert str(a_permit()) == "P-000123 VANCE active 2025-06-18..2025-06-20"
