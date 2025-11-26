import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.ids.reference import PERMIT, REVIEW, RIG, STRUCTURE
from jeepdolly.store.counter import highest, next_serial


def test_the_first_reference_is_one(office):
    assert next_serial(office, RIG, "rig", "reference") == "R-00001"


def test_the_highest_of_an_empty_table_is_none(office):
    assert highest(office, "rig", "reference") is None


def test_a_table_that_is_not_there_is_refused(office):
    with pytest.raises(BadValueError):
        highest(office, "nothing", "reference")


def test_the_counter_climbs_from_what_is_there(office):
    office.execute("INSERT INTO carrier VALUES ('A', 'A Haul', 1, 'MT', 1)")
    office.execute("INSERT INTO rig VALUES ('R-00007', 'A', '3S2', '2025-01-01')")
    assert next_serial(office, RIG, "rig", "reference") == "R-00008"


def test_the_counter_reads_the_text_maximum(office):
    office.execute("INSERT INTO carrier VALUES ('A', 'A Haul', 1, 'MT', 1)")
    for number in ("R-00002", "R-00010", "R-00003"):
        office.execute("INSERT INTO rig VALUES (?, 'A', '3S2', '2025-01-01')", (number,))
    assert next_serial(office, RIG, "rig", "reference") == "R-00011"


def test_the_padding_is_what_makes_the_text_order_numeric():
    assert RIG.format(2) < RIG.format(10)
    assert PERMIT.format(2) < PERMIT.format(10)
    assert STRUCTURE.format(2) < STRUCTURE.format(10)
    assert REVIEW.format(2) < REVIEW.format(10)


def test_the_counter_refuses_a_table_that_is_not_there(office):
    with pytest.raises(BadValueError):
        next_serial(office, RIG, "nothing", "reference")


def test_every_store_hands_out_its_own_first_reference(office):
    from jeepdolly.store.office import Office

    made = Office(office)
    assert made.rigs.next_reference() == "R-00001"
    assert made.permits.next_number() == "P-000001"
    assert made.reviews.next_reference() == "E-00001"
    assert made.roadway.next_structure() == "STR-00001"


def test_two_stores_do_not_share_a_counter(office):
    from jeepdolly.store.office import Office

    made = Office(office)
    office.execute("INSERT INTO carrier VALUES ('A', 'A Haul', 1, 'MT', 1)")
    office.execute("INSERT INTO rig VALUES ('R-00007', 'A', '3S2', '2025-01-01')")
    assert made.rigs.next_reference() == "R-00008"
    assert made.permits.next_number() == "P-000001"
