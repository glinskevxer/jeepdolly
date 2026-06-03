"""Every command and every option says what it is for, in a sentence.

``jeepdolly --help`` is the only documentation most people will read, and it is
generated from these strings. A command whose help is ``Do the thing`` and an
option with no help at all are both worse than useless there: they take up a line
and say nothing.

Four rules, and all of them are about the printed page rather than about style.
A command's first help line is a sentence, so it starts on a capital and ends on
a full stop. An option's help is a sentence for the same reason. Neither runs
past the width the terminal will wrap at. And every option has one.

Arguments are exempt. Click does not print help for them and there is nowhere to
put it.
"""

from __future__ import annotations

import sys

import click

from jeepdolly.cli.main import main as cli

__all__ = ["MAX_LINE", "faults", "main", "problems", "walk_commands"]

#: A help line longer than this wraps badly in a narrow terminal.
MAX_LINE = 80


def walk_commands(
    group: click.Group, prefix: tuple[str, ...] = ()
) -> list[tuple[str, click.Command]]:
    """Every command under a group, with the words a clerk would type."""
    found: list[tuple[str, click.Command]] = []
    for name in sorted(group.commands):
        command = group.commands[name]
        here = " ".join((*prefix, name))
        found.append((here, command))
        if isinstance(command, click.Group):
            found.extend(walk_commands(command, (*prefix, name)))
    return found


def _sentence(text: str) -> str | None:
    """Why this is not a printable sentence, or ``None`` if it is."""
    if not text.strip():
        return "says nothing"
    first = text.strip().splitlines()[0].strip()
    if not first[:1].isupper():
        return f"starts lower case: {first!r}"
    if not first.endswith("."):
        return f"does not end in a full stop: {first!r}"
    if len(first) > MAX_LINE:
        return f"is {len(first)} characters, over {MAX_LINE}"
    return None


def faults(name: str, command: click.Command) -> list[str]:
    """Everything wrong with one command's help, one line each."""
    found: list[str] = []
    trouble = _sentence(command.help or "")
    if trouble is not None:
        found.append(f"jeepdolly {name}: the help {trouble}")
    for parameter in command.params:
        if not isinstance(parameter, click.Option) or parameter.name == "help":
            continue
        if parameter.hidden:
            continue
        spelled = ", ".join(parameter.opts)
        trouble = _sentence(parameter.help or "")
        if trouble is not None:
            found.append(f"jeepdolly {name} {spelled}: the help {trouble}")
    return found


def problems() -> list[str]:
    """Every command or option whose help is not a printable sentence."""
    assert isinstance(cli, click.Group)
    found: list[str] = []
    found.extend(faults("", cli))
    for name, command in walk_commands(cli):
        found.extend(faults(name, command))
    return found


def main() -> int:
    """Report every help string that would read badly and fail if there is one."""
    found = problems()
    for line in found:
        print(f"check_help: {line}")
    if found:
        print(f"check_help: {len(found)} help strings do not read")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
