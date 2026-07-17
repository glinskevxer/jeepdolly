from jeepdolly.billing.account import Account, Entry, EntryKind
from jeepdolly.permit.revoke import Cause
from jeepdolly.report.carrier import RECENT, CarrierFile, carrier_sheet
from jeepdolly.units.money import cents

from .conftest import DECIDED, an_application


def text(lines: list[str]) -> str:
    """The lines joined, for a substring check."""
    return "\n".join(lines)


def a_file(desk, permits=(), entries=()) -> CarrierFile:
    """The carrier file as the report command builds it."""
    office = desk.office
    return CarrierFile(
        carrier=office.carriers.get("VANCE"),
        rigs=tuple(office.rigs.for_carrier("VANCE")),
        permits=tuple(permits),
        account=Account(carrier="VANCE", entries=tuple(entries)),  # type: ignore[arg-type]
        events=tuple(office.history.all()),
    )


def test_the_sheet_names_the_carrier(desk):
    printed = text(carrier_sheet(a_file(desk)))
    assert "carrier file VANCE" in printed
    assert "Vance Heavy Haul" in printed


def test_the_sheet_shows_the_federal_number(desk):
    assert "1184062" in text(carrier_sheet(a_file(desk)))


def test_the_sheet_says_the_carrier_is_active(desk):
    assert "active" in text(carrier_sheet(a_file(desk)))


def test_a_retired_carrier_says_so(desk):
    desk.office.carriers.save(desk.office.carriers.get("VANCE").retired())
    assert "retired" in text(carrier_sheet(a_file(desk)))


def test_the_sheet_lists_the_rigs(desk):
    printed = text(carrier_sheet(a_file(desk)))
    assert "R-00001" in printed
    assert "3S2" in printed


def test_the_sheet_shows_the_rig_gross(desk):
    assert "80,000 lb" in text(carrier_sheet(a_file(desk)))


def test_the_sheet_says_when_there_are_no_permits(desk):
    assert "none issued" in text(carrier_sheet(a_file(desk)))


def test_the_sheet_lists_a_permit(desk, issued):
    printed = text(carrier_sheet(a_file(desk, permits=[issued])))
    assert str(issued.number) in printed
    assert "issued" in printed


def test_the_sheet_counts_the_live_permits(desk, issued):
    made = a_file(desk, permits=[issued])
    assert len(made.live_permits) == 1
    assert "still live  1" in text(carrier_sheet(made))


def test_a_void_permit_is_not_live(desk, issued):
    gone = desk.void(str(issued.number), Cause.CANCELLED, DECIDED)
    made = a_file(desk, permits=[gone])
    assert made.live_permits == ()
    assert made.voided == 1


def test_a_void_permit_is_not_counted_as_spent(desk, issued):
    gone = desk.void(str(issued.number), Cause.CANCELLED, DECIDED)
    assert int(a_file(desk, permits=[gone]).spent) == 0


def test_a_live_permit_is_counted_as_spent(desk, issued):
    assert int(a_file(desk, permits=[issued]).spent) == int(issued.fee)


def test_the_sheet_shows_the_balance(desk):
    entry = Entry(
        day=DECIDED,
        sequence=1,
        carrier="VANCE",  # type: ignore[arg-type]
        kind=EntryKind.DEPOSIT,
        amount=cents(100000),
    )
    assert "$1,000.00" in text(carrier_sheet(a_file(desk, entries=[entry])))


def test_the_sheet_shows_the_headroom(desk):
    assert "headroom" in text(carrier_sheet(a_file(desk)))


def test_the_sheet_shows_recent_activity(desk, issued):
    printed = text(carrier_sheet(a_file(desk, permits=[issued])))
    assert "recent activity" in printed


def test_the_sheet_shows_only_the_last_few_permits(desk):
    permits = []
    for _ in range(RECENT + 3):
        filed = desk.file(an_application())
        permits.append(desk.issue(filed.key, DECIDED))
    printed = text(carrier_sheet(a_file(desk, permits=permits)))
    assert str(permits[0].number) not in printed
    assert str(permits[-1].number) in printed


def test_the_sheet_still_counts_every_permit(desk):
    permits = []
    for _ in range(RECENT + 3):
        filed = desk.file(an_application())
        permits.append(desk.issue(filed.key, DECIDED))
    assert f"issued      {RECENT + 3}" in text(carrier_sheet(a_file(desk, permits=permits)))


def test_the_file_prints_a_summary(desk, issued):
    made = a_file(desk, permits=[issued])
    assert str(made).startswith("VANCE: 1 rigs, 1 permits")


def test_a_carrier_with_no_rigs_says_so(desk):
    desk.office.rigs.remove("R-00001")
    assert "none on file" in text(carrier_sheet(a_file(desk)))
