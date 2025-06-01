"""Reading and writing applications.

The load is written first and the application points at it. That is one extra
row and one extra join and it earns both back the first time a carrier applies
twice for the same transformer: the two applications are separate records that
happen to describe the same piece of freight, and a report can say so.

Everything is written through the model's own validation on the way out, so an
application that has been edited in the file into a shape the office would never
accept fails on the read rather than on the decision.
"""

from __future__ import annotations

import sqlite3

from jeepdolly.errors import NotFoundError
from jeepdolly.ids.reference import Code, Serial, code
from jeepdolly.permit.application import Application, Kind
from jeepdolly.store.loads import LoadStore, load_from_row
from jeepdolly.store.sqlite import maybe_one, one, rows, scalar
from jeepdolly.units.clock import Day, DaySpan, format_day, parse_day

__all__ = ["ApplicationStore", "FiledApplication", "application_from_row"]

_COLUMNS = (
    "carrier_code",
    "rig_reference",
    "load_id",
    "kind",
    "first_day",
    "last_day",
    "filed_on",
    "origin",
    "destination",
)


def application_from_row(row: sqlite3.Row) -> Application:
    """Build an application out of one joined row."""
    return Application(
        carrier=Code(row["carrier_code"]),
        rig=Serial(row["rig_reference"]),
        load=load_from_row(row),
        span=DaySpan(parse_day(row["first_day"]), parse_day(row["last_day"])),
        filed_on=parse_day(row["filed_on"]),
        kind=Kind(row["kind"]),
        origin=None if row["origin"] is None else Code(row["origin"]),
        destination=None if row["destination"] is None else Code(row["destination"]),
    )


class FiledApplication:
    """An application with the key the office filed it under."""

    __slots__ = ("application", "key", "load_id")

    def __init__(self, key: int, application: Application, load_id: int) -> None:
        self.key = key
        self.application = application
        self.load_id = load_id

    def __repr__(self) -> str:
        return f"<FiledApplication {self.key} {self.application}>"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FiledApplication):
            return NotImplemented
        return (self.key, self.application) == (other.key, other.application)

    def __hash__(self) -> int:
        return hash((self.key, self.application))


class ApplicationStore:
    """Every application the office has taken."""

    _JOIN = (
        "SELECT a.*, l.description, l.weight, l.width, l.height, l.length,"
        " l.front_overhang, l.rear_overhang, l.divisible, l.reason"
        " FROM application a JOIN load_item l ON l.id = a.load_id"
    )

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.loads = LoadStore(connection)

    def add(self, application: Application) -> FiledApplication:
        """Write an application and the load it describes."""
        for kind, table, column, wanted in (
            ("carrier", "carrier", "code", str(application.carrier)),
            ("rig", "rig", "reference", str(application.rig)),
        ):
            found = maybe_one(
                self.connection, f"SELECT 1 FROM {table} WHERE {column} = ?", (wanted,)
            )
            if found is None:
                raise NotFoundError(kind, wanted)
        load_id = self.loads.add(application.load)
        names = ", ".join(_COLUMNS)
        placeholders = ", ".join("?" for _ in _COLUMNS)
        cursor = self.connection.execute(
            f"INSERT INTO application ({names}) VALUES ({placeholders})",
            (
                str(application.carrier),
                str(application.rig),
                load_id,
                str(application.kind),
                format_day(application.span.first),
                format_day(application.span.last),
                format_day(application.filed_on),
                None if application.origin is None else str(application.origin),
                None if application.destination is None else str(application.destination),
            ),
        )
        key = cursor.lastrowid
        cursor.close()
        assert key is not None
        return FiledApplication(key=int(key), application=application, load_id=load_id)

    def get(self, key: int) -> FiledApplication:
        """One application by key, raising if it is not there."""
        row = one(
            self.connection, f"{self._JOIN} WHERE a.id = ?", (int(key),), kind="application"
        )
        return FiledApplication(
            key=int(row["id"]),
            application=application_from_row(row),
            load_id=int(row["load_id"]),
        )

    def find(self, key: int) -> FiledApplication | None:
        """One application by key, or ``None``."""
        row = maybe_one(self.connection, f"{self._JOIN} WHERE a.id = ?", (int(key),))
        if row is None:
            return None
        return FiledApplication(
            key=int(row["id"]),
            application=application_from_row(row),
            load_id=int(row["load_id"]),
        )

    def _many(self, sql: str, parameters: tuple[object, ...] = ()) -> list[FiledApplication]:
        return [
            FiledApplication(
                key=int(row["id"]),
                application=application_from_row(row),
                load_id=int(row["load_id"]),
            )
            for row in rows(self.connection, sql, parameters)
        ]

    def all(self) -> list[FiledApplication]:
        """Every application, oldest first."""
        return self._many(f"{self._JOIN} ORDER BY a.id")

    def for_carrier(self, carrier: str) -> list[FiledApplication]:
        """Every application from one carrier, oldest first."""
        owner = code(str(carrier))
        return self._many(f"{self._JOIN} WHERE a.carrier_code = ? ORDER BY a.id", (str(owner),))

    def on_day(self, day: Day) -> list[FiledApplication]:
        """Every application whose span covers one day."""
        stamp = format_day(day)
        return self._many(
            f"{self._JOIN} WHERE a.first_day <= ? AND a.last_day >= ? ORDER BY a.id",
            (stamp, stamp),
        )

    def of_kind(self, kind: Kind) -> list[FiledApplication]:
        """Every application of one kind, oldest first."""
        return self._many(f"{self._JOIN} WHERE a.kind = ? ORDER BY a.id", (str(Kind(kind)),))

    def count(self) -> int:
        """How many applications are on file."""
        return int(scalar(self.connection, "SELECT count(*) FROM application") or 0)

    def __len__(self) -> int:
        return self.count()
