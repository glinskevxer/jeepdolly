import datetime as dt

import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.limits.finding import Finding, Severity
from jeepdolly.permit.application import Kind
from jeepdolly.permit.decision import Decision, Outcome, decide, outcome_for
from jeepdolly.units.distance import miles
from jeepdolly.units.length import feet, feet_inches
from jeepdolly.units.mass import pounds

from .conftest import FILED, a_load, an_application

DECIDED = dt.date(2025, 6, 17)


def a_finding(**over: object) -> Finding:
    kw: dict[str, object] = {
        "rule": "gross",
        "subject": "the rig",
        "severity": Severity.PERMIT,
        "detail": "over the 80,000 lb gross limit",
        "excess": pounds(20000),
    }
    kw.update(over)
    return Finding(**kw)  # type: ignore[arg-type]


def test_a_clean_application_is_issued(trip):
    made = decide(trip, (), DECIDED, miles("42.00"))
    assert made.outcome is Outcome.ISSUE
    assert made.issued


def test_an_issued_decision_carries_an_invoice(trip):
    made = decide(trip, (), DECIDED, miles("42.00"))
    assert made.invoice is not None
    assert made.fee is not None


def test_a_permit_finding_is_still_issued(trip):
    made = decide(trip, (a_finding(),), DECIDED, miles("42.00"))
    assert made.outcome is Outcome.ISSUE


def test_the_excess_reaches_the_invoice(trip):
    made = decide(trip, (a_finding(),), DECIDED, miles("42.00"))
    assert made.invoice is not None
    assert made.invoice.has("WEIGHT")


def test_a_posted_bridge_refuses(trip):
    blocked = a_finding(rule="posted-bridge", severity=Severity.REFUSE, excess=pounds(0))
    made = decide(trip, (blocked,), DECIDED, miles("42.00"))
    assert made.outcome is Outcome.REFUSE


def test_an_over_width_block_refers(trip):
    referable = a_finding(rule="over-width", severity=Severity.REFUSE, excess=pounds(0))
    made = decide(trip, (referable,), DECIDED, miles("42.00"))
    assert made.outcome is Outcome.REFER


def test_one_refusal_beats_a_referral(trip):
    referable = a_finding(rule="over-width", severity=Severity.REFUSE, excess=pounds(0))
    blocked = a_finding(rule="clearance", severity=Severity.REFUSE, excess=pounds(0))
    made = decide(trip, (referable, blocked), DECIDED, miles("42.00"))
    assert made.outcome is Outcome.REFUSE


def test_a_superload_is_referred_even_when_clean():
    made = decide(an_application(kind=Kind.SUPERLOAD), (), DECIDED, miles("42.00"))
    assert made.outcome is Outcome.REFER


def test_a_referred_decision_has_no_invoice(trip):
    referable = a_finding(rule="over-height", severity=Severity.REFUSE, excess=pounds(0))
    made = decide(trip, (referable,), DECIDED, miles("42.00"))
    assert made.invoice is None
    assert made.fee is None


def test_a_refusal_lists_its_reasons(trip):
    blocked = a_finding(
        rule="clearance",
        subject="STR-1 MRL overhead",
        severity=Severity.REFUSE,
        excess=pounds(0),
    )
    made = decide(trip, (blocked,), DECIDED, miles("42.00"))
    assert made.reasons == ("STR-1 MRL overhead: over the 80,000 lb gross limit",)


def test_a_clean_decision_has_no_blockers(trip):
    assert decide(trip, (), DECIDED, miles("42.00")).blockers == ()


def test_a_note_does_not_block(trip):
    note = a_finding(rule="flags", severity=Severity.NOTE, excess=pounds(0))
    assert decide(trip, (note,), DECIDED, miles("42.00")).outcome is Outcome.ISSUE


def test_the_escorts_are_worked_out_from_the_load():
    wide = an_application(load=a_load(width=feet(13)))
    made = decide(wide, (), DECIDED, miles("42.00"))
    assert made.escort_count == 1


