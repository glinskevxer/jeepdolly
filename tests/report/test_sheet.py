import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.report.layout import LEFT, RIGHT
from jeepdolly.report.sheet import Sheet


def test_a_new_sheet_is_empty():
    assert Sheet().empty


def test_a_title_takes_no_blank_line_before_it():
    made = Sheet().title("revenue return").done()
    assert made[0] == "revenue return"


def test_a_title_is_underlined():
    made = Sheet().title("revenue return", width=20).done()
    assert made[1] == "-" * 20


def test_a_section_takes_a_blank_line_before_it():
    made = Sheet().title("a").section("b").done()
    assert "" in made
    assert made[made.index("") + 1] == "b"


def test_the_first_section_on_an_empty_sheet_takes_no_blank():
    made = Sheet().section("b").done()
    assert made[0] == "b"


def test_rows_go_under_the_last_heading():
    made = Sheet().section("stretches").rows(["code"], [["SEG-AB"]]).done()
    assert made[-1] == "SEG-AB"


def test_rows_take_an_alignment():
    made = Sheet().rows(["n"], [["1"], ["100"]], aligns=[RIGHT]).done()
    assert made[-2] == "  1"


def test_rows_refuse_a_short_row():
    with pytest.raises(BadValueError):
        Sheet().rows(["a", "b"], [["only one"]])


def test_a_summary_takes_a_blank_line_before_it():
    made = Sheet().note("x").summary([("a", "1")]).done()
    assert made == ["x", "", "a  1"]


def test_an_empty_summary_adds_nothing():
    made = Sheet().note("x").summary([]).done()
    assert made == ["x"]


def test_a_note_is_one_plain_line():
    assert Sheet().note("nothing to report").done() == ["nothing to report"]


def test_notes_are_a_run_of_plain_lines():
    assert Sheet().notes(["a", "b"]).done() == ["a", "b"]


def test_the_builder_chains_every_section():
    made = (
        Sheet()
        .title("revenue return")
        .section("by month")
        .rows(["month", "take"], [["2025-06", "$97.52"]], aligns=[LEFT, RIGHT])
        .summary([("permits", "1")])
        .done()
    )
    assert made[0] == "revenue return"
    assert "by month" in made
    assert made[-1] == "permits  1"


def test_two_sections_each_take_one_blank():
    made = Sheet().section("a").section("b").done()
    assert made.count("") == 1


def test_a_sheet_refuses_something_that_is_not_a_list():
    with pytest.raises(BadValueError):
        Sheet(lines="not a list")  # type: ignore[arg-type]


def test_a_sheet_hands_back_its_own_lines():
    made = Sheet()
    assert made.done() is made.lines


def test_a_sheet_stops_being_empty_once_written_to():
    made = Sheet().note("x")
    assert not made.empty
