"""What every command needs: the file to work on, and how to fail.

Commands are thin. They parse, they call one thing, and they print. Everything
that could be shared between two commands lives here so that the commands stay
readable side by side.

Errors from the package are turned into click's own failure, which prints one
line and exits two. A traceback on a mistyped carrier code is not useful to a
clerk, and the traceback is still available by running with ``--debug``.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import click

from jeepdolly.errors import JeepdollyError
from jeepdolly.store.office import Office, opened_office

__all__ = ["DEFAULT_FILE", "Session", "office_of", "reporting"]

#: The file a command works on when nothing says otherwise.
DEFAULT_FILE = Path("permits.sqlite3")


#: The most a clerk's sign on may be.
MAX_CLERK = 30


@dataclass(slots=True)
class Session:
    """The state a command inherits from the top level group.

    ``clerk`` is whoever is at the counter. It reaches the journal and nothing
    else, and it is allowed to be blank because the office ran for a year before
    anybody was asked to sign on.
    """

    path: Path
    debug: bool = False
    clerk: str = ""

    def __post_init__(self) -> None:
        tidy = " ".join(str(self.clerk).split())
        if len(tidy) > MAX_CLERK:
            raise click.BadParameter(f"a sign on is at most {MAX_CLERK} characters")
        self.clerk = tidy


@contextmanager
def office_of(session: Session) -> Iterator[Office]:
    """Open the session's file, turning package errors into clean failures."""
    with reporting(session), opened_office(session.path) as office:
        yield office


@contextmanager
def reporting(session: Session) -> Iterator[None]:
    """Turn a package error into a one line failure unless debugging."""
    try:
        yield
    except JeepdollyError as exc:
        if session.debug:
            raise
        raise click.ClickException(str(exc)) from exc
