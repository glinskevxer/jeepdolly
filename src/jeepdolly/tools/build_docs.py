"""Generate the command reference from the command tree itself.

A reference written by hand goes stale the first time somebody adds an option,
and it goes stale silently. This walks the click group, reads every command, its
help text and its options, and writes the document. The build then regenerates it
and fails if what comes out differs from what is committed.

That is the important half. Generating a document is easy; the value is in the
check that the committed copy matches, because that is what makes a forgotten
regeneration a red build instead of a wrong document.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from jeepdolly import __version__
from jeepdolly.cli.main import main as cli
from jeepdolly.tools.document import Document
from jeepdolly.tools.walk import repo_root

__all__ = ["DOCUMENT", "DOC_NAME", "doc_path", "main", "render", "write"]

#: Where the reference is committed.
DOC_NAME = "commands.md"


def doc_path() -> Path:
    """Where the command reference lives."""
    return repo_root() / "docs" / DOC_NAME


def _option_rows(command: click.Command) -> list[tuple[str, str, str]]:
    """Every option of one command as name, kind and help."""
    rows: list[tuple[str, str, str]] = []
    for parameter in command.params:
        if isinstance(parameter, click.Argument):
            rows.append((parameter.name or "", "argument", ""))
            continue
        if not isinstance(parameter, click.Option):
            continue
        names = ", ".join(parameter.opts)
        kind = "flag" if parameter.is_flag else "option"
        if parameter.required:
            kind = f"required {kind}"
        rows.append((names, kind, parameter.help or ""))
    return rows


def _walk(group: click.Group, prefix: str) -> list[str]:
    """The lines for one group and everything under it."""
    lines: list[str] = []
    for name in sorted(group.commands):
        command = group.commands[name]
        path = f"{prefix} {name}".strip()
        lines.append("")
        lines.append(f"### `{path}`")
        lines.append("")
        lines.append((command.help or "").strip().splitlines()[0] if command.help else "")
        rows = _option_rows(command)
        if rows:
            lines.append("")
            lines.append("| name | kind | what it is for |")
            lines.append("| --- | --- | --- |")
            for option, kind, text in rows:
                lines.append(f"| `{option}` | {kind} | {text} |")
        if isinstance(command, click.Group):
            lines.extend(_walk(command, path))
    return lines


def render() -> str:
    """The whole reference as text."""
    lines = [
        "# jeepdolly commands",
        "",
        "Generated from the command tree by `tools/build_docs.py`.",
        "Run that with `--write` after changing a command, or the build will say so.",
        "",
        f"Package version {__version__}.",
        "",
        "## commands",
    ]
    assert isinstance(cli, click.Group)
    lines.extend(_walk(cli, "jeepdolly"))
    return "\n".join(lines).rstrip() + "\n"


DOCUMENT = Document(name="build_docs", render=render, path_of=lambda: doc_path())


def write() -> Path:
    """Write the document out and hand back where it went."""
    return DOCUMENT.write()


def main(argv: list[str] | None = None) -> int:
    """Write the document, or check the committed one is current."""
    return DOCUMENT.main(argv)


if __name__ == "__main__":
    sys.exit(main())
