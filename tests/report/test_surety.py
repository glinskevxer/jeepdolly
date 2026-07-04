import datetime as dt

import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.party.surety import Certificate, Cover
from jeepdolly.permit.application import Kind
from jeepdolly.report.surety import CHASE_WITHIN, chases, cover_sheet, lapsed
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


def test_the_default_chase_window_is_a_month():
    assert CHASE_WITHIN == 30


def test_a_certificate_running_out_soon_is_chased():
    held = [a_certificate(span=DaySpan(JAN, dt.date(2025, 7, 10)))]
    assert [one.carrier for one in chases(held, JUN)] == ["VANCE"]


def test_a_certificate_with_months_left_is_not_chased():
    assert chases([a_certificate()], JUN) == []


def test_the_chase_list_is_soonest_first():
    early = a_certificate(policy="A", span=DaySpan(JAN, dt.date(2025, 7, 2)))
    late = a_certificate(policy="B", span=DaySpan(JAN, dt.date(2025, 7, 20)))
    assert [one.policy for one in chases([late, early], JUN)] == ["A", "B"]


def test_a_lapsed_certificate_is_not_on_the_chase_list():
    held = [a_certificate(span=DaySpan(dt.date(2024, 1, 1), dt.date(2024, 6, 1)))]
    assert chases(held, JUN) == []


def test_a_lapsed_certificate_is_on_the_lapsed_list():
    held = [a_certificate(span=DaySpan(dt.date(2024, 1, 1), dt.date(2024, 6, 1)))]
    assert len(lapsed(held, JUN)) == 1


def test_the_lapsed_list_is_longest_gone_first():
    old = a_certificate(policy="OLD", span=DaySpan(JAN, dt.date(2025, 2, 1)))
    new = a_certificate(policy="NEW", span=DaySpan(JAN, dt.date(2025, 5, 1)))
    assert [one.policy for one in lapsed([new, old], JUN)] == ["OLD", "NEW"]


def test_a_lapsed_line_says_how_long_ago():
    held = [a_certificate(span=DaySpan(JAN, dt.date(2025, 6, 20)))]
    assert "lapsed 10 days ago" in str(lapsed(held, JUN)[0])


def test_a_chased_line_says_how_long_is_left():
    held = [a_certificate(span=DaySpan(JAN, dt.date(2025, 7, 10)))]
    assert "has 11 days left" in str(chases(held, JUN)[0])


def test_the_last_day_still_counts_as_good():
    held = [a_certificate(span=DaySpan(JAN, JUN))]
    assert lapsed(held, JUN) == []
    assert len(chases(held, JUN)) == 1


def test_a_datetime_is_refused_by_the_chase_list():
    with pytest.raises(BadValueError):
        chases([a_certificate()], dt.datetime(2025, 6, 30, tzinfo=dt.UTC))


def test_a_datetime_is_refused_by_the_lapsed_list():
    with pytest.raises(BadValueError):
        lapsed([a_certificate()], dt.datetime(2025, 6, 30, tzinfo=dt.UTC))


def test_an_empty_file_prints_nothing_to_chase():
    lines = cover_sheet([], JUN)
    assert any("nothing to chase" in line for line in lines)


def test_the_sheet_names_the_day_it_was_run():
    assert any("2025" in line for line in cover_sheet([], JUN))


def test_the_sheet_puts_the_lapsed_section_first():
    held = [
        a_certificate(policy="GONE", span=DaySpan(JAN, dt.date(2025, 5, 1))),
        a_certificate(policy="SOON", span=DaySpan(JAN, dt.date(2025, 7, 10))),
    ]
    lines = cover_sheet(held, JUN)
    body = "\n".join(lines)
    assert body.index("already lapsed") < body.index("running out")


def test_the_sheet_counts_what_it_found():
    held = [a_certificate(span=DaySpan(JAN, dt.date(2025, 7, 10)))]
    assert any("running out" in line and "1" in line for line in cover_sheet(held, JUN))


def test_asking_against_a_kind_adds_the_shortfall_section():
    held = [a_certificate(amount=cents(10_000_00))]
    lines = cover_sheet(held, JUN, against=Kind.TRIP)
    assert any("short for a trip permit" in line for line in lines)


def test_the_shortfall_section_names_the_missing_cover():
    held = [a_certificate(amount=cents(10_000_00))]
    body = "\n".join(cover_sheet(held, JUN, against=Kind.TRIP))
    assert "public liability" in body


def test_a_carrier_that_is_clear_gets_no_shortfall_section():
    held = [
        a_certificate(cover=Cover.BOND, amount=cents(50_000_00)),
        a_certificate(cover=Cover.LIABILITY, policy="L-1", amount=cents(750_000_00)),
    ]
    body = "\n".join(cover_sheet(held, JUN, against=Kind.TRIP))
    assert "short for" not in body


def test_the_plain_sheet_has_no_shortfall_section():
    held = [a_certificate(amount=cents(10_000_00))]
    assert "short for" not in "\n".join(cover_sheet(held, JUN))


def test_a_wider_window_pulls_in_more_certificates():
    held = [a_certificate(span=DaySpan(JAN, dt.date(2025, 9, 1)))]
    assert chases(held, JUN) == []
    assert len(chases(held, JUN, 90)) == 1
