import ast

from jeepdolly.tools.check_dataclasses import MUTABLE, decorated, main, problems


def class_of(text: str) -> ast.ClassDef:
    """The first class in a snippet."""
    node = ast.parse(text).body[0]
    assert isinstance(node, ast.ClassDef)
    return node


def test_the_package_has_no_loose_dataclasses():
    assert problems() == []


def test_main_passes_over_the_package():
    assert main() == 0


def test_a_plain_class_is_not_a_dataclass():
    assert decorated(class_of("class Thing: pass")) is None


def test_a_bare_decorator_reads_as_no_arguments():
    assert decorated(class_of("@dataclass\nclass Thing: pass")) == {}


def test_a_called_decorator_reads_its_arguments():
    got = decorated(class_of("@dataclass(frozen=True, slots=True)\nclass Thing: pass"))
    assert got == {"frozen": True, "slots": True}


def test_a_dotted_decorator_is_read():
    got = decorated(class_of("@dataclasses.dataclass(frozen=True)\nclass Thing: pass"))
    assert got == {"frozen": True}


def test_another_decorator_is_ignored():
    assert decorated(class_of("@staticmethod\nclass Thing: pass")) is None


def test_a_computed_argument_is_left_out():
    got = decorated(class_of("@dataclass(frozen=WANT)\nclass Thing: pass"))
    assert got == {}


def test_the_exception_list_is_short():
    assert len(MUTABLE) <= 4


def test_every_exception_says_why():
    assert all(len(reason.split()) >= 10 for reason in MUTABLE.values())


def test_every_exception_names_a_class_in_this_package():
    assert all(name.startswith("jeepdolly.") for name in MUTABLE)


def test_the_desk_is_one_of_the_exceptions():
    assert "jeepdolly.permit.desk.Desk" in MUTABLE


def test_the_sheet_builder_is_one_of_the_exceptions():
    assert "jeepdolly.report.sheet.Sheet" in MUTABLE
