"""Every module and every public definition carries a docstring.

This is not a style preference. The office generates its command reference and
its glossary from these strings, so an undocumented public function is a hole in
a document somebody reads. A one line docstring is enough and most of them are.

Private names are skipped. So are overloads and the ``__post_init__`` methods,
which are validation and say nothing a reader of the class needs.
"""

from __future__ import annotations

import ast
import sys

from jeepdolly.tools.walk import module_of, parse, source_files

__all__ = ["EXEMPT", "MIN_WORDS", "main", "problems"]

#: A docstring shorter than this is not a sentence.
MIN_WORDS = 3

#: Methods whose body is the documentation.
EXEMPT = frozenset(
    {
        "__post_init__",
        "__str__",
        "__repr__",
        "__len__",
        "__iter__",
        "__eq__",
        "__hash__",
        "__contains__",
    }
)


def _walk(node: ast.AST, path: str) -> list[tuple[str, ast.AST]]:
    """Every public definition under a node, with a readable name."""
    out: list[tuple[str, ast.AST]] = []
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            if child.name.startswith("_") and child.name not in {"__init__"}:
                continue
            if child.name in EXEMPT:
                continue
            here = f"{path}.{child.name}"
            out.append((here, child))
            if isinstance(child, ast.ClassDef):
                out.extend(_walk(child, here))
    return out


def problems() -> list[str]:
    """Every module or definition with a missing or thin docstring."""
    found: list[str] = []
    for source in source_files():
        module = module_of(source)
        tree = parse(source)
        if not ast.get_docstring(tree):
            found.append(f"{module}: the module has no docstring")
        for name, node in _walk(tree, module):
            assert isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
            text = ast.get_docstring(node)
            if not text:
                found.append(f"{name}: no docstring")
            elif len(text.split()) < MIN_WORDS:
                found.append(f"{name}: docstring is under {MIN_WORDS} words")
    return found


def main() -> int:
    """Report everything undocumented and fail if there is anything."""
    found = problems()
    for line in found:
        print(f"check_docstrings: {line}")
    if found:
        print(f"check_docstrings: {len(found)} undocumented")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
