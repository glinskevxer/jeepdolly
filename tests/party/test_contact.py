import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.party.contact import MAX_EMAIL, MAX_NAME, Contact, Role, digits_of, format_number


def a_contact(**over: object) -> Contact:
    """A dispatcher at a carrier, with any part of it swapped out."""
    kw: dict[str, object] = {
        "carrier": "VANCE",
        "role": Role.DISPATCH,
        "name": "Ruth Halloran",
        "number": "(406) 555-0142",
    }
    kw.update(over)
    return Contact(**kw)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "typed",
    [
        "(406) 555-0142",
        "406-555-0142",
        "406.555.0142",
        "4065550142",
        "1 406 555 0142",
        "+1 (406) 555-0142",
    ],
)
def test_every_way_a_number_arrives_stores_the_same(typed):
    assert digits_of(typed) == "4065550142"


def test_a_short_number_is_refused():
    with pytest.raises(BadValueError):
        digits_of("555-0142")


def test_a_long_number_is_refused():
    with pytest.raises(BadValueError):
        digits_of("406 555 0142 99")


def test_a_number_that_is_not_text_is_refused():
    with pytest.raises(BadValueError):
        digits_of(4065550142)  # type: ignore[arg-type]


def test_a_stored_number_prints_punctuated():
    assert format_number("4065550142") == "(406) 555-0142"


def test_the_printed_number_round_trips():
    assert digits_of(format_number("4065550142")) == "4065550142"


def test_a_contact_stores_the_digits():
    assert a_contact().number == "4065550142"


def test_a_contact_prints_its_number():
    assert a_contact().printed == "(406) 555-0142"


def test_a_contact_normalises_the_carrier():
    assert a_contact(carrier="vance").carrier == "VANCE"


def test_a_contact_collapses_whitespace_in_the_name():
    assert a_contact(name="Ruth   Halloran").name == "Ruth Halloran"


def test_a_contact_refuses_an_empty_name():
    with pytest.raises(BadValueError):
        a_contact(name="  ")


def test_a_contact_refuses_a_name_that_is_too_long():
    with pytest.raises(BadValueError):
        a_contact(name="x" * (MAX_NAME + 1))


def test_a_contact_lower_cases_the_address():
    assert a_contact(email="Ruth@Vance.Example").email == "ruth@vance.example"


def test_a_contact_allows_no_address():
    assert a_contact().email == ""


def test_a_contact_refuses_something_that_is_not_an_address():
    with pytest.raises(BadValueError):
        a_contact(email="ruth at vance")


def test_a_contact_refuses_an_address_that_is_too_long():
    with pytest.raises(BadValueError):
        a_contact(email="x" * MAX_EMAIL + "@vance.example")


def test_a_contact_refuses_an_address_that_is_not_text():
    with pytest.raises(BadValueError):
        a_contact(email=12)


def test_a_contact_refuses_a_non_bool_primary():
    with pytest.raises(BadValueError):
        a_contact(primary="yes")


def test_a_contact_defaults_to_not_primary():
    assert not a_contact().primary


def test_promoting_marks_it_primary():
    assert a_contact().promoted().primary


def test_demoting_takes_it_back():
    assert not a_contact().promoted().demoted().primary


def test_promoting_keeps_everything_else():
    made = a_contact(email="ruth@vance.example").promoted()
    assert made.name == "Ruth Halloran"
    assert made.email == "ruth@vance.example"


def test_a_contact_prints_its_role_and_number():
    assert str(a_contact()) == "VANCE dispatch Ruth Halloran (406) 555-0142"


def test_a_primary_contact_is_starred():
    assert str(a_contact().promoted()).endswith("*")


def test_a_contact_with_an_address_prints_it():
    assert "ruth@vance.example" in str(a_contact(email="ruth@vance.example"))


def test_contacts_order_by_carrier_then_role():
    first = a_contact(role=Role.ACCOUNTS)
    assert sorted([a_contact(), first])[0] is first


def test_every_role_is_accepted():
    for role in Role:
        assert a_contact(role=role).role is role
