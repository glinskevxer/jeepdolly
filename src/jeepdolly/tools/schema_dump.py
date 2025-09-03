"""Generate the schema document from a freshly migrated file.

The schema is not written down anywhere a person can read it. It is a list of
migrations, and reading seven migrations to find out what columns ``permit`` has
is not something anybody should have to do. So the writer builds an office in
memory, applies every migration, and asks sqlite what it ended up with.

Asking sqlite rather than parsing the migration text is the point. A column added
in migration four and dropped in migration six does not appear, and the document
matches the file a clerk actually has.
"""

from __future__ import annotations

import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

from jeepdolly.store.migrations import LATEST, migrate
from jeepdolly.store.sqlite import MEMORY, opened, rows, table_names
from jeepdolly.tools.walk import repo_root

__all__ = [
    "DOC_NAME",
    "Column",
    "columns_of",
    "doc_path",
    "indexes_of",
    "main",
    "render",
    "write",
]

#: Where the schema document is committed.
DOC_NAME = "schema.md"


def doc_path() -> Path:
    """Where the schema document lives."""
    return repo_root() / "docs" / DOC_NAME


@dataclass(frozen=True, slots=True)
class Column:
    """One column as sqlite reports it."""

    name: str
    kind: str
    not_null: bool
    default: str
    primary_key: bool

    @property
    def note(self) -> str:
        """The constraints on this column, as one field."""
        parts: list[str] = []
        if self.primary_key:
            parts.append("primary key")
        if self.not_null:
            parts.append("not null")
        if self.default:
            parts.append(f"default {self.default}")
        return ", ".join(parts)


def columns_of(connection: sqlite3.Connection, table: str) -> list[Column]:
    """Every column of one table, in declared order."""
    if table not in table_names(connection):
        return []
    out: list[Column] = []
    for row in rows(connection, f"PRAGMA table_info({table})"):
        out.append(
            Column(
                name=row["name"],
                kind=row["type"] or "",
                not_null=bool(row["notnull"]),
                default="" if row["dflt_value"] is None else str(row["dflt_value"]),
                primary_key=bool(row["pk"]),
            )
        )
    return out


def indexes_of(connection: sqlite3.Connection, table: str) -> list[str]:
    """Every index the office declared on one table, by name."""
    found = rows(
        connection,
        "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = ?"
        " AND sql IS NOT NULL ORDER BY name",
        (table,),
    )
    return [row["name"] for row in found]


def render() -> str:
    """The whole schema document as text."""
    lines = [
        "# jeepdolly schema",
        "",
        "Generated from a freshly migrated file by `tools/schema_dump.py`.",
        "Run that with `--write` after adding a migration.",
        "",
        f"Schema version {LATEST}.",
    ]
    with opened(MEMORY) as connection:
        migrate(connection)
        for table in table_names(connection):
            lines.append("")
            lines.append(f"## {table}")
            lines.append("")
            lines.append("| column | type | constraints |")
            lines.append("| --- | --- | --- |")
            for column in columns_of(connection, table):
                lines.append(f"| {column.name} | {column.kind} | {column.note} |")
            names = indexes_of(connection, table)
            if names:
                lines.append("")
                lines.append("Indexes: " + ", ".join(f"`{name}`" for name in names))
    return "\n".join(lines).rstrip() + "\n"


def write() -> Path:
    """Write the schema document out and hand back where it went."""
    path = doc_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    """Write the schema document, or check the committed one is current."""
    args = sys.argv[1:] if argv is None else argv
    if "--write" in args:
        print(f"schema_dump: wrote {write()}")
        return 0
    path = doc_path()
    if not path.exists():
        print(f"schema_dump: {path} has never been written")
        return 1
    if path.read_text(encoding="utf-8") != render():
        print(f"schema_dump: {path} is out of date, run with --write")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
