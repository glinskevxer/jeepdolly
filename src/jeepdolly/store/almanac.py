"""Reading and writing the seasonal orders and the embargoes.

Both are the same shape: a header with a span, and a set of counties in a side
table. A statewide embargo has no county rows at all, which is the one thing to
know when reading this: an empty county set means everywhere, not nowhere.

The books come back built, which runs the same duplicate code check the office
would run on a hand written list. That is worth the cost because the books are
read once at the top of a decision and passed down.
"""

from __future__ import annotations

import sqlite3

from jeepdolly.almanac.embargo import Embargo, EmbargoBook
from jeepdolly.almanac.holiday import embargoes_in
from jeepdolly.almanac.season import Season, SeasonBook
from jeepdolly.errors import ConflictError, NotFoundError
from jeepdolly.ids.reference import Code, code
from jeepdolly.store.sqlite import maybe_one, rows, scalar
from jeepdolly.units.clock import DaySpan, Window, format_day, parse_day

__all__ = ["AlmanacStore"]


class AlmanacStore:
    """Every seasonal order and every embargo the office keeps."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Hold the open connection this store reads and writes."""
        self.connection = connection

    def _counties(self, table: str, column: str, key: str) -> frozenset[str]:
        """The counties named against one order."""
        found = rows(
            self.connection,
            f"SELECT county FROM {table} WHERE {column} = ? ORDER BY county",
            (key,),
        )
        return frozenset(row["county"] for row in found)

    def add_season(self, season: Season) -> Season:
        """Write a seasonal order and the counties it covers."""
        if self.find_season(str(season.code)) is not None:
            raise ConflictError("season", season.code)
        self.connection.execute(
            "INSERT INTO season (code, first_day, last_day, percent, note)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                str(season.code),
                format_day(season.span.first),
                format_day(season.span.last),
                season.percent,
                season.note,
            ),
        )
        for county in sorted(season.counties):
            self.connection.execute(
                "INSERT INTO season_county (season_code, county) VALUES (?, ?)",
                (str(season.code), county),
            )
        return season

    def _season_from_row(self, row: sqlite3.Row) -> Season:
        return Season(
            code=Code(row["code"]),
            span=DaySpan(parse_day(row["first_day"]), parse_day(row["last_day"])),
            percent=int(row["percent"]),
            counties=self._counties("season_county", "season_code", row["code"]),
            note=row["note"],
        )

    def find_season(self, key: str) -> Season | None:
        """One seasonal order by code, or ``None``."""
        row = maybe_one(
            self.connection, "SELECT * FROM season WHERE code = ?", (str(code(str(key))),)
        )
        return None if row is None else self._season_from_row(row)

    def get_season(self, key: str) -> Season:
        """One seasonal order by code, raising if it is not there."""
        found = self.find_season(key)
        if found is None:
            raise NotFoundError("season", str(code(str(key))))
        return found

    def seasons(self) -> list[Season]:
        """Every seasonal order, in code order."""
        return [
            self._season_from_row(row)
            for row in rows(self.connection, "SELECT * FROM season ORDER BY code")
        ]

    def season_book(self) -> SeasonBook:
        """Every seasonal order, built into a book."""
        return SeasonBook(seasons=tuple(self.seasons()))

    def remove_season(self, key: str) -> None:
        """Take a seasonal order off the books."""
        self.get_season(key)
        self.connection.execute("DELETE FROM season WHERE code = ?", (str(code(str(key))),))

    def add_embargo(self, embargo: Embargo) -> Embargo:
        """Write an embargo and the counties it covers."""
        if self.find_embargo(str(embargo.code)) is not None:
            raise ConflictError("embargo", embargo.code)
        window = embargo.window
        self.connection.execute(
            "INSERT INTO embargo (code, first_day, last_day, reason, window_start,"
            " window_end, weekends_only) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(embargo.code),
                format_day(embargo.span.first),
                format_day(embargo.span.last),
                embargo.reason,
                None if window is None else window.start,
                None if window is None else window.end,
                int(embargo.weekends_only),
            ),
        )
        for county in sorted(embargo.counties or ()):
            self.connection.execute(
                "INSERT INTO embargo_county (embargo_code, county) VALUES (?, ?)",
                (str(embargo.code), county),
            )
        return embargo

    def _embargo_from_row(self, row: sqlite3.Row) -> Embargo:
        counties = self._counties("embargo_county", "embargo_code", row["code"])
        start = row["window_start"]
        end = row["window_end"]
        return Embargo(
            code=Code(row["code"]),
            span=DaySpan(parse_day(row["first_day"]), parse_day(row["last_day"])),
            reason=row["reason"],
            window=None if start is None else Window(int(start), int(end)),
            counties=counties or None,
            weekends_only=bool(row["weekends_only"]),
        )

    def find_embargo(self, key: str) -> Embargo | None:
        """One embargo by code, or ``None``."""
        row = maybe_one(
            self.connection, "SELECT * FROM embargo WHERE code = ?", (str(code(str(key))),)
        )
        return None if row is None else self._embargo_from_row(row)

    def get_embargo(self, key: str) -> Embargo:
        """One embargo by code, raising if it is not there."""
        found = self.find_embargo(key)
        if found is None:
            raise NotFoundError("embargo", str(code(str(key))))
        return found

    def embargoes(self) -> list[Embargo]:
        """Every embargo, in code order."""
        return [
            self._embargo_from_row(row)
            for row in rows(self.connection, "SELECT * FROM embargo ORDER BY code")
        ]

    def embargo_book(self) -> EmbargoBook:
        """Every embargo, built into a book."""
        return EmbargoBook(embargoes=tuple(self.embargoes()))

    def remove_embargo(self, key: str) -> None:
        """Take an embargo off the books."""
        self.get_embargo(key)
        self.connection.execute("DELETE FROM embargo WHERE code = ?", (str(code(str(key))),))

    def load_holidays(self, year: int) -> list[Embargo]:
        """Put a year of holiday embargoes on the books, skipping any already there."""
        written: list[Embargo] = []
        for embargo in embargoes_in(year):
            if self.find_embargo(str(embargo.code)) is None:
                written.append(self.add_embargo(embargo))
        return written

    def counts(self) -> tuple[int, int]:
        """How many seasonal orders and embargoes are on file."""
        return (
            int(scalar(self.connection, "SELECT count(*) FROM season") or 0),
            int(scalar(self.connection, "SELECT count(*) FROM embargo") or 0),
        )
