"""Laying text out in columns without pulling anything in.

The office prints on a line printer and reads on a terminal, and both want the
same thing: fixed width columns that do not move when a number gets longer. This
is the whole of the presentation layer.

Columns are measured over the rows they are given, so a table is as narrow as it
can be. A cell wider than its heading widens the column; a heading wider than
every cell does the same. Nothing truncates, because a truncated permit number
is worse than a ragged edge.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from jeepdolly.errors import BadValueError

__all__ = ["LEFT", "RIGHT", "banner", "pairs", "rule", "table"]

LEFT = "left"
RIGHT = "right"


def _pad(text: str, width: int, align: str) -> str:
    if align == RIGHT:
        return text.rjust(width)
    return text.ljust(width)


def rule(width: int, character: str = "-") -> str:
    """A horizontal rule."""
    if isinstance(width, bool) or not isinstance(width, int) or width < 0:
        raise BadValueError("width", width, "want a whole number")
    if len(character) != 1:
        raise BadValueError("character", character, "want exactly one character")
    return character * width


def banner(title: str, width: int = 64) -> list[str]:
    """A heading with a rule under it."""
    if not isinstance(title, str) or not title.strip():
        raise BadValueError("title", title, "want some text")
    tidy = " ".join(title.split())
    return [tidy, rule(max(width, len(tidy)))]


def table(
    headings: Sequence[str],
    body: Iterable[Sequence[str]],
    aligns: Sequence[str] | None = None,
    gap: int = 2,
) -> list[str]:
    """Lay rows out under headings, one line per row.

    Every row has to have as many cells as there are headings. A short row is a
    bug in the caller and it is caught here rather than printed as a hole.
    """
    rows = [list(row) for row in body]
    columns = len(headings)
    if columns == 0:
        raise BadValueError("headings", headings, "want at least one column")
    for row in rows:
        if len(row) != columns:
            raise BadValueError("row", row, f"want {columns} cells")
    if aligns is None:
        aligns = [LEFT] * columns
    if len(aligns) != columns:
        raise BadValueError("aligns", aligns, f"want {columns} of them")
    for align in aligns:
        if align not in (LEFT, RIGHT):
            raise BadValueError("align", align, "want left or right")
    widths = [
        max([len(str(headings[i]))] + [len(str(row[i])) for row in rows])
        for i in range(columns)
    ]
    spacer = " " * gap
    lines = [
        spacer.join(
            _pad(str(headings[i]), widths[i], aligns[i]) for i in range(columns)
        ).rstrip()
    ]
    lines.append(spacer.join(rule(widths[i]) for i in range(columns)))
    for row in rows:
        lines.append(
            spacer.join(
                _pad(str(row[i]), widths[i], aligns[i]) for i in range(columns)
            ).rstrip()
        )
    return lines


def pairs(items: Iterable[tuple[str, str]], gap: int = 2) -> list[str]:
    """Lay label and value pairs out with the labels lined up."""
    held = list(items)
    if not held:
        return []
    width = max(len(label) for label, _ in held)
    spacer = " " * gap
    return [f"{label.ljust(width)}{spacer}{value}".rstrip() for label, value in held]
