from collections.abc import Callable

import pytest
from click.testing import Result


@pytest.fixture
def with_carriers(run: Callable[..., Result]) -> Callable[..., Result]:
    """An office file with two carriers on it."""
    run(
        "carrier",
        "add",
        "--code",
        "VANCE",
        "--name",
        "Vance Heavy Haul",
        "--usdot",
        "1184062",
        "--state",
        "MT",
    )
    run("carrier", "add", "--code", "OTHER", "--name", "Other", "--usdot", "2", "--state", "ID")
    return run


def add_dispatch(run: Callable[..., Result], code: str = "VANCE", **over: str) -> Result:
    """Record a dispatcher at a carrier."""
    args = {"--name": "Ruth Halloran", "--number": "(406) 555-0142"}
    args.update(over)
    flat: list[str] = []
    for key, value in args.items():
        flat.extend([key, value])
    return run("carrier", "contact", code, *flat)


def test_a_contact_goes_on_file(with_carriers):
    result = add_dispatch(with_carriers)
    assert result.exit_code == 0
    assert "Ruth Halloran" in result.output
    assert "(406) 555-0142" in result.output


def test_a_number_is_tidied_however_it_is_typed(with_carriers):
    result = add_dispatch(with_carriers, **{"--number": "406.555.0142"})
    assert "(406) 555-0142" in result.output


def test_a_short_number_is_refused(with_carriers):
    assert add_dispatch(with_carriers, **{"--number": "555-0142"}).exit_code == 1


def test_a_carrier_that_is_not_there_is_refused(with_carriers):
    assert add_dispatch(with_carriers, "NOBODY").exit_code == 1


def test_a_bad_address_is_refused(with_carriers):
    assert add_dispatch(with_carriers, **{"--email": "ruth at vance"}).exit_code == 1


def test_the_contacts_are_listed(with_carriers):
    add_dispatch(with_carriers)
    assert "Ruth Halloran" in with_carriers("carrier", "contacts", "VANCE").output


def test_the_listing_says_when_there_is_nobody(with_carriers):
    assert "no contacts on file" in with_carriers("carrier", "contacts", "VANCE").output


def test_a_second_role_is_kept_beside_the_first(with_carriers):
    add_dispatch(with_carriers)
    with_carriers(
        "carrier",
        "contact",
        "VANCE",
        "--role",
        "accounts",
        "--name",
        "Dale Okonkwo",
        "--number",
        "4065550188",
    )
    output = with_carriers("carrier", "contacts", "VANCE").output
    assert "Ruth Halloran" in output
    assert "Dale Okonkwo" in output


def test_promoting_marks_the_primary(with_carriers):
    add_dispatch(with_carriers)
    result = with_carriers("carrier", "primary", "VANCE", "--role", "dispatch")
    assert result.exit_code == 0
    assert result.output.strip().endswith("*")


def test_promoting_a_second_demotes_the_first(with_carriers):
    add_dispatch(with_carriers)
    with_carriers(
        "carrier",
        "contact",
        "VANCE",
        "--role",
        "safety",
        "--name",
        "Ana Reyes",
        "--number",
        "4065550199",
    )
    with_carriers("carrier", "primary", "VANCE", "--role", "dispatch")
    with_carriers("carrier", "primary", "VANCE", "--role", "safety")
    output = with_carriers("carrier", "contacts", "VANCE").output
    assert output.count("*") == 1


def test_promoting_somebody_who_is_not_there_is_refused(with_carriers):
    assert with_carriers("carrier", "primary", "VANCE", "--role", "safety").exit_code == 1


def test_a_number_is_looked_up(with_carriers):
    add_dispatch(with_carriers)
    assert "Ruth Halloran" in with_carriers("carrier", "ring", "406-555-0142").output


def test_a_number_nobody_has_says_so(with_carriers):
    assert "nobody on file" in with_carriers("carrier", "ring", "4065559999").output


def test_a_number_at_two_carriers_finds_both(with_carriers):
    add_dispatch(with_carriers)
    add_dispatch(with_carriers, "OTHER", **{"--name": "Sam Ilg"})
    output = with_carriers("carrier", "ring", "4065550142").output
    assert "VANCE" in output
    assert "OTHER" in output


def test_a_bad_number_to_look_up_is_refused(with_carriers):
    assert with_carriers("carrier", "ring", "nonsense").exit_code == 1


def test_the_carrier_sheet_shows_who_to_ring(with_carriers):
    add_dispatch(with_carriers)
    output = with_carriers("report", "carrier", "VANCE").output
    assert "who to ring" in output
    assert "Ruth Halloran" in output


def test_the_carrier_sheet_leaves_the_section_off_when_empty(with_carriers):
    assert "who to ring" not in with_carriers("report", "carrier", "VANCE").output
