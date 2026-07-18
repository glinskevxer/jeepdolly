from collections.abc import Callable

from click.testing import Result

from tests.cli.test_permit import apply_one


def with_wires(stocked: Callable[..., Result]) -> None:
    """Hang a power line and a railway bridge over the corridor."""
    stocked(
        "road",
        "structure",
        "--segment",
        "SEG-AB",
        "--name",
        "Reserve Street crossing",
        "--kind",
        "overhead",
        "--milepost",
        "8.00",
        "--clearance",
        "15'4\"",
        "--owner",
        "Missoula Electric",
        "--notice-days",
        "3",
    )
    stocked(
        "road",
        "structure",
        "--segment",
        "SEG-BD",
        "--name",
        "MRL overpass",
        "--kind",
        "overhead",
        "--milepost",
        "4.00",
        "--clearance",
        "15'0\"",
        "--owner",
        "Montana Rail Link",
        "--notice-days",
        "10",
    )


def issued(stocked: Callable[..., Result], **over: str) -> Result:
    """File and issue one permit for a tall load."""
    apply_one(stocked, **{"--height": "15'0\"", **over})
    result = stocked("permit", "issue", "1", "--on", "2025-06-17")
    assert result.exit_code == 0, result.output
    return result


def test_an_empty_map_lists_no_owners(stocked):
    assert "nobody on file owns anything" in stocked("road", "owners").output


def test_an_owner_shows_up_once_recorded(stocked):
    with_wires(stocked)
    assert "Missoula Electric" in stocked("road", "owners").output


def test_asking_for_one_owner_lists_what_they_own(stocked):
    with_wires(stocked)
    output = stocked("road", "owners", "--owner", "Missoula Electric").output
    assert "Reserve Street" in output


def test_an_owner_with_nothing_on_file_says_so(stocked):
    with_wires(stocked)
    assert "nothing on file" in stocked("road", "owners", "--owner", "Nobody").output


def test_a_tall_load_gets_a_call_sheet(stocked):
    with_wires(stocked)
    issued(stocked)
    output = stocked("report", "notices", "P-000001", "--on", "2025-06-01").output
    assert "Missoula Electric" in output


def test_the_call_sheet_names_the_permit(stocked):
    with_wires(stocked)
    issued(stocked)
    assert "P-000001" in stocked("report", "notices", "P-000001", "--on", "2025-06-01").output


def test_a_short_load_needs_no_calls(stocked):
    with_wires(stocked)
    apply_one(stocked, **{"--height": "10'0\""})
    stocked("permit", "issue", "1", "--on", "2025-06-17")
    output = stocked("report", "notices", "P-000001", "--on", "2025-06-01").output
    assert "nobody has to be told" in output


def test_a_permit_on_a_bare_map_needs_no_calls(stocked):
    issued(stocked)
    output = stocked("report", "notices", "P-000001", "--on", "2025-06-01").output
    assert "nobody has to be told" in output


def test_a_late_call_sheet_says_so(stocked):
    with_wires(stocked)
    issued(stocked)
    output = stocked("report", "notices", "P-000001", "--on", "2025-06-17").output
    assert "already late" in output


def test_the_call_sheet_for_an_unknown_permit_fails(stocked):
    assert stocked("report", "notices", "P-999999").exit_code != 0
