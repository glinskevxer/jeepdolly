import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.report.layout import LEFT, RIGHT, banner, pairs, rule, table


def test_rule_repeats_the_character():
    assert rule(5) == "-----"


def test_rule_takes_another_character():
    assert rule(3, "=") == "==="


def test_rule_of_zero_is_empty():
    assert rule(0) == ""


def test_rule_refuses_a_negative_width():
    with pytest.raises(BadValueError):
        rule(-1)


def test_rule_refuses_a_bool():
    with pytest.raises(BadValueError):
        rule(True)


def test_rule_refuses_two_characters():
    with pytest.raises(BadValueError):
        rule(3, "==")


def test_banner_puts_a_rule_under_the_title():
    lines = banner("permit", width=10)
    assert lines == ["permit", "----------"]


def test_banner_widens_for_a_long_title():
    lines = banner("a very long permit heading", width=4)
    assert len(lines[1]) == len(lines[0])


def test_banner_collapses_whitespace_in_the_title():
    assert banner("a   b", width=4)[0] == "a b"


def test_banner_refuses_an_empty_title():
    with pytest.raises(BadValueError):
        banner("  ")


def test_table_lines_the_columns_up():
    lines = table(["code", "miles"], [["SEG-AB", "12.00"], ["SEG-BD", "31.00"]])
    assert lines[0] == "code    miles"
    assert lines[2] == "SEG-AB  12.00"


def test_table_puts_a_rule_under_the_headings():
    lines = table(["code"], [["SEG-AB"]])
    assert lines[1] == "------"


def test_table_widens_a_column_for_a_long_cell():
    lines = table(["a"], [["a very long cell"]])
    assert len(lines[1]) == len("a very long cell")


def test_table_widens_a_column_for_a_long_heading():
    lines = table(["a long heading"], [["x"]])
    assert len(lines[1]) == len("a long heading")


def test_table_right_aligns_when_told_to():
    lines = table(["n"], [["1"], ["100"]], aligns=[RIGHT])
    assert lines[2] == "  1"


def test_table_left_aligns_by_default():
    lines = table(["n"], [["1"], ["100"]])
    assert lines[2].startswith("1")


def test_table_with_no_rows_is_the_heading_and_the_rule():
    assert len(table(["code"], [])) == 2


def test_table_refuses_no_columns():
    with pytest.raises(BadValueError):
        table([], [])


def test_table_refuses_a_short_row():
    with pytest.raises(BadValueError):
        table(["a", "b"], [["only one"]])


def test_table_refuses_the_wrong_number_of_aligns():
    with pytest.raises(BadValueError):
        table(["a", "b"], [], aligns=[LEFT])


def test_table_refuses_an_unknown_align():
    with pytest.raises(BadValueError):
        table(["a"], [], aligns=["middle"])


def test_table_takes_a_wider_gap():
    lines = table(["a", "b"], [["1", "2"]], gap=4)
    assert lines[2] == "1    2"


def test_table_does_not_leave_trailing_space():
    lines = table(["a", "bbbb"], [["1", "2"]])
    assert all(line == line.rstrip() for line in lines)


def test_pairs_line_the_labels_up():
    lines = pairs([("carrier", "VANCE"), ("fee", "$97.52")])
    assert lines == ["carrier  VANCE", "fee      $97.52"]


def test_pairs_of_nothing_is_empty():
    assert pairs([]) == []


def test_pairs_takes_a_wider_gap():
    assert pairs([("a", "b")], gap=4) == ["a    b"]


def test_pairs_do_not_leave_trailing_space():
    assert pairs([("a", "")]) == ["a"]
