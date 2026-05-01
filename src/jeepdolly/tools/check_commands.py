"""Every command on the command line is exercised by at least one test.

The command line is the only front end this office has, and it is the layer where
a mistake is invisible to the rest of the suite: every module underneath can be
green while a command passes its arguments in the wrong order.

So this walks the click tree, works out how each command is spelled at the
prompt, and looks for that spelling in the command line tests. It is a crude
check and it is deliberately crude: it proves a command is *reached*, not that it
is tested well. What it catches is the command nobody thought about, which is the
one that breaks.

It looks for the argument sequence rather than the command name, because a bare
name turns up in half the suite for other reasons and would make this pass on
almost anything.

The same check runs against the walk script, which drives an *installed* copy of
the package from a shell. That catches a different failure: a command that works
when click is invoked in process and does not when it is spelled at a prompt,
which is where quoting, exit statuses and the console script entry point live.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Sequence

import click

from jeepdolly.cli.main import main as cli
from jeepdolly.tools.walk import repo_root

__all__ = [
    "SUITE",
    "WALK",
    "invocation",
    "main",
    "paths_of",
    "problems",
    "spoken",
    "untested",
    "unwalked",
]

#: Where the command line tests live, relative to the repository root.
SUITE = "tests/cli"

#: The shell script that drives an installed copy, relative to the same root.
WALK = "scripts/walk.sh"


def paths_of(group: click.Group, prefix: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
    """Every command in a group, as the words a clerk would type."""
    found: list[tuple[str, ...]] = []
    for name in sorted(group.commands):
        command = group.commands[name]
        here = (*prefix, name)
        if isinstance(command, click.Group):
            found.extend(paths_of(command, here))
        else:
            found.append(here)
    return found


def invocation(path: tuple[str, ...]) -> re.Pattern[str]:
    """A pattern matching the way a test spells one command."""
    body = r",\s*".join(re.escape(f'"{word}"') for word in path)
    return re.compile(body)


def spoken(path: tuple[str, ...]) -> re.Pattern[str]:
    """A pattern matching the way the walk script spells one command.

    ``run permit issue`` at the start of a line, allowing for the continuation
    backslashes the script uses to keep its lines readable.
    """
    body = r"[ \t]+".join(re.escape(word) for word in path)
    return re.compile(rf"^\s*run\s+{body}(\s|$)", re.MULTILINE)


def untested(text: str, paths: Sequence[tuple[str, ...]]) -> list[tuple[str, ...]]:
    """Every command whose spelling does not appear in the given text."""
    return [path for path in paths if invocation(path).search(text) is None]


def unwalked(text: str, paths: Sequence[tuple[str, ...]]) -> list[tuple[str, ...]]:
    """Every command the walk script never runs."""
    return [path for path in paths if spoken(path).search(text) is None]


def problems() -> list[str]:
    """Every command the suite or the walk script never reaches."""
    assert isinstance(cli, click.Group)
    found: list[str] = []
    every = paths_of(cli)
    suite = repo_root() / SUITE
    if not suite.is_dir():
        found.append(f"{SUITE} is not there, so nothing exercises the command line")
    else:
        text = "\n".join(
            path.read_text(encoding="utf-8") for path in sorted(suite.rglob("*.py"))
        )
        found.extend(
            "jeepdolly " + " ".join(path) + ": no test invokes it"
            for path in untested(text, every)
        )
    walk = repo_root() / WALK
    if not walk.exists():
        found.append(f"{WALK} is not there, so nothing drives an installed copy")
    else:
        text = walk.read_text(encoding="utf-8")
        found.extend(
            "jeepdolly " + " ".join(path) + f": {WALK} never runs it"
            for path in unwalked(text, every)
        )
    return found


def main() -> int:
    """Report every command nothing exercises and fail if there is one."""
    found = problems()
    for line in found:
        print(f"check_commands: {line}")
    if found:
        print(f"check_commands: {len(found)} commands are never invoked by a test")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
