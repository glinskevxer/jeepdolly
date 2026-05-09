"""Every command the README shows is a command that exists.

The README is the first thing anybody runs and the last thing anybody updates. A
command renamed in a refactor leaves an example that fails on the reader's first
try, which is a worse first impression than having no example at all.

So the indented block in the README is read as shell, every ``jeepdolly ...``
line is parsed as far as its first option, and the words are looked up in the
command tree. Options are not checked. They change more often than names do and
checking them would make this fire on every sensible edit.
"""

from __future__ import annotations

import re
import sys

import click

from jeepdolly.cli.main import main as cli
from jeepdolly.tools.walk import repo_root

__all__ = ["README", "main", "problems", "resolves", "shown"]

#: The document that shows commands.
README = "README.md"

_LINE = re.compile(r"^\s{2,}(?:\\?\s*)?jeepdolly\s+(.*)$")


def shown(text: str) -> list[tuple[str, ...]]:
    """Every command spelled out in the README, longest match first.

    A line is taken up to its first option, so ``permit apply --carrier VANCE``
    reads as ``permit apply``. What is left may still hold a positional argument,
    which ``resolves`` walks past rather than this trying to guess at.
    """
    found: list[tuple[str, ...]] = []
    for line in text.splitlines():
        hit = _LINE.match(line)
        if hit is None:
            continue
        words: list[str] = []
        for word in hit.group(1).split():
            if word.startswith("-") or word == "\\":
                break
            words.append(word)
        if words and tuple(words) not in found:
            found.append(tuple(words))
    return found


def resolves(path: tuple[str, ...]) -> bool:
    """Do the leading words of this line name a command in the tree.

    Words are consumed while they keep naming subcommands, and whatever is left
    is taken to be arguments. ``permit issue 1`` resolves; ``permit issued 1``
    does not, because ``issued`` stops the walk on a group.
    """
    node: click.Command = cli
    used = 0
    for word in path:
        if not isinstance(node, click.Group) or word not in node.commands:
            break
        node = node.commands[word]
        used += 1
    return used > 0 and not isinstance(node, click.Group)


def problems() -> list[str]:
    """Every command the README shows that is not there."""
    path = repo_root() / README
    if not path.exists():
        return [f"{README} is not there"]
    text = path.read_text(encoding="utf-8")
    return [
        f"{README} shows `jeepdolly {' '.join(one)}`, which is not a command"
        for one in shown(text)
        if not resolves(one)
    ]


def main() -> int:
    """Report every example that would fail and exit non zero if there is one."""
    found = problems()
    for line in found:
        print(f"check_readme: {line}")
    if found:
        print(f"check_readme: {len(found)} examples do not run")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
