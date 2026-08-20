from jeepdolly.enforce.ticket import Discrepancy
from jeepdolly.enforce.violation import CHARGEABLE
from jeepdolly.permit.revoke import Cause
from jeepdolly.tools.check_enums import (
    OVERLAP,
    constraints_in,
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
