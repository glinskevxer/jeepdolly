import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.limits.finding import Finding, Severity, excess_of, worst
from jeepdolly.units.mass import pounds


def a_finding(**over: object) -> Finding:
    """A single axle overage, with any part of it swapped out."""
    kw: dict[str, object] = {
        "rule": "single-axle",
        "subject": "axle 4",
        "severity": Severity.PERMIT,
        "detail": "over the 20,000 lb single axle limit",
        "excess": pounds(2300),
    }
    kw.update(over)
    return Finding(**kw)  # type: ignore[arg-type]


def test_finding_keeps_its_rule():
    assert a_finding().rule == "single-axle"


def test_finding_takes_a_severity_as_text():
    assert a_finding(severity="refuse").severity is Severity.REFUSE


def test_finding_refuses_an_unknown_severity():
    with pytest.raises(ValueError, match="not a valid|note|permit|refuse"):
        a_finding(severity="grumble")


def test_finding_collapses_whitespace_in_the_detail():
    assert a_finding(detail="over   the  limit").detail == "over the limit"


def test_finding_refuses_an_empty_rule():
    with pytest.raises(BadValueError):
        a_finding(rule="  ")


def test_finding_refuses_an_empty_subject():
    with pytest.raises(BadValueError):
        a_finding(subject="")


def test_finding_refuses_a_detail_that_is_not_text():
    with pytest.raises(BadValueError):
        a_finding(detail=42)


def test_finding_defaults_to_no_excess():
    made = Finding(rule="r", subject="s", severity=Severity.NOTE, detail="d")
    assert int(made.excess) == 0


def test_note_refuses_an_excess():
    with pytest.raises(BadValueError):
        a_finding(severity=Severity.NOTE)


def test_a_refusal_severity_blocks_the_permit():
    assert a_finding(severity=Severity.REFUSE, excess=pounds(0)).blocking


def test_permit_is_not_blocking():
    assert not a_finding().blocking


def test_permit_with_an_excess_is_billable():
    assert a_finding().billable


def test_permit_with_no_excess_is_not_billable():
    assert not a_finding(excess=pounds(0)).billable


def test_refuse_is_never_billable():
    assert not a_finding(severity=Severity.REFUSE).billable


def test_note_is_never_billable():
    assert not a_finding(severity=Severity.NOTE, excess=pounds(0)).billable


def test_finding_prints_the_subject_and_the_overage():
    assert str(a_finding()) == "axle 4: over the 20,000 lb single axle limit by 2,300 lb"


def test_finding_with_no_excess_prints_without_a_tail():
    made = a_finding(excess=pounds(0))
    assert str(made) == "axle 4: over the 20,000 lb single axle limit"


def test_worst_of_nothing_is_a_note():
    assert worst([]) is Severity.NOTE


def test_worst_finds_the_refusal():
    batch = [a_finding(), a_finding(severity=Severity.REFUSE, excess=pounds(0))]
    assert worst(batch) is Severity.REFUSE


def test_worst_of_notes_is_a_note():
    batch = [a_finding(severity=Severity.NOTE, excess=pounds(0))]
    assert worst(batch) is Severity.NOTE


def test_worst_reads_a_generator():
    batch = (a_finding() for _ in range(2))
    assert worst(batch) is Severity.PERMIT


def test_excess_of_nothing_is_zero():
    assert int(excess_of([])) == 0


def test_excess_takes_the_largest_and_does_not_add():
    batch = [a_finding(excess=pounds(3000)), a_finding(excess=pounds(5000))]
    assert int(excess_of(batch)) == 5000


def test_excess_ignores_a_refusal():
    batch = [a_finding(severity=Severity.REFUSE, excess=pounds(90000))]
    assert int(excess_of(batch)) == 0


def test_excess_reads_a_generator():
    batch = (a_finding(excess=pounds(n)) for n in (1000, 4000))
    assert int(excess_of(batch)) == 4000


def test_findings_with_the_same_parts_are_equal():
    assert a_finding() == a_finding()


def test_a_finding_cannot_be_written_to():
    with pytest.raises(AttributeError):
        a_finding().rule = "other"  # type: ignore[misc]
