"""The open office: one file, one connection, all the stores hanging off it.

Everything above this layer takes an ``Office`` rather than a connection, so no
caller has to know the table names or remember to turn foreign keys on. The
handle is deliberately not a context manager itself. ``opened_office`` is, and
making the handle one as well produced code that opened the file twice and
looked correct.

Opening and creating are separate calls. Opening a file that has never been
migrated raises rather than quietly migrating it, because the office runs
against a shared file on a share drive and a stray path typo used to create an
empty database next to the real one and then report that every carrier was gone.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from jeepdolly.errors import ConflictError, NotFoundError
from jeepdolly.store.carriers import CarrierStore
from jeepdolly.store.loads import LoadStore
from jeepdolly.store.migrations import LATEST, migrate, version
from jeepdolly.store.rigs import RigStore
from jeepdolly.store.sqlite import MEMORY, opened, writing

__all__ = ["Office", "create", "opened_new_office", "opened_office"]


class Office:
    """An open permit office file."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.carriers = CarrierStore(connection)
        self.rigs = RigStore(connection)
        self.loads = LoadStore(connection)

    @property
    def version(self) -> int:
        """The schema version this file is at."""
        return version(self.connection)

    @property
    def current(self) -> bool:
        """Is the file at the latest schema version."""
        return self.version == LATEST

    @contextmanager
    def writing(self) -> Iterator[Office]:
        """Run a block inside one immediate transaction."""
        with writing(self.connection):
            yield self

    def commit(self) -> None:
        """Write out whatever is pending."""
        self.connection.commit()

    def rollback(self) -> None:
        """Throw away whatever is pending."""
        self.connection.rollback()

    def upgrade(self) -> list[int]:
        """Apply any migrations this file has not seen."""
        return migrate(self.connection)

    def __repr__(self) -> str:
        return f"<Office at schema {self.version}>"


def create(path: str | Path) -> None:
    """Make a new office file and bring it up to date.

    Refuses a path that is already a file. Creating over an existing office is
    not something the office ever wants to do by accident, and doing it on
    purpose is a delete followed by a create.
    """
    target = Path(path)
    if str(path) != MEMORY and target.exists():
        raise ConflictError("office file", str(target))
    with opened(path) as connection:
        migrate(connection)


@contextmanager
def opened_office(path: str | Path) -> Iterator[Office]:
    """Open an existing office file, raising if it has no schema."""
    target = Path(path)
    if str(path) != MEMORY and not target.exists():
        raise NotFoundError("office file", str(target))
    with opened(path) as connection:
        office = Office(connection)
        if office.version == 0:
            raise NotFoundError("office schema", str(target))
        yield office


@contextmanager
def opened_new_office(path: str | Path = MEMORY) -> Iterator[Office]:
    """Create an office and open it in one step, for tests and for ``init``."""
    create(path)
    if str(path) == MEMORY:
        # An in memory database dies with its connection, so it has to be
        # created and used on the same one rather than reopened.
        with opened(path) as connection:
            office = Office(connection)
            office.upgrade()
            yield office
        return
    with opened_office(path) as office:
        yield office
