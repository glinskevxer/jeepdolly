import datetime as dt

from jeepdolly.report.workload import Month, average_days, by_month, turnarounds, workload_sheet
from jeepdolly.store.history import Event, EventKind

from .conftest import DECIDED, an_application


def text(lines: list[str]) -> str:
    """The lines joined, for a substring check."""
    return "\n".join(lines)


def an_event(
    sequence: int, day: dt.date, kind: EventKind, subject: str, detail: str = ""
) -> Event:
    """One journal line."""
    return Event(sequence=sequence, day=day, kind=kind, subject=subject, detail=detail)


def test_an_empty_journal_has_no_months():
    assert by_month([]) == []


def test_a_filing_is_counted_in_its_month():
    journal = [an_event(1, dt.date(2025, 6, 16), EventKind.FILED, "application 1")]
    assert by_month(journal) == [Month(key="2025-06", filed=1)]


def test_two_months_come_out_earliest_first():
    journal = [
        an_event(1, dt.date(2025, 7, 1), EventKind.FILED, "application 2"),
        an_event(2, dt.date(2025, 6, 16), EventKind.FILED, "application 1"),
    ]
    assert [one.key for one in by_month(journal)] == ["2025-06", "2025-07"]


def test_every_counted_kind_lands_in_its_column():
    day = dt.date(2025, 6, 16)
    journal = [
        an_event(1, day, EventKind.FILED, "application 1"),
        an_event(2, day, EventKind.ISSUED, "P-000001"),
        an_event(3, day, EventKind.VOIDED, "P-000001"),
        an_event(4, day, EventKind.REFERRED, "E-00001"),
    ]
    got = by_month(journal)[0]
    assert (got.filed, got.issued, got.voided, got.referred) == (1, 1, 1, 1)


def test_a_kind_nobody_counts_is_ignored():
    journal = [an_event(1, dt.date(2025, 6, 16), EventKind.QUOTED, "application 1")]
    assert by_month(journal) == []


def test_a_month_prints_its_counts():
    made = Month(key="2025-06", filed=3, issued=2, voided=1)
    assert str(made) == "2025-06: 3 filed, 2 issued, 1 voided"


def test_a_month_reports_what_came_in_and_what_went_out():
    made = Month(key="2025-06", filed=3, issued=2)
    assert made.taken == 3
    assert made.done == 2


def test_the_turnaround_follows_the_journal(desk):
    filed = desk.file(an_application())
    desk.issue(filed.key, DECIDED)
    waits = turnarounds(desk.office.history.all())
    assert waits == {"P-000001": 1}


def test_a_permit_issued_the_day_it_was_filed_waits_nothing(desk):
    filed = desk.file(an_application())
    desk.issue(filed.key, an_application().filed_on)
    assert turnarounds(desk.office.history.all()) == {"P-000001": 0}


def test_an_application_never_issued_is_not_measured(desk):
    desk.file(an_application())
    assert turnarounds(desk.office.history.all()) == {}


def test_two_permits_are_both_measured(desk):
    first = desk.file(an_application())
    desk.issue(first.key, DECIDED)
    second = desk.file(an_application())
    desk.issue(second.key, DECIDED)
    assert len(turnarounds(desk.office.history.all())) == 2


def test_an_issue_line_naming_no_application_is_skipped():
    journal = [an_event(1, dt.date(2025, 6, 17), EventKind.ISSUED, "P-000001", "VANCE")]
    assert turnarounds(journal) == {}


def test_the_average_of_nothing_is_zero():
    assert average_days({}) == 0.0


def test_the_average_is_the_mean():
    assert average_days({"a": 1, "b": 2, "c": 3}) == 2.0


def test_the_average_is_rounded_to_two_places():
    assert average_days({"a": 1, "b": 2}) == 1.5


def test_the_sheet_says_when_nothing_came_through():
    assert "nothing has come through" in text(workload_sheet([]))


def test_the_sheet_lists_the_months(desk):
    filed = desk.file(an_application())
    desk.issue(filed.key, DECIDED)
    printed = text(workload_sheet(desk.office.history.all()))
    assert "counter workload" in printed
    assert "2025-06" in printed


def test_the_sheet_reports_the_average(desk):
    filed = desk.file(an_application())
    desk.issue(filed.key, DECIDED)
    assert "average days  1.00" in text(workload_sheet(desk.office.history.all()))


def test_the_sheet_reports_the_slowest(desk):
    filed = desk.file(an_application())
    desk.issue(filed.key, DECIDED)
    assert "slowest       1" in text(workload_sheet(desk.office.history.all()))


def test_the_sheet_counts_what_it_measured(desk):
    filed = desk.file(an_application())
    desk.issue(filed.key, DECIDED)
    desk.file(an_application())
    printed = text(workload_sheet(desk.office.history.all()))
    assert "filed         2" in printed
    assert "measured      1" in printed
