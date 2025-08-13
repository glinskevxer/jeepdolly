import ast

from jeepdolly.tools.check_exports import LOOSE, SKIP, defined, exported, main, problems


def tree_of(text: str) -> ast.Module:
    """Parse a snippet the way the check does."""
    return ast.parse(text)


def test_the_package_has_no_problems():
    assert problems() == []


def test_main_passes():
    assert main() == 0


def test_exported_reads_a_list():
    assert exported(tree_of('__all__ = ["a", "b"]')) == ["a", "b"]


def test_exported_reads_a_tuple():
    assert exported(tree_of('__all__ = ("a",)')) == ["a"]


def test_exported_is_none_without_an_all():
    assert exported(tree_of("x = 1")) is None


def test_exported_of_a_computed_all_is_empty():
    assert exported(tree_of("__all__ = sorted(names)")) == []


def test_exported_skips_a_name_that_is_not_a_string():
    assert exported(tree_of("__all__ = [1, 'a']")) == ["a"]


def test_defined_finds_a_function():
    assert "go" in defined(tree_of("def go(): pass"))


def test_defined_finds_a_class():
    assert "Thing" in defined(tree_of("class Thing: pass"))


def test_defined_finds_a_constant():
    assert "LIMIT" in defined(tree_of("LIMIT = 5"))


def test_defined_finds_an_annotated_constant():
    assert "LIMIT" in defined(tree_of("LIMIT: int = 5"))


def test_defined_leaves_out_private_names():
    assert defined(tree_of("_hidden = 1")) == set()


def test_defined_leaves_out_a_nested_function():
    assert defined(tree_of("def outer():\n    def inner(): pass")) == {"outer"}


def test_the_skip_list_is_small():
    assert len(SKIP) <= 4


def test_every_skipped_module_is_ours():
    assert all(name.startswith("jeepdolly") for name in SKIP)


def test_a_dunder_counts_as_public():
    assert "__version__" in defined(tree_of('__version__ = "1.0"'))


def test_all_itself_does_not_count():
    assert "__all__" not in defined(tree_of('__all__ = ["a"]'))


def test_a_type_var_does_not_count():
    text = "from typing import TypeVar\nT = TypeVar('T')"
    assert "T" not in defined(tree_of(text))


def test_the_loose_list_is_only_the_command_modules():
    assert LOOSE == ("jeepdolly.cli.",)
