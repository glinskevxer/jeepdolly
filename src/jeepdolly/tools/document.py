"""The half of a generated document that is the same for all three of them.

Three writers had the same forty lines: work out where the file goes, render it,
write it when told to, and otherwise compare it with what is committed and fail
with the same three messages. The only part that differed was ``render``.

The differences that had already crept in were the interesting bit. One writer
said "has never been written" and another said "is missing", one made the ``docs``
directory and two assumed it, and only one of them reported where it had written
to. None of that was a decision.

So the shape lives here and each writer is now a ``render`` and a name.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from jeepdolly.errors import BadValueError

__all__ = ["Document"]


@dataclass(frozen=True, slots=True)
class Document:
    """One generated file, its writer and its staleness check.

    ``path_of`` is a callable rather than a path so that a test can point one
    writer at a temporary file without the others noticing.
    """

    name: str
    render: Callable[[], str]
    path_of: Callable[[], Path]

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise BadValueError("name", self.name, "want some text")

    @property
    def path(self) -> Path:
        """Where the document is committed."""
        return self.path_of()

    @property
    def text(self) -> str:
        """What the document should say right now."""
        return self.render()

    @property
    def written(self) -> bool:
        """Has the document ever been written."""
        return self.path.exists()

    @property
    def current(self) -> bool:
        """Does the committed copy match what would be generated."""
        return self.written and self.path.read_text(encoding="utf-8") == self.text

    def write(self) -> Path:
        """Write the document out and hand back where it went."""
        path = self.path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.text, encoding="utf-8")
        return path

    def main(self, argv: list[str] | None = None) -> int:
        """Write the document, or check the committed one is current."""
        args = sys.argv[1:] if argv is None else argv
        if "--write" in args:
            print(f"{self.name}: wrote {self.write()}")
            return 0
        if not self.written:
            print(f"{self.name}: {self.path} has never been written")
            return 1
        if not self.current:
            print(f"{self.name}: {self.path} is out of date, run with --write")
            return 1
        return 0
