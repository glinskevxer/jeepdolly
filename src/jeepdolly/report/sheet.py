"""Building a printed sheet a section at a time.

Six reports were the same three moves in the same order: a heading, some tables
with headings above them, and a block of label and value pairs at the bottom. Each
one built a ``lines`` list, appended a blank string between sections when it
remembered to, and returned it.

The blanks are the tell. Four of the six put a blank line before every section
and two put one after the heading as well, so the reports did not line up on the
page and nobody could see why. A section knows it wants a blank line before it,
and now only one piece of code knows that.

The builder is deliberately not clever. It appends to a list and hands the list
back. Anything that wanted a layout engine would be a different problem.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from jeepdolly.errors import BadValueError
from jeepdolly.report.layout import banner, pairs, table

__all__ = ["Sheet"]


@dataclass(slots=True)
class Sheet:
    """A printed sheet, built a section at a time."""

    lines: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.lines, list):
            raise BadValueError("lines", self.lines, "want a list of lines")

    @property
    def empty(self) -> bool:
        """Has anything been put on the sheet yet."""
        return not self.lines

    def _gap(self) -> None:
        """A blank line before a section, unless the sheet is still empty."""
        if self.lines:
            self.lines.append("")

    def title(self, text: str, width: int = 64) -> Sheet:
        """The sheet's own heading. Takes no blank line before it."""
        self.lines.extend(banner(text, width))
        return self

    def section(self, text: str) -> Sheet:
        """A heading for the next block, with a blank line before it."""
        self._gap()
        self.lines.extend(banner(text))
        return self

    def rows(
        self,
        headings: Sequence[str],
        body: Iterable[Sequence[str]],
        aligns: Sequence[str] | None = None,
    ) -> Sheet:
        """A table under whatever heading was last written."""
        self.lines.extend(table(headings, body, aligns))
        return self

    def summary(self, items: Iterable[tuple[str, str]]) -> Sheet:
        """A block of label and value pairs, with a blank line before it."""
        held = list(items)
        if not held:
            return self
        self._gap()
        self.lines.extend(pairs(held))
        return self

    def note(self, text: str) -> Sheet:
        """One plain line."""
        self.lines.append(text)
        return self

    def notes(self, texts: Iterable[str]) -> Sheet:
        """A run of plain lines."""
        self.lines.extend(texts)
        return self

    def done(self) -> list[str]:
        """The finished sheet."""
        return self.lines