def test_the_escorts_are_billed():
    wide = an_application(load=a_load(width=feet(13)))
    made = decide(wide, (), DECIDED, miles("42.00"))
    assert made.invoice is not None
    assert made.invoice.has("ESCORT")


def test_a_narrow_load_needs_no_escorts():
    narrow = an_application(load=a_load(width=feet_inches(8, 6)))
    assert decide(narrow, (), DECIDED, miles("42.00")).escorts == ()


def test_an_annual_is_decided_without_a_distance():
    from jeepdolly.permit.application import ANNUAL_DAYS
    from jeepdolly.units.clock import DaySpan

    year = DaySpan(
        dt.date(2025, 7, 1), dt.date(2025, 7, 1) + dt.timedelta(days=ANNUAL_DAYS - 1)
    )
    annual = an_application(kind=Kind.ANNUAL, span=year, origin=None, destination=None)
    made = decide(annual, (), DECIDED)
    assert made.issued


def test_a_decision_refuses_a_day_before_the_application(trip):
    with pytest.raises(BadValueError):
        decide(trip, (), FILED - dt.timedelta(days=1), miles("42.00"))


def test_a_decision_may_be_made_the_day_it_is_filed(trip):
    assert decide(trip, (), FILED, miles("42.00")).issued


def test_a_decision_refuses_a_datetime(trip):
    with pytest.raises(BadValueError):
        decide(trip, (), dt.datetime(2025, 6, 17, tzinfo=dt.UTC), miles("42.00"))


def test_an_issued_decision_without_an_invoice_is_refused(trip):
    with pytest.raises(BadValueError):
        Decision(
            application=trip,
            outcome=Outcome.ISSUE,
            findings=(),
            escorts=(),
            decided_on=DECIDED,
        )


def test_a_refused_decision_with_an_invoice_is_refused(trip):
    priced = decide(trip, (), DECIDED, miles("42.00"))
    with pytest.raises(BadValueError):
        Decision(
            application=trip,
            outcome=Outcome.REFUSE,
            findings=(),
            escorts=(),
            decided_on=DECIDED,
            invoice=priced.invoice,
        )


def test_outcome_for_reads_only_the_rules(trip):
    blocked = a_finding(rule="local-order", severity=Severity.REFUSE, excess=pounds(0))
    assert outcome_for(trip, (blocked,)) is Outcome.REFUSE


def test_a_decision_prints_its_outcome_and_bill(trip):
    made = decide(trip, (), DECIDED, miles("42.00"))
    assert str(made).startswith("VANCE issue, 5 lines")


def test_a_refusal_prints_without_a_bill(trip):
    blocked = a_finding(rule="clearance", severity=Severity.REFUSE, excess=pounds(0))
    assert str(decide(trip, (blocked,), DECIDED, miles("42.00"))) == "VANCE refuse"


def test_a_tall_load_gets_a_height_pole_and_a_height_line():
    tall = an_application(load=a_load(height=feet_inches(15, 8), width=feet_inches(8, 6)))
    made = decide(tall, (), DECIDED, miles("42.00"))
    assert made.escort_count == 1
    assert made.invoice is not None
    assert made.invoice.has("HEIGHT")


def test_a_cleared_superload_issues():
    made = decide(
        an_application(kind=Kind.SUPERLOAD), (), DECIDED, miles("42.00"), cleared=True
    )
    assert made.outcome is Outcome.ISSUE


def test_clearing_lifts_a_referable_block(trip):
    referable = a_finding(rule="over-width", severity=Severity.REFUSE, excess=pounds(0))
    made = decide(trip, (referable,), DECIDED, miles("42.00"), cleared=True)
    assert made.outcome is Outcome.ISSUE


def test_clearing_does_not_lift_a_posted_bridge(trip):
    blocked = a_finding(rule="posted-bridge", severity=Severity.REFUSE, excess=pounds(0))
    made = decide(trip, (blocked,), DECIDED, miles("42.00"), cleared=True)
    assert made.outcome is Outcome.REFUSE


def test_outcome_for_takes_the_cleared_flag(trip):
    assert outcome_for(trip, (), cleared=True) is Outcome.ISSUE
