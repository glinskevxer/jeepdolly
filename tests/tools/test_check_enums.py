from jeepdolly.enforce.ticket import Discrepancy
from jeepdolly.enforce.violation import CHARGEABLE
from jeepdolly.permit.revoke import Cause
from jeepdolly.tools.check_enums import (
    OVERLAP,
    constraints_in,
    drift,
    enums_in_package,
    main,
    problems,
    schema_text,
)

SCHEMA = "CREATE TABLE t (a TEXT CHECK (a IN ('one', 'two')), b TEXT)"


def test_the_package_schema_matches_its_enums():
    assert problems() == []


def test_main_passes_over_the_package():
    assert main() == 0


def test_the_schema_holds_the_tables_the_migrations_make():
    text = schema_text()
    assert "CREATE TABLE carrier" in text
    assert "CREATE TABLE revocation" in text


def test_a_constrained_column_is_found():
    assert constraints_in(SCHEMA) == [("a", frozenset({"one", "two"}))]


def test_a_column_with_no_constraint_is_not_found():
    assert constraints_in("CREATE TABLE t (b TEXT)") == []


def test_an_empty_literal_list_is_not_found():
    assert constraints_in("CREATE TABLE t (a TEXT CHECK (a IN ()))") == []


def test_a_lower_case_check_is_still_found():
    assert constraints_in("create table t (a text check (a in ('one')))") == [
        ("a", frozenset({"one"}))
    ]


def test_two_constraints_are_both_found():
    text = "CREATE TABLE t (a TEXT CHECK (a IN ('one')), b TEXT CHECK (b IN ('two')))"
    assert len(constraints_in(text)) == 2


def test_every_enum_the_package_defines_is_collected():
    held = enums_in_package()
    assert held["jeepdolly.permit.revoke.Cause"] == frozenset(str(one) for one in Cause)


def test_a_named_subset_is_collected_too():
    held = enums_in_package()
    assert held["jeepdolly.enforce.violation.CHARGEABLE"] == frozenset(
        str(one) for one in CHARGEABLE
    )


def test_the_whole_discrepancy_enum_is_collected():
    held = enums_in_package()
    assert held["jeepdolly.enforce.ticket.Discrepancy"] == frozenset(
        str(one) for one in Discrepancy
    )


def test_a_lower_case_module_constant_is_not_collected():
    held = enums_in_package()
    assert not any(name.rsplit(".", 1)[1].islower() for name in held)


def test_the_violation_column_matches_the_subset_and_not_the_enum():
    found = [values for column, values in constraints_in(schema_text()) if column == "kind"]
    assert frozenset(str(one) for one in CHARGEABLE) in found


def test_two_shared_values_are_enough_to_be_a_copy():
    assert OVERLAP == 2


CANDIDATES = {"a.Colour": frozenset({"red", "green", "blue"})}


def test_a_constraint_matching_a_named_set_exactly_is_fine():
    assert drift([("colour", frozenset({"red", "green", "blue"}))], CANDIDATES) == []


def test_a_constraint_missing_a_member_is_reported():
    found = drift([("colour", frozenset({"red", "green"}))], CANDIDATES)
    assert found == ["colour: a.Colour has ['blue'] and the schema does not"]


def test_a_constraint_with_a_member_the_enum_lost_is_reported():
    found = drift([("colour", frozenset({"red", "green", "blue", "puce"}))], CANDIDATES)
    assert found == ["colour: the schema has ['puce'] and a.Colour does not"]


def test_a_constraint_that_drifted_both_ways_is_reported_twice():
    found = drift([("colour", frozenset({"red", "green", "puce"}))], CANDIDATES)
    assert len(found) == 2


def test_a_constraint_sharing_too_little_is_left_alone():
    assert drift([("mood", frozenset({"red", "sad"}))], CANDIDATES) == []


def test_a_constraint_matching_nothing_at_all_is_left_alone():
    assert drift([("mood", frozenset({"glad", "sad"}))], CANDIDATES) == []


def test_the_closest_candidate_is_the_one_reported():
    candidates = {
        "a.Colour": frozenset({"red", "green", "blue"}),
        "a.Warm": frozenset({"red", "orange"}),
    }
    found = drift([("colour", frozenset({"red", "green"}))], candidates)
    assert "a.Colour" in found[0]


def test_the_findings_come_back_sorted():
    constraints = [
        ("zebra", frozenset({"red", "green"})),
        ("apple", frozenset({"red", "green"})),
    ]
    found = drift(constraints, CANDIDATES)
    assert found == sorted(found)


def test_an_empty_schema_has_nothing_to_report():
    assert drift([], CANDIDATES) == []


def test_no_candidates_at_all_means_nothing_to_compare_against():
    assert drift([("colour", frozenset({"red"}))], {}) == []
