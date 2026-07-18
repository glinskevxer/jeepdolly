import datetime as dt

import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.report.notice import late, notice_sheet, still_time
from jeepdolly.route.notice import Notice

FIRST = dt.date(2025, 6, 18)


def a_notice(**over: object) -> Notice:
    kw: dict[str, object] = {
        "tell_by": dt.date(2025, 6, 15),
        "owner": "Missoula Electric",
        "lead_days": 3,
        "places": ("Reserve Street crossing on US-12",),
    }
    kw.update(over)
    return Notice(**kw)  # type: ignore[arg-type]


def test_a_call_still_ahead_is_not_late():
    assert late([a_notice()], dt.date(2025, 6, 14)) == []


def test_a_call_past_its_deadline_is_late():
    assert len(late([a_notice()], FIRST)) == 1


def test_a_call_on_its_deadline_still_has_time():
    assert len(still_time([a_notice()], dt.date(2025, 6, 15))) == 1


def test_the_late_list_is_longest_gone_first():
    early = a_notice(tell_by=dt.date(2025, 6, 1), owner="MRL")
    assert late([a_notice(), early], FIRST)[0].owner == "MRL"


def test_a_datetime_day_is_refused_by_the_late_list():
    with pytest.raises(BadValueError):
        late([a_notice()], dt.datetime(2025, 6, 18, tzinfo=dt.UTC))


def test_a_datetime_day_is_refused_by_the_ahead_list():
    with pytest.raises(BadValueError):
        still_time([a_notice()], dt.datetime(2025, 6, 18, tzinfo=dt.UTC))


def test_a_permit_needing_no_calls_says_so():
    assert any("nobody has to be told" in line for line in notice_sheet([], FIRST))


def test_the_sheet_names_the_permit_when_given_one():
    lines = notice_sheet([], FIRST, "P-000001")
    assert any("P-000001" in line for line in lines)


def test_the_sheet_names_the_day_it_was_run():
    assert any("2025" in line for line in notice_sheet([], FIRST))


def test_the_late_section_comes_first():
    ahead = a_notice(tell_by=dt.date(2025, 6, 20), owner="MRL")
    body = "\n".join(notice_sheet([ahead, a_notice()], FIRST))
    assert body.index("already late") < body.index("still time")


def test_a_sheet_with_nothing_late_has_no_late_section():
    lines = notice_sheet([a_notice()], dt.date(2025, 6, 1))
    heads = [line for line in lines if line.strip() == "already late"]
    assert heads == []


def test_the_sheet_names_the_owner_and_the_place():
    body = "\n".join(notice_sheet([a_notice()], FIRST))
    assert "Missoula Electric" in body
    assert "Reserve Street" in body


def test_one_owner_with_two_places_gets_two_rows():
    both = a_notice(places=("Reserve Street on US-12", "Rattlesnake on SR-200"))
    body = "\n".join(notice_sheet([both], FIRST))
    assert "Rattlesnake" in body
    assert "Reserve Street" in body


def test_the_sheet_counts_the_calls():
    assert any("calls to make" in line for line in notice_sheet([a_notice()], FIRST))


def test_the_sheet_counts_what_is_already_late():
    lines = notice_sheet([a_notice()], FIRST)
    assert any("already late" in line and "1" in line for line in lines)


def test_the_days_column_goes_negative_once_late():
    body = "\n".join(notice_sheet([a_notice()], FIRST))
    assert "-3" in body
