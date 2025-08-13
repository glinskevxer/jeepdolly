"""``__all__`` has to match what the module actually defines.

Two failures, in opposite directions, and both have happened here.

A name listed in ``__all__`` that is no longer defined is a broken star import
and, worse, a broken documentation build: the generated command reference reads
``__all__`` and prints a heading for something that is not there.

A public name defined and *not* listed is a name nobody knows is public. It gets
imported by one caller, then another, and by the time somebody wants to change
it there are six.

Modules with no ``__all__`` at all are skipped rather than failed. A handful are
genuinely private to their package.
"""

from __future__ import annotations

import ast
import sys

from jeepdolly.tools.walk import module_of, parse, source_files

__all__ = ["LOOSE", "SKIP", "defined", "exported", "main", "problems"]

#: Modules that are allowed to have no ``__all__``.
SKIP = frozenset({"jeepdolly.tools", "jeepdolly.cli"})

#: Modules where a public name may sit outside ``__all__``. The command modules
#: are the whole list: a click command is registered on its group by the
#: decorator and is never imported by name, so listing every one of them would
#: be a second copy of the command table that nothing reads.
LOOSE = ("jeepdolly.cli.",)


def exported(tree: ast.Module) -> list[str] | None:
    """The names in ``__all__``, or ``None`` when there is no ``__all__``."""
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "__all__":
                if not isinstance(node.value, ast.List | ast.Tuple):
                    return []
                out: list[str] = []
                for item in node.value.elts:
                    if isinstance(item, ast.Constant) and isinstance(item.value, str):
                        out.append(item.value)
                return out
    return None


def defined(tree: ast.Module) -> set[str]:
    """Every public name the module binds at the top level."""
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return {name for name in names if _public(name)} - _type_vars(tree)


def _public(name: str) -> bool:
    """Is this a name a caller could reasonably import.

    A dunder counts. ``__version__`` is as public as anything in the package.
    """
    if name.startswith("__") and name.endswith("__"):
        return name != "__all__"
    return not name.startswith("_")


def _type_vars(tree: ast.Module) -> set[str]:
    """Names bound to a ``TypeVar``, which are declarations and not exports."""
    found: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        called = node.value.func
        name = called.id if isinstance(called, ast.Name) else getattr(called, "attr", "")
        if name == "TypeVar":
            for target in node.targets:
                if isinstance(target, ast.Name):
                    found.add(target.id)
    return found


def problems() -> list[str]:
    """Every mismatch between ``__all__`` and the module, one line each."""
    found: list[str] = []
    for path in source_files():
        module = module_of(path)
        tree = parse(path)
        listed = exported(tree)
        if listed is None:
            if module not in SKIP and defined(tree):
                found.append(f"{module}: defines public names and has no __all__")
            continue
        here = defined(tree)
        for name in listed:
            if name not in here:
                found.append(f"{module}: __all__ names {name}, which is not defined here")
        if not module.startswith(LOOSE):
            for name in sorted(here - set(listed)):
                found.append(f"{module}: {name} is public and not in __all__")
        if len(set(listed)) != len(listed):
            found.append(f"{module}: __all__ repeats a name")
    return found


def main() -> int:
    """Report every mismatch and fail if there is one."""
    found = problems()
    for line in found:
        print(f"check_exports: {line}")
    if found:
        print(f"check_exports: {len(found)} problems")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
