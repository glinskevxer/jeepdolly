import pytest

from jeepdolly.errors import NotFoundError
from jeepdolly.party.carrier import Carrier
from jeepdolly.party.contact import Contact, Role
from jeepdolly.store.carriers import CarrierStore
from jeepdolly.store.contacts import ContactStore


def a_contact(**over: object) -> Contact:
    kw: dict[str, object] = {
        "carrier": "VANCE",
        "role": Role.DISPATCH,
        "name": "Ruth Halloran",
        "number": "(406) 555-0142",
    }
    kw.update(over)
    return Contact(**kw)  # type: ignore[arg-type]


@pytest.fixture
def store(office):
    """A contact store with two carriers on file."""
    carriers = CarrierStore(office)
    carriers.add(
        Carrier(code="VANCE", name="Vance Heavy Haul", usdot=1184062, home_state="MT")  # type: ignore[arg-type]
    )
    carriers.add(
        Carrier(code="OTHER", name="Other Haul", usdot=2, home_state="ID")  # type: ignore[arg-type]
    )
    return ContactStore(office)


def test_a_new_store_is_empty(store):
    assert store.count() == 0


def test_a_contact_round_trips(store):
    store.put(a_contact())
    assert store.get("VANCE", Role.DISPATCH).name == "Ruth Halloran"


def test_the_number_round_trips_as_digits(store):
    store.put(a_contact())
    assert store.get("VANCE", Role.DISPATCH).number == "4065550142"


def test_the_address_round_trips(store):
    store.put(a_contact(email="ruth@vance.example"))
    assert store.get("VANCE", Role.DISPATCH).email == "ruth@vance.example"


def test_writing_the_same_role_twice_replaces_it(store):
    store.put(a_contact())
    store.put(a_contact(name="Dale Okonkwo"))
    assert store.count() == 1
    assert store.get("VANCE", Role.DISPATCH).name == "Dale Okonkwo"


def test_two_roles_at_one_carrier_both_stay(store):
    store.put(a_contact())
    store.put(a_contact(role=Role.ACCOUNTS, name="Dale Okonkwo"))
    assert len(store.for_carrier("VANCE")) == 2


def test_a_carrier_that_is_not_there_is_refused(store):
    with pytest.raises(NotFoundError):
        store.put(a_contact(carrier="NOBODY"))


def test_get_raises_when_there_is_none(store):
    with pytest.raises(NotFoundError):
        store.get("VANCE", Role.DISPATCH)


def test_find_returns_none_when_there_is_none(store):
    assert store.find("VANCE", Role.DISPATCH) is None


def test_there_is_no_primary_to_start_with(store):
    store.put(a_contact())
    assert store.primary("VANCE") is None


def test_promoting_names_the_primary(store):
    store.put(a_contact())
    store.promote("VANCE", Role.DISPATCH)
    found = store.primary("VANCE")
    assert found is not None
    assert found.role is Role.DISPATCH


def test_promoting_a_second_demotes_the_first(store):
    store.put(a_contact(primary=True))
    store.put(a_contact(role=Role.ACCOUNTS, name="Dale Okonkwo", primary=True))
    found = store.primary("VANCE")
    assert found is not None
    assert found.role is Role.ACCOUNTS
    assert not store.get("VANCE", Role.DISPATCH).primary


def test_only_one_primary_survives(store):
    store.put(a_contact(primary=True))
    store.put(a_contact(role=Role.SAFETY, name="Ana Reyes", primary=True))
    both = store.for_carrier("VANCE")
    assert sum(1 for one in both if one.primary) == 1


def test_the_primary_comes_first_in_the_listing(store):
    store.put(a_contact())
    store.put(a_contact(role=Role.SAFETY, name="Ana Reyes", primary=True))
    assert store.for_carrier("VANCE")[0].role is Role.SAFETY


def test_promoting_a_contact_that_is_not_there_is_refused(store):
    with pytest.raises(NotFoundError):
        store.promote("VANCE", Role.SAFETY)


def test_another_carriers_primary_is_left_alone(store):
    store.put(a_contact(primary=True))
    store.put(a_contact(carrier="OTHER", name="Sam Ilg", primary=True))
    assert store.primary("VANCE") is not None
    assert store.primary("OTHER") is not None


def test_a_number_is_found_however_it_was_typed(store):
    store.put(a_contact())
    assert len(store.by_number("406-555-0142")) == 1


def test_a_number_at_two_carriers_finds_both(store):
    store.put(a_contact())
    store.put(a_contact(carrier="OTHER", name="Sam Ilg"))
    assert len(store.by_number("4065550142")) == 2


def test_a_number_nobody_has_finds_nothing(store):
    assert store.by_number("4065559999") == []


def test_removing_takes_it_off_the_file(store):
    store.put(a_contact())
    store.remove("VANCE", Role.DISPATCH)
    assert store.find("VANCE", Role.DISPATCH) is None


def test_removing_one_that_is_not_there_is_refused(store):
    with pytest.raises(NotFoundError):
        store.remove("VANCE", Role.DISPATCH)


def test_deleting_a_carrier_takes_its_contacts(store, office):
    store.put(a_contact())
    office.execute("DELETE FROM carrier WHERE code = 'VANCE'")
    assert store.count() == 0


def test_count_and_len_agree(store):
    store.put(a_contact())
    assert store.count() == len(store) == 1


def test_the_table_refuses_a_short_number(store, office):
    with pytest.raises(Exception, match="CHECK"):
        office.execute(
            "INSERT INTO contact (carrier_code, role, name, number)"
            " VALUES ('VANCE', 'dispatch', 'x', '5550142')"
        )


def test_the_office_hands_out_a_contact_store(office):
    from jeepdolly.store.office import Office

    assert isinstance(Office(office).contacts, ContactStore)
