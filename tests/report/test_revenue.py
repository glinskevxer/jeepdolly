import datetime as dt

from jeepdolly.billing.account import Account, Entry, EntryKind
from jeepdolly.report.revenue import (
    by_carrier,
    by_code,
    by_month,
    counted,
    month_of,
    reconcile,
    revenue_sheet,
    within,
)
from jeepdolly.units.clock import DaySpan
from jeepdolly.units.money import cents

from .conftest import DECIDED, a_load, an_application

JUNE = DaySpan(dt.date(2025, 6, 1), dt.date(2025, 6, 30))
JULY = DaySpan(dt.date(2025, 7, 1), dt.date(2025, 7, 31))


def text(lines: list[str]) -> str:
    return "\n".join(lines)


def test_month_of_pads_the_month():
    assert month_of(dt.date(2025, 6, 19)) == "2025-06"


def test_month_of_sorts_as_text():
    assert month_of(dt.date(2025, 9, 1)) < month_of(dt.date(2025, 10, 1))


def test_counted_keeps_an_active_permit(issued):
    assert counted([issued]) == [issued]


def test_counted_drops_a_void_permit(desk, issued):
    gone = desk.void(str(issued.number), "cancelled", DECIDED)
    assert counted([gone]) == []


def test_counted_keeps_a_superseded_permit(desk, issued):
    second = desk.issue(desk.file(an_application(load=a_load())).key, DECIDED)
    desk.office.permits.save_state(issued.superseded_by(second.number))
    both = desk.office.permits.all()
    assert len(counted(both)) == 2


def test_counted_is_in_number_order(desk, issued):
    desk.issue(desk.file(an_application()).key, DECIDED)
    numbers = [str(p.number) for p in counted(desk.office.permits.all())]
    assert numbers == sorted(numbers)


def test_by_month_buckets_the_take(issued):
    got = by_month([issued])
    assert len(got) == 1
    assert got[0].key == "2025-06"
    assert got[0].permits == 1


def test_by_month_adds_the_fees(desk, issued):
    second = desk.issue(desk.file(an_application()).key, DECIDED)
    got = by_month([issued, second])
    assert int(got[0].amount) == int(issued.fee) + int(second.fee)


def test_by_carrier_buckets_the_take(issued):
    got = by_carrier([issued])
    assert got[0].key == "VANCE"


def test_by_code_counts_each_line(issued):
    codes = {t.key for t in by_code([issued])}
    assert "TRIP" in codes
    assert "MILES" in codes


def test_by_code_amounts_add_to_the_fee(issued):
    assert sum(int(t.amount) for t in by_code([issued])) == int(issued.fee)


def test_a_take_prints_its_bucket(issued):
    assert "VANCE" in str(by_carrier([issued])[0])


def test_within_keeps_a_permit_in_the_span(issued):
    assert within([issued], JUNE) == [issued]


def test_within_drops_a_permit_outside_the_span(issued):
    assert within([issued], JULY) == []


def test_reconcile_is_zero_when_they_agree(desk, issued):
    entry = Entry(
        day=DECIDED,
        sequence=1,
        carrier="VANCE",  # type: ignore[arg-type]
        kind=EntryKind.CHARGE,
        amount=issued.fee,
        reference=str(issued.number),
    )
    account = Account(carrier="VANCE", entries=(entry,))  # type: ignore[arg-type]
    assert int(reconcile([issued], account)) == 0


def test_reconcile_shows_an_uncharged_permit(issued):
    account = Account(carrier="VANCE", entries=())  # type: ignore[arg-type]
    assert int(reconcile([issued], account)) == int(issued.fee)


def test_reconcile_ignores_another_carriers_permits(issued):
    account = Account(carrier="OTHER", entries=())  # type: ignore[arg-type]
    assert int(reconcile([issued], account)) == 0


def test_reconcile_shows_an_overcharge(issued):
    entry = Entry(
        day=DECIDED,
        sequence=1,
        carrier="VANCE",  # type: ignore[arg-type]
        kind=EntryKind.CHARGE,
        amount=cents(int(issued.fee) + 100),
        reference=str(issued.number),
    )
    account = Account(carrier="VANCE", entries=(entry,))  # type: ignore[arg-type]
    assert int(reconcile([issued], account)) == -100


def test_the_sheet_says_when_there_is_nothing():
    assert "nothing to report" in text(revenue_sheet([]))


def test_the_sheet_has_all_three_sections(issued):
    printed = text(revenue_sheet([issued]))
    assert "by month" in printed
    assert "by carrier" in printed
    assert "by fee line" in printed


def test_the_sheet_totals_the_take(issued):
    from jeepdolly.units.money import format_money

    assert format_money(issued.fee) in text(revenue_sheet([issued]))


def test_the_sheet_counts_the_voided(desk, issued):
    gone = desk.void(str(issued.number), "cancelled", DECIDED)
    printed = text(revenue_sheet([gone]))
    assert "nothing to report" in printed


def test_the_sheet_names_its_span(issued):
    assert "2025-06-01..2025-06-30" in text(revenue_sheet([issued], JUNE))


def test_the_sheet_filters_by_span(issued):
    assert "nothing to report" in text(revenue_sheet([issued], JULY))
