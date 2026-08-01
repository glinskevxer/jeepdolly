from collections.abc import Callable

from click.testing import Result

from tests.cli.test_permit import apply_one

ON = ("--on", "2025-06-19")


def issued(stocked: Callable[..., Result]) -> Result:
    """File and issue one permit, so there is something to weigh."""
    apply_one(stocked)
    result = stocked("permit", "issue", "1", "--on", "2025-06-17")
    assert result.exit_code == 0, result.output
    return result


def weigh(stocked: Callable[..., Result], *axles: str) -> Result:
    """Weigh the issued permit's rig on a set of pads."""
    flat: list[str] = []
    for one in axles:
        flat.extend(["--axle", one])
    return stocked(
        "enforce",
        "weigh",
        "P-000001",
        *flat,
        "--place",
        "Bonner scales",
        "--officer",
        "Sgt Ramos",
        *ON,
    )


def test_a_rig_inside_its_permit_is_clean(stocked):
    issued(stocked)
    result = weigh(stocked, "12,000", "17,000", "17,000", "17,000", "17,000")
    assert result.exit_code == 0, result.output
    assert "inside the permit" in result.output


def test_a_rig_over_its_permit_is_priced(stocked):
    issued(stocked)
    result = weigh(stocked, "20,000", "25,000", "25,000", "25,000", "25,000")
    assert "gross over permit" in result.output
    assert "penalties" in result.output


def test_weighing_writes_the_ticket(stocked):
    issued(stocked)
    weigh(stocked, "12,000", "17,000", "17,000", "17,000", "17,000")
    assert "WT-00001" in stocked("enforce", "tickets", "P-000001").output


def test_a_permit_never_weighed_says_so(stocked):
    issued(stocked)
    assert "never been weighed" in stocked("enforce", "tickets", "P-000001").output


def test_a_ticket_lists_its_pads(stocked):
    issued(stocked)
    weigh(stocked, "12,000", "17,000", "17,000", "17,000", "17,000")
    output = stocked("enforce", "ticket", "WT-00001").output
    assert "axle 1" in output
    assert "gross" in output


def test_a_clean_carrier_has_nothing_against_it(stocked):
    issued(stocked)
    assert "nothing against it" in stocked("enforce", "record", "VANCE").output


def test_an_overweight_carrier_gets_a_record(stocked):
    issued(stocked)
    weigh(stocked, "20,000", "25,000", "25,000", "25,000", "25,000")
    output = stocked("enforce", "record", "VANCE").output
    assert "VANCE" in output
    assert "violations" in output


def test_a_second_offence_costs_more_than_the_first(stocked):
    issued(stocked)
    first = weigh(stocked, "20,000", "25,000", "25,000", "25,000", "25,000")
    second = weigh(stocked, "20,000", "25,000", "25,000", "25,000", "25,000")
    assert first.output != second.output


def test_the_penalty_lands_on_the_carriers_account(stocked):
    issued(stocked)
    weigh(stocked, "20,000", "25,000", "25,000", "25,000", "25,000")
    assert "WT-00001" in stocked("account", "statement", "VANCE").output


def test_weighing_an_unknown_permit_fails(stocked):
    assert weigh(stocked, "12,000").exit_code != 0


def test_a_ticket_that_was_never_written_fails(stocked):
    assert stocked("enforce", "ticket", "WT-99999").exit_code != 0


def test_a_carrier_that_is_not_on_file_fails(stocked):
    assert stocked("enforce", "record", "NOBODY").exit_code != 0


def test_the_journal_records_the_weighing(stocked):
    issued(stocked)
    weigh(stocked, "12,000", "17,000", "17,000", "17,000", "17,000")
    assert "weighed" in stocked("history", "show", "--about", "P-000001").output
