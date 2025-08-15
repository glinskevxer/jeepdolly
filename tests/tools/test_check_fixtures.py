import ast

from jeepdolly.tools.check_fixtures import OPENERS, is_fixture, main, opens_something, problems


def function_of(text: str) -> ast.FunctionDef:
    """The first function in a snippet."""
    node = ast.parse(text).body[0]
    assert isinstance(node, ast.FunctionDef)
    return node


def test_the_suite_has_no_problems():
    assert problems() == []


def test_main_passes_over_the_suite():
    assert main() == 0


def test_a_plain_decorator_is_read():
    assert is_fixture(function_of("@pytest.fixture\ndef go(): pass"))


def test_a_called_decorator_is_read():
    assert is_fixture(function_of("@pytest.fixture()\ndef go(): pass"))


def test_a_bare_name_decorator_is_read():
    assert is_fixture(function_of("@fixture\ndef go(): pass"))


def test_an_undecorated_function_is_not_a_fixture():
    assert not is_fixture(function_of("def go(): pass"))


def test_another_decorator_is_not_a_fixture():
    assert not is_fixture(function_of("@staticmethod\ndef go(): pass"))


def test_a_body_that_opens_is_found():
    assert opens_something(function_of("def go():\n    return opened(path)"))


def test_a_dotted_open_is_found():
    assert opens_something(function_of("def go():\n    return store.connect(path)"))


def test_a_body_that_opens_nothing_is_not_found():
    assert not opens_something(function_of("def go():\n    return 1"))


def test_every_opener_is_a_bare_name():
    assert all("." not in name for name in OPENERS)


def test_the_opener_list_covers_the_office_helpers():
    assert "opened_new_office" in OPENERS
    assert "opened_office" in OPENERS
