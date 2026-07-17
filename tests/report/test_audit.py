from jeepdolly.billing.account import Account, Entry, EntryKind
from jeepdolly.permit.revoke import Cause
from jeepdolly.report.audit import Audit, Finding, audit, audit_sheet
from jeepdolly.store.history import Event, EventKind
from jeepdolly.units.money import cents

from .conftest import DECIDED


def text(lines: list[str]) -> str:
    """The lines joined, for a substring check."""
    return "\n".join(lines)


def a_charge(reference: str, amount: int, sequence: int = 1) -> Entry:
    """One charge entry against a permit."""
    return Entry(
        day=DECIDED,
        sequence=sequence,
        carrier="VANCE",  # type: ignore[arg-type]
        kind=EntryKind.CHARGE,
        amount=cents(amount),
        reference=reference,
    )


def a_refund(reference: str, amount: int, sequence: int = 2) -> Entry:
    """One refund entry against a permit."""
    return Entry(
        day=DECIDED,
        sequence=sequence,
        carrier="VANCE",  # type: ignore[arg-type]
        kind=EntryKind.REFUND,
        amount=cents(amount),
        reference=reference,
        note="void",
    )


def an_account(*entries: Entry) -> Account:
    """One carrier's account holding these entries."""
    return Account(carrier="VANCE", entries=entries)  # type: ignore[arg-type]


def test_a_charged_permit_audits_clean(issued):
    account = an_account(a_charge(str(issued.number), int(issued.fee)))
    got = audit("VANCE", [issued], account, [])
    assert got.clean
    assert int(got.gap) == 0


def test_an_uncharged_permit_is_reported(issued):
    got = audit("VANCE", [issued], an_account(), [])
    assert not got.clean
    assert "never charged" in str(got.findings[0])


def test_an_uncharged_permit_shows_the_gap(issued):
    got = audit("VANCE", [issued], an_account(), [])
    assert int(got.gap) == int(issued.fee)


def test_a_wrong_charge_is_reported(issued):
    account = an_account(a_charge(str(issued.number), int(issued.fee) + 500))
    got = audit("VANCE", [issued], account, [])
    assert "against a fee of" in str(got.findings[0])


def test_a_charge_against_no_permit_is_reported(issued):
    account = an_account(
        a_charge(str(issued.number), int(issued.fee)), a_charge("P-000099", 1000, 2)
    )
    got = audit("VANCE", [issued], account, [])
    assert "no permit of this carrier" in str(got.findings[0])


def test_a_voided_and_refunded_permit_audits_clean(desk, issued):
    from jeepdolly.units.money import cents as money

    desk.office.accounts.deposit("VANCE", DECIDED, money(100000))
    desk.office.accounts.charge("VANCE", DECIDED, issued.fee, str(issued.number))
    gone = desk.void(str(issued.number), Cause.CANCELLED, DECIDED)
    got = audit(
        "VANCE",
        [gone],
        desk.office.accounts.account("VANCE"),
        desk.office.history.all(),
    )
    assert got.clean


def test_a_voided_permit_that_was_not_refunded_is_reported(issued):
    gone = issued.voided("cancelled", DECIDED)
    account = an_account(a_charge(str(gone.number), int(gone.fee)))
    logged = [Event(sequence=1, day=DECIDED, kind=EventKind.VOIDED, subject=str(gone.number))]
    got = audit("VANCE", [gone], account, logged)
    assert "not refunded" in str(got.findings[0])


def test_a_void_with_no_journal_line_is_reported(issued):
    gone = issued.voided("cancelled", DECIDED)
    account = an_account(
        a_charge(str(gone.number), int(gone.fee)), a_refund(str(gone.number), int(gone.fee))
    )
    got = audit("VANCE", [gone], account, [])
    assert "no journal line" in str(got.findings[0])


def test_another_carriers_permit_is_left_out(issued):
    got = audit("OTHER", [issued], Account(carrier="OTHER", entries=()), [])  # type: ignore[arg-type]
    assert got.clean
    assert int(got.owed) == 0


def test_a_voided_permit_is_not_owed(issued):
    gone = issued.voided("cancelled", DECIDED)
    logged = [Event(sequence=1, day=DECIDED, kind=EventKind.VOIDED, subject=str(gone.number))]
    got = audit("VANCE", [gone], an_account(), logged)
    assert int(got.owed) == 0


def test_a_clean_audit_prints_that_the_records_agree(issued):
    account = an_account(a_charge(str(issued.number), int(issued.fee)))
    assert "the records agree" in str(audit("VANCE", [issued], account, []))


def test_a_dirty_audit_prints_how_far_apart(issued):
    assert "apart" in str(audit("VANCE", [issued], an_account(), []))


def test_a_finding_prints_its_amount():
    made = Finding(subject="P-000001", problem="never charged", amount=cents(9752))
    assert str(made) == "P-000001: never charged $97.52"


def test_a_finding_without_an_amount_prints_plainly():
    assert str(Finding(subject="P-000001", problem="no journal line")) == (
        "P-000001: no journal line"
    )


def test_the_sheet_says_when_there_are_no_carriers():
    assert "no carriers on file" in text(audit_sheet([]))


def test_the_sheet_lists_every_carrier(issued):
    account = an_account(a_charge(str(issued.number), int(issued.fee)))
    got = audit("VANCE", [issued], account, [])
    assert "VANCE" in text(audit_sheet([got]))


def test_the_sheet_lists_the_problems(issued):
    got = audit("VANCE", [issued], an_account(), [])
    printed = text(audit_sheet([got]))
    assert "VANCE problems" in printed
    assert "never charged" in printed


def test_the_sheet_counts_the_clean_carriers(issued):
    account = an_account(a_charge(str(issued.number), int(issued.fee)))
    got = audit("VANCE", [issued], account, [])
    assert "clean     1" in text(audit_sheet([got]))


def test_an_empty_audit_of_a_carrier_with_no_permits_is_clean():
    got = audit("VANCE", [], an_account(), [])
    assert got.clean
    assert isinstance(got, Audit)


def test_two_charges_against_one_permit_add_up(issued):
    account = an_account(
        a_charge(str(issued.number), 1000, 1), a_charge(str(issued.number), 2000, 2)
    )
    got = audit("VANCE", [issued], account, [])
    assert int(got.charged) == 3000


def test_a_repeated_day_of_dates_is_irrelevant_to_the_audit(issued):
    account = an_account(a_charge(str(issued.number), int(issued.fee)))
    first = audit("VANCE", [issued], account, [])
    second = audit("VANCE", [issued], account, [])
    assert first == second


def test_the_audit_is_reproducible(issued):
    account = an_account(a_charge(str(issued.number), int(issued.fee) + 1))
    runs = {tuple(str(f) for f in audit("VANCE", [issued], account, []).findings)}
    for _ in range(3):
        runs.add(tuple(str(f) for f in audit("VANCE", [issued], account, []).findings))
    assert len(runs) == 1
