"""A migration that has run somewhere may never be edited again.

The office's file lives on a share drive and has been through every migration in
the list. Editing migration four now means a file created next week has a
different schema from the one that has been in use for a year, and there is
nothing in either file that says which.

So each migration is fingerprinted the first time it appears and the fingerprint
is committed. Changing a statement changes the fingerprint and fails the build.
Adding a migration is fine and only needs the lock file refreshed, which is what
``--update`` is for.

The lock is a plain text file, one line per migration, because a reviewer has to
be able to see in a diff that a new line was added rather than an old one
changed.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from jeepdolly.store.migrations import MIGRATIONS, Migration
from jeepdolly.tools.walk import package_root

__all__ = [
    "LOCK_NAME",
    "fingerprint",
    "lock_path",
    "main",
    "problems",
    "read_lock",
    "write_lock",
]

#: The committed fingerprints, beside the migrations they cover.
LOCK_NAME = "migrations.lock"


def lock_path() -> Path:
    """Where the lock file lives."""
    return package_root() / "store" / LOCK_NAME


def fingerprint(migration: Migration) -> str:
    """A stable digest of one migration's statements.

    Whitespace is collapsed first, so reformatting a statement is allowed and
    changing what it does is not. That is the line the office wants: a migration
    reindented by an editor should not fail the build.
    """
    body = "\n".join(" ".join(statement.split()) for statement in migration.statements)
    text = f"{migration.number}\n{migration.name}\n{body}"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def read_lock() -> dict[int, str]:
    """The committed fingerprints, by migration number."""
    path = lock_path()
    if not path.exists():
        return {}
    out: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        number, digest = line.split(None, 1)
        out[int(number)] = digest.strip()
    return out


def write_lock() -> Path:
    """Write the lock file from the migrations as they stand."""
    lines = ["# migration fingerprints, written by check_migrations --update"]
    lines.extend(f"{m.number} {fingerprint(m)}" for m in MIGRATIONS)
    path = lock_path()
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def problems() -> list[str]:
    """Every migration whose fingerprint has moved, or is missing."""
    locked = read_lock()
    found: list[str] = []
    for migration in MIGRATIONS:
        digest = fingerprint(migration)
        if migration.number not in locked:
            found.append(f"migration {migration.number} has no fingerprint on file")
        elif locked[migration.number] != digest:
            found.append(f"migration {migration.number} ({migration.name}) has been edited")
    for number in sorted(set(locked) - {m.number for m in MIGRATIONS}):
        found.append(f"migration {number} is fingerprinted and no longer in the list")
    return found


def main(argv: list[str] | None = None) -> int:
    """Check the fingerprints, or rewrite them when told to."""
    args = sys.argv[1:] if argv is None else argv
    if "--update" in args:
        print(f"check_migrations: wrote {write_lock()}")
        return 0
    found = problems()
    for line in found:
        print(f"check_migrations: {line}")
    if found:
        print("check_migrations: run with --update only when adding a migration")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
