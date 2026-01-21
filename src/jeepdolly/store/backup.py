"""Copying the office file safely, and asking sqlite whether it is sound.

Copying a live sqlite file with ``cp`` is the classic way to get a backup that
restores into a file with half a transaction in it. Sqlite's own backup API
copies page by page while holding the right locks, so that is what this uses, and
it is why this module exists rather than a line of shell in the runbook.

The integrity check is separate and worth running on its own. It walks every page
and every index and is the only thing that will tell you a disk has been quietly
corrupting rows, which is not a thing the office would otherwise notice until an
auditor asked why a carrier had two accounts.

Vacuuming is here too because a file that has had a year of permits deleted out
of it is mostly free pages, and the office copies that file to a share drive
every night.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from jeepdolly.errors import BadValueError, ConflictError, NotFoundError
from jeepdolly.store.migrations import LATEST, version
from jeepdolly.store.sqlite import MEMORY, connect, opened, rows, scalar, table_names

__all__ = ["Soundness", "back_up", "check_file", "file_size", "row_counts", "vacuum"]


@dataclass(frozen=True, slots=True)
class Soundness:
    """What sqlite says about a file, and what the office says about it."""

    integrity: str
    foreign_keys: int
    schema: int
    tables: int

    @property
    def sound(self) -> bool:
        """Is the file whole and up to date."""
        return self.integrity == "ok" and self.foreign_keys == 0 and self.schema == LATEST

    @property
    def trouble(self) -> tuple[str, ...]:
        """Everything wrong with the file, one line each."""
        found: list[str] = []
        if self.integrity != "ok":
            found.append(f"sqlite reports {self.integrity}")
        if self.foreign_keys:
            found.append(f"{self.foreign_keys} rows point at records that are gone")
        if self.schema != LATEST:
            found.append(f"schema is at {self.schema} and the office is at {LATEST}")
        return tuple(found)

    def __str__(self) -> str:
        if self.sound:
            return f"sound, schema {self.schema}, {self.tables} tables"
        return "; ".join(self.trouble)


def check_file(path: str | Path) -> Soundness:
    """Ask sqlite whether a file is whole, and the office whether it is current."""
    target = Path(path)
    if str(path) != MEMORY and not target.exists():
        raise NotFoundError("office file", str(target))
    with opened(path) as connection:
        integrity = str(scalar(connection, "PRAGMA integrity_check") or "unknown")
        broken = len(rows(connection, "PRAGMA foreign_key_check"))
        return Soundness(
            integrity=integrity,
            foreign_keys=broken,
            schema=version(connection),
            tables=len(table_names(connection)),
        )


def back_up(source: str | Path, target: str | Path) -> Path:
    """Copy an office file page by page, refusing to write over one that is there."""
    from_path = Path(source)
    to_path = Path(target)
    if not from_path.exists():
        raise NotFoundError("office file", str(from_path))
    if from_path.resolve() == to_path.resolve():
        # Checked before the plain "it is already there" case, so that copying a
        # file onto itself says what is actually wrong with it.
        raise BadValueError("backup", str(to_path), "is the file being copied")
    if to_path.exists():
        raise ConflictError("backup file", str(to_path))
    to_path.parent.mkdir(parents=True, exist_ok=True)
    with opened(from_path) as live, closing(connect(to_path)) as copy:
        live.backup(copy)
    return to_path


def vacuum(path: str | Path) -> int:
    """Rebuild a file into as few pages as it needs, and say how many bytes it saved."""
    target = Path(path)
    if not target.exists():
        raise NotFoundError("office file", str(target))
    before = file_size(target)
    with opened(target) as connection:
        connection.execute("VACUUM")
    return max(0, before - file_size(target))


def file_size(path: str | Path) -> int:
    """How many bytes a file takes, counting its write ahead log."""
    target = Path(path)
    total = target.stat().st_size if target.exists() else 0
    for suffix in ("-wal", "-shm"):
        beside = target.with_name(target.name + suffix)
        if beside.exists():
            total += beside.stat().st_size
    return total


def row_counts(connection: sqlite3.Connection) -> dict[str, int]:
    """How many rows each table holds, in name order."""
    out: dict[str, int] = {}
    for table in table_names(connection):
        # The table name comes from sqlite's own catalogue, never from a caller.
        out[table] = int(scalar(connection, f"SELECT count(*) FROM {table}") or 0)
    return out
