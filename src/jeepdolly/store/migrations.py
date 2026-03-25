"""The schema, as an ordered list that only ever grows.

Every change to the file is a new migration appended to ``MIGRATIONS``. Nothing
edits an existing one, ever, including the ones that look obviously wrong in
hindsight, because an office that has been running for two years has files that
took the old one and there is no way to tell them apart afterwards.

The applied migrations are recorded in ``schema_change`` with the day they ran.
That table is created by the runner rather than by a migration, which is the one
piece of the schema that has to exist before any migration can.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from jeepdolly.errors import BadValueError
from jeepdolly.store.sqlite import rows, scalar, writing

__all__ = [
    "LATEST",
    "MIGRATIONS",
    "Migration",
    "applied",
    "check_order",
    "migrate",
    "pending",
    "version",
]


@dataclass(frozen=True, slots=True, order=True)
class Migration:
    """One numbered step, with the statements it runs."""

    number: int
    name: str
    statements: tuple[str, ...]

    def __post_init__(self) -> None:
        if isinstance(self.number, bool) or not isinstance(self.number, int):
            raise BadValueError("number", self.number, "want a whole number")
        if self.number < 1:
            raise BadValueError("number", self.number, "migrations start at 1")
        if not self.name.strip():
            raise BadValueError("name", self.name, "want some text")
        object.__setattr__(self, "statements", tuple(self.statements))
        if not self.statements:
            raise BadValueError("statements", self.name, "a migration does something")

    def run(self, connection: sqlite3.Connection) -> None:
        """Apply the statements and record that it happened."""
        for statement in self.statements:
            connection.execute(statement)
        connection.execute(
            "INSERT INTO schema_change (number, name) VALUES (?, ?)",
            (self.number, self.name),
        )


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        number=1,
        name="carriers",
        statements=(
            """
            CREATE TABLE carrier (
                code        TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                usdot       INTEGER NOT NULL UNIQUE,
                home_state  TEXT NOT NULL,
                active      INTEGER NOT NULL DEFAULT 1
                            CHECK (active IN (0, 1))
            )
            """,
            "CREATE INDEX carrier_by_name ON carrier (name)",
        ),
    ),
    Migration(
        number=2,
        name="rigs and their axles",
        statements=(
            """
            CREATE TABLE rig (
                reference     TEXT PRIMARY KEY,
                carrier_code  TEXT NOT NULL REFERENCES carrier (code),
                name          TEXT NOT NULL,
                recorded_on   TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE rig_axle (
                rig_reference  TEXT NOT NULL REFERENCES rig (reference) ON DELETE CASCADE,
                position       INTEGER NOT NULL,
                weight         INTEGER NOT NULL CHECK (weight >= 0),
                tires          INTEGER NOT NULL CHECK (tires > 0),
                tire_width     INTEGER NOT NULL CHECK (tire_width > 0),
                liftable       INTEGER NOT NULL DEFAULT 0 CHECK (liftable IN (0, 1)),
                steering       INTEGER NOT NULL DEFAULT 0 CHECK (steering IN (0, 1)),
                spacing_ahead  INTEGER NOT NULL DEFAULT 0 CHECK (spacing_ahead >= 0),
                PRIMARY KEY (rig_reference, position)
            )
            """,
            "CREATE INDEX rig_by_carrier ON rig (carrier_code)",
        ),
    ),
    Migration(
        number=3,
        name="loads",
        statements=(
            """
            CREATE TABLE load_item (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                description     TEXT NOT NULL,
                weight          INTEGER NOT NULL CHECK (weight >= 0),
                width           INTEGER NOT NULL CHECK (width > 0),
                height          INTEGER NOT NULL CHECK (height > 0),
                length          INTEGER NOT NULL CHECK (length > 0),
                front_overhang  INTEGER NOT NULL DEFAULT 0 CHECK (front_overhang >= 0),
                rear_overhang   INTEGER NOT NULL DEFAULT 0 CHECK (rear_overhang >= 0),
                divisible       INTEGER NOT NULL DEFAULT 1 CHECK (divisible IN (0, 1)),
                reason          TEXT NOT NULL DEFAULT ''
            )
            """,
        ),
    ),
    Migration(
        number=4,
        name="the road map",
        statements=(
            """
            CREATE TABLE node (
                code    TEXT PRIMARY KEY,
                name    TEXT NOT NULL,
                county  TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE segment (
                code          TEXT PRIMARY KEY,
                start_node    TEXT NOT NULL REFERENCES node (code),
                end_node      TEXT NOT NULL REFERENCES node (code),
                route         TEXT NOT NULL,
                distance      INTEGER NOT NULL CHECK (distance > 0),
                road_class    TEXT NOT NULL
                              CHECK (road_class IN ('interstate', 'state', 'local')),
                one_way       INTEGER NOT NULL DEFAULT 0 CHECK (one_way IN (0, 1)),
                posted_gross  INTEGER CHECK (posted_gross IS NULL OR posted_gross > 0),
                CHECK (start_node <> end_node)
            )
            """,
            """
            CREATE TABLE structure (
                reference     TEXT PRIMARY KEY,
                segment_code  TEXT NOT NULL REFERENCES segment (code) ON DELETE CASCADE,
                name          TEXT NOT NULL,
                kind          TEXT NOT NULL
                              CHECK (kind IN ('bridge', 'culvert', 'overhead', 'tunnel')),
                milepost      INTEGER NOT NULL CHECK (milepost >= 0),
                clearance     INTEGER CHECK (clearance IS NULL OR clearance > 0),
                rating        INTEGER CHECK (rating IS NULL OR rating > 0),
                CHECK (clearance IS NULL OR rating IS NULL)
            )
            """,
            "CREATE INDEX segment_by_start ON segment (start_node)",
            "CREATE INDEX segment_by_end ON segment (end_node)",
            "CREATE INDEX structure_by_segment ON structure (segment_code, milepost)",
        ),
    ),
    Migration(
        number=5,
        name="applications",
        statements=(
            """
            CREATE TABLE application (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                carrier_code  TEXT NOT NULL REFERENCES carrier (code),
                rig_reference TEXT NOT NULL REFERENCES rig (reference),
                load_id       INTEGER NOT NULL REFERENCES load_item (id),
                kind          TEXT NOT NULL
                              CHECK (kind IN ('trip', 'annual', 'superload')),
                first_day     TEXT NOT NULL,
                last_day      TEXT NOT NULL,
                filed_on      TEXT NOT NULL,
                origin        TEXT REFERENCES node (code),
                destination   TEXT REFERENCES node (code),
                CHECK (last_day >= first_day),
                CHECK (
                    (kind = 'annual' AND origin IS NULL AND destination IS NULL)
                    OR (kind <> 'annual' AND origin IS NOT NULL AND destination IS NOT NULL)
                )
            )
            """,
            "CREATE INDEX application_by_carrier ON application (carrier_code, filed_on)",
            "CREATE INDEX application_by_day ON application (first_day, last_day)",
        ),
    ),
    Migration(
        number=6,
        name="permits and their working",
        statements=(
            """
            CREATE TABLE permit (
                number          TEXT PRIMARY KEY,
                application_id  INTEGER NOT NULL REFERENCES application (id),
                outcome         TEXT NOT NULL
                                CHECK (outcome IN ('issue', 'refer', 'refuse')),
                decided_on      TEXT NOT NULL,
                issued_on       TEXT NOT NULL,
                first_day       TEXT NOT NULL,
                last_day        TEXT NOT NULL,
                state           TEXT NOT NULL
                                CHECK (state IN ('active', 'void', 'superseded')),
                reason          TEXT NOT NULL DEFAULT '',
                replaced_by     TEXT REFERENCES permit (number),
                distance        INTEGER CHECK (distance IS NULL OR distance >= 0),
                CHECK (last_day >= first_day),
                CHECK (state <> 'void' OR reason <> ''),
                CHECK (state = 'superseded' OR replaced_by IS NULL)
            )
            """,
            """
            CREATE TABLE permit_finding (
                permit_number  TEXT NOT NULL REFERENCES permit (number) ON DELETE CASCADE,
                position       INTEGER NOT NULL,
                rule           TEXT NOT NULL,
                subject        TEXT NOT NULL,
                severity       TEXT NOT NULL
                               CHECK (severity IN ('note', 'permit', 'refuse')),
                detail         TEXT NOT NULL,
                excess         INTEGER NOT NULL DEFAULT 0 CHECK (excess >= 0),
                PRIMARY KEY (permit_number, position)
            )
            """,
            """
            CREATE TABLE permit_fee_line (
                permit_number  TEXT NOT NULL REFERENCES permit (number) ON DELETE CASCADE,
                position       INTEGER NOT NULL,
                code           TEXT NOT NULL,
                detail         TEXT NOT NULL,
                amount         INTEGER NOT NULL,
                PRIMARY KEY (permit_number, position),
                UNIQUE (permit_number, code)
            )
            """,
            """
            CREATE TABLE permit_escort (
                permit_number  TEXT NOT NULL REFERENCES permit (number) ON DELETE CASCADE,
                position       INTEGER NOT NULL,
                role           TEXT NOT NULL,
                reasons        TEXT NOT NULL,
                PRIMARY KEY (permit_number, position)
            )
            """,
            "CREATE INDEX permit_by_application ON permit (application_id)",
            "CREATE INDEX permit_by_day ON permit (first_day, last_day)",
        ),
    ),
    Migration(
        number=7,
        name="carrier accounts",
        statements=(
            """
            CREATE TABLE account_entry (
                carrier_code  TEXT NOT NULL REFERENCES carrier (code),
                sequence      INTEGER NOT NULL,
                day           TEXT NOT NULL,
                kind          TEXT NOT NULL
                              CHECK (kind IN ('deposit', 'charge', 'refund', 'adjustment')),
                amount        INTEGER NOT NULL,
                reference     TEXT NOT NULL DEFAULT '',
                note          TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (carrier_code, sequence),
                CHECK (kind = 'adjustment' OR amount > 0),
                CHECK (kind <> 'adjustment' OR (amount <> 0 AND note <> '')),
                CHECK (kind <> 'charge' OR reference <> '')
            )
            """,
            """
            CREATE TABLE account_terms (
                carrier_code  TEXT PRIMARY KEY REFERENCES carrier (code),
                floor         INTEGER NOT NULL CHECK (floor <= 0)
            )
            """,
            "CREATE INDEX account_by_day ON account_entry (carrier_code, day)",
        ),
    ),
    Migration(
        number=8,
        name="engineering reviews",
        statements=(
            """
            CREATE TABLE review (
                reference       TEXT PRIMARY KEY,
                application_id  INTEGER NOT NULL REFERENCES application (id),
                opened_on       TEXT NOT NULL,
                state           TEXT NOT NULL
                                CHECK (state IN ('open', 'approved', 'refused', 'withdrawn')),
                engineer        TEXT NOT NULL DEFAULT '',
                decided_on      TEXT,
                note            TEXT NOT NULL DEFAULT '',
                CHECK (state <> 'open' OR (decided_on IS NULL AND engineer = '')),
                CHECK (state = 'open' OR decided_on IS NOT NULL),
                CHECK (state <> 'refused' OR note <> '')
            )
            """,
            """
            CREATE TABLE review_condition (
                review_reference  TEXT NOT NULL REFERENCES review (reference) ON DELETE CASCADE,
                position          INTEGER NOT NULL,
                text              TEXT NOT NULL CHECK (text <> ''),
                PRIMARY KEY (review_reference, position)
            )
            """,
            "CREATE INDEX review_by_application ON review (application_id)",
            "CREATE INDEX review_by_state ON review (state, opened_on)",
        ),
    ),
    Migration(
        number=9,
        name="the almanac",
        statements=(
            """
            CREATE TABLE season (
                code       TEXT PRIMARY KEY,
                first_day  TEXT NOT NULL,
                last_day   TEXT NOT NULL,
                percent    INTEGER NOT NULL
                           CHECK (percent BETWEEN 25 AND 150 AND percent <> 100),
                note       TEXT NOT NULL DEFAULT '',
                CHECK (last_day >= first_day)
            )
            """,
            """
            CREATE TABLE season_county (
                season_code  TEXT NOT NULL REFERENCES season (code) ON DELETE CASCADE,
                county       TEXT NOT NULL CHECK (county <> ''),
                PRIMARY KEY (season_code, county)
            )
            """,
            """
            CREATE TABLE embargo (
                code           TEXT PRIMARY KEY,
                first_day      TEXT NOT NULL,
                last_day       TEXT NOT NULL,
                reason         TEXT NOT NULL CHECK (reason <> ''),
                window_start   INTEGER CHECK (window_start IS NULL
                                              OR window_start BETWEEN 0 AND 1439),
                window_end     INTEGER CHECK (window_end IS NULL
                                              OR window_end BETWEEN 0 AND 1439),
                weekends_only  INTEGER NOT NULL DEFAULT 0 CHECK (weekends_only IN (0, 1)),
                CHECK (last_day >= first_day),
                CHECK ((window_start IS NULL) = (window_end IS NULL))
            )
            """,
            """
            CREATE TABLE embargo_county (
                embargo_code  TEXT NOT NULL REFERENCES embargo (code) ON DELETE CASCADE,
                county        TEXT NOT NULL CHECK (county <> ''),
                PRIMARY KEY (embargo_code, county)
            )
            """,
            "CREATE INDEX season_by_day ON season (first_day, last_day)",
            "CREATE INDEX embargo_by_day ON embargo (first_day, last_day)",
        ),
    ),
    Migration(
        number=10,
        name="the journal",
        statements=(
            """
            CREATE TABLE journal (
                sequence  INTEGER PRIMARY KEY AUTOINCREMENT,
                day       TEXT NOT NULL,
                kind      TEXT NOT NULL CHECK (kind <> ''),
                subject   TEXT NOT NULL CHECK (subject <> ''),
                detail    TEXT NOT NULL DEFAULT '',
                clerk     TEXT NOT NULL DEFAULT ''
            )
            """,
            "CREATE INDEX journal_by_subject ON journal (subject, sequence)",
            "CREATE INDEX journal_by_day ON journal (day, sequence)",
        ),
    ),
    Migration(
        number=11,
        name="index the references sqlite does not",
        statements=(
            "CREATE INDEX application_by_rig ON application (rig_reference)",
            "CREATE INDEX application_by_load ON application (load_id)",
            "CREATE INDEX application_by_origin ON application (origin)",
            "CREATE INDEX application_by_destination ON application (destination)",
            "CREATE INDEX permit_by_successor ON permit (replaced_by)",
        ),
    ),
)

#: The number the schema reaches when every migration has run.
LATEST = MIGRATIONS[-1].number

_CHANGE_TABLE = """
CREATE TABLE IF NOT EXISTS schema_change (
    number  INTEGER PRIMARY KEY,
    name    TEXT NOT NULL,
    ran_at  TEXT NOT NULL DEFAULT (datetime('now'))
)
"""


def check_order(migrations: tuple[Migration, ...] = MIGRATIONS) -> None:
    """The list has to be 1, 2, 3 with no gaps and no repeats."""
    numbers = [m.number for m in migrations]
    if numbers != list(range(1, len(numbers) + 1)):
        raise BadValueError("migrations", numbers, "want 1..n with no gaps")
    names = [m.name for m in migrations]
    if len(set(names)) != len(names):
        raise BadValueError("migrations", names, "two of them share a name")


def applied(connection: sqlite3.Connection) -> list[int]:
    """The migration numbers already in this file, in order."""
    connection.execute(_CHANGE_TABLE)
    found = rows(connection, "SELECT number FROM schema_change ORDER BY number")
    return [row["number"] for row in found]


def pending(connection: sqlite3.Connection) -> list[Migration]:
    """The migrations this file has not seen yet."""
    check_order()
    done = set(applied(connection))
    return [m for m in MIGRATIONS if m.number not in done]


def migrate(connection: sqlite3.Connection) -> list[int]:
    """Bring the file up to date, returning what ran.

    Every migration runs in its own transaction. A failure halfway through a
    list leaves the file at the last migration that completed, which is a state
    the runner can pick up from next time.
    """
    ran: list[int] = []
    for migration in pending(connection):
        with writing(connection):
            migration.run(connection)
        ran.append(migration.number)
    return ran


def version(connection: sqlite3.Connection) -> int:
    """The highest migration this file has applied, or zero."""
    connection.execute(_CHANGE_TABLE)
    found = scalar(connection, "SELECT max(number) FROM schema_change")
    return int(found) if found is not None else 0
