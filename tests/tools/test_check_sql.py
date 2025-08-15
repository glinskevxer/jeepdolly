import ast

from jeepdolly.tools.check_sql import ALLOWED, interpolations, main, problems


def tree_of(text: str) -> ast.Module:
    """Parse a snippet the way the check does."""
    return ast.parse(text)


def test_the_package_has_no_problems():
    assert problems() == []


def test_main_passes_over_the_package():
    assert main() == 0


def test_a_plain_query_has_no_interpolations():
    assert interpolations(tree_of('x = "SELECT * FROM thing"')) == []


def test_an_interpolated_query_is_found():
    got = interpolations(tree_of('x = f"SELECT * FROM {table}"'))
    assert [name for _, name in got] == ["table"]


def test_an_interpolated_string_that_is_not_a_query_is_ignored():
    assert interpolations(tree_of('x = f"hello {name}"')) == []


def test_the_check_reads_lower_case_sql():
    got = interpolations(tree_of('x = f"select * from {table}"'))
    assert got


def test_an_insert_is_read():
    got = interpolations(tree_of('x = f"INSERT INTO {table} VALUES (?)"'))
    assert got


def test_an_update_is_read():
    got = interpolations(tree_of('x = f"UPDATE {table} SET a = ?"'))
    assert got


def test_a_delete_is_read():
    got = interpolations(tree_of('x = f"DELETE FROM {table}"'))
    assert got


def test_the_line_number_comes_back():
    got = interpolations(tree_of('\n\nx = f"SELECT * FROM {table}"'))
    assert got[0][0] == 3


def test_an_attribute_reads_as_its_dotted_name():
    got = interpolations(tree_of('x = f"SELECT * FROM {self.table}"'))
    assert [name for _, name in got] == ["self.table"]


def test_the_allowed_list_holds_only_identifiers():
    assert "carrier" not in ALLOWED
    assert "self.table" in ALLOWED


def test_the_allowed_list_is_short():
    assert len(ALLOWED) <= 12
