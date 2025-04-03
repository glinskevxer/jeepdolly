import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.party.carrier import MAX_NAME, MAX_USDOT, STATES, Carrier


def a_carrier(**over: object) -> Carrier:
    """A carrier on file, with any part of it swapped out."""
    kw: dict[str, object] = {
        "code": "VANCE",
        "name": "Vance Heavy Haul",
        "usdot": 1184062,
        "home_state": "MT",
    }
    kw.update(over)
    return Carrier(**kw)  # type: ignore[arg-type]


def test_carrier_normalises_the_code():
    assert a_carrier(code="vance").code == "VANCE"


def test_carrier_collapses_whitespace_in_the_name():
    assert a_carrier(name="Vance   Heavy\tHaul").name == "Vance Heavy Haul"


def test_carrier_refuses_an_empty_name():
    with pytest.raises(BadValueError):
        a_carrier(name="   ")


def test_carrier_refuses_a_name_that_is_too_long():
    with pytest.raises(BadValueError):
        a_carrier(name="x" * (MAX_NAME + 1))


def test_carrier_takes_the_longest_name():
    assert len(a_carrier(name="x" * MAX_NAME).name) == MAX_NAME


def test_carrier_refuses_a_name_that_is_not_text():
    with pytest.raises(BadValueError):
        a_carrier(name=12)


def test_carrier_upper_cases_the_state():
    assert a_carrier(home_state="mt").home_state == "MT"


def test_carrier_trims_the_state():
    assert a_carrier(home_state=" MT ").home_state == "MT"


def test_carrier_refuses_a_state_it_does_not_know():
    with pytest.raises(BadValueError):
        a_carrier(home_state="ZZ")


def test_carrier_refuses_a_state_that_is_not_text():
    with pytest.raises(BadValueError):
        a_carrier(home_state=30)


@pytest.mark.parametrize("state", sorted(STATES))
def test_every_listed_state_is_accepted(state):
    assert a_carrier(home_state=state).home_state == state


def test_the_state_list_has_the_district_and_puerto_rico():
    assert "DC" in STATES
    assert "PR" in STATES


def test_carrier_refuses_usdot_zero():
    with pytest.raises(BadValueError):
        a_carrier(usdot=0)


def test_carrier_refuses_a_usdot_that_is_too_big():
    with pytest.raises(BadValueError):
        a_carrier(usdot=MAX_USDOT + 1)


def test_carrier_takes_the_biggest_usdot():
    assert a_carrier(usdot=MAX_USDOT).usdot == MAX_USDOT


def test_carrier_refuses_a_bool_usdot():
    with pytest.raises(BadValueError):
        a_carrier(usdot=True)


def test_carrier_refuses_a_float_usdot():
    with pytest.raises(BadValueError):
        a_carrier(usdot=1184062.0)


def test_carrier_defaults_to_active():
    assert a_carrier().active


def test_carrier_refuses_a_non_bool_active():
    with pytest.raises(BadValueError):
        a_carrier(active="yes")


def test_an_active_carrier_may_be_issued_a_permit():
    assert a_carrier().issuable


def test_an_inactive_carrier_may_not():
    assert not a_carrier(active=False).issuable


def test_retired_turns_the_flag_off():
    assert not a_carrier().retired().active


def test_retired_keeps_everything_else():
    original = a_carrier()
    gone = original.retired()
    assert (gone.code, gone.name, gone.usdot, gone.home_state) == (
        original.code,
        original.name,
        original.usdot,
        original.home_state,
    )


def test_restored_turns_the_flag_back_on():
    assert a_carrier(active=False).restored().active


def test_retiring_twice_is_the_same_as_once():
    assert a_carrier().retired().retired() == a_carrier().retired()


def test_renamed_changes_only_the_name():
    changed = a_carrier().renamed("Vance Transport")
    assert changed.name == "Vance Transport"
    assert changed.code == a_carrier().code


def test_renamed_keeps_the_inactive_flag():
    assert not a_carrier(active=False).renamed("Other").active


def test_renamed_refuses_an_empty_name():
    with pytest.raises(BadValueError):
        a_carrier().renamed("  ")


def test_carrier_prints_its_dot_number():
    assert str(a_carrier()) == "VANCE Vance Heavy Haul, USDOT 1184062"


def test_an_inactive_carrier_says_so_when_printed():
    assert str(a_carrier(active=False)).endswith("(inactive)")


def test_carriers_order_by_code():
    first = a_carrier(code="AAA", usdot=1)
    assert sorted([a_carrier(), first])[0] is first


def test_carriers_with_the_same_parts_are_equal():
    assert a_carrier() == a_carrier()


def test_carrier_is_frozen():
    with pytest.raises(AttributeError):
        a_carrier().name = "Other"  # type: ignore[misc]
