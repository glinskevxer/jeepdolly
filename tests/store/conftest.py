"""A migrated in memory office for the store suite."""

import sqlite3
from collections.abc import Iterator

import pytest

from jeepdolly.store.migrations import migrate
from jeepdolly.store.sqlite import MEMORY, opened


@pytest.fixture
def raw() -> Iterator[sqlite3.Connection]:
    """An open connection with no schema at all."""
    with opened(MEMORY) as connection:
        yield connection


@pytest.fixture
def office(raw: sqlite3.Connection) -> sqlite3.Connection:
    """An open connection with every migration applied."""
    migrate(raw)
    return raw
