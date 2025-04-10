"""Reading and writing rigs.

A rig is two tables. The header carries whose it is and when it was recorded,
and the axle table carries the arrangement one row per axle with the spacing to
the axle ahead of it. Storing the spacing on the axle behind it, rather than in
a separate list, is the one shape that cannot get out of step with the axle
count, and getting those two out of step is how a rig ends up with four axles
and three and a half spacings.

Position zero always carries a spacing of zero, because there is nothing ahead
of the steer axle. The reader drops it and the writer puts it back.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from dataclasses import dataclass

from jeepdolly.errors import BadValueError, ConflictError, NotFoundError
from jeepdolly.ids.reference import RIG, Code, Serial, code, serial
from jeepdolly.rig.axle import Axle
from jeepdolly.rig.config import Configuration
from jeepdolly.store.sqlite import maybe_one, one, rows, scalar
from jeepdolly.units.clock import Day, format_day, parse_day
from jeepdolly.units.length import inches
from jeepdolly.units.mass import pounds

__all__ = ["FiledRig", "RigStore"]


@dataclass(frozen=True, slots=True)
class FiledRig:
    """A configuration as the office holds it, with its paperwork."""

    reference: Serial
    carrier: Code
    config: Configuration
    recorded_on: Day

    def __post_init__(self) -> None:
        object.__setattr__(self, "reference", serial(str(self.reference)))
        object.__setattr__(self, "carrier", code(str(self.carrier)))
        if not isinstance(self.recorded_on, dt.date) or isinstance(
            self.recorded_on, dt.datetime
        ):
            raise BadValueError("recorded on", self.recorded_on, "want a date")

    @property
    def name(self) -> Code:
        """The carrier's shorthand for the arrangement."""
        return self.config.name

    def __str__(self) -> str:
        return f"{self.reference} {self.carrier} {self.config}"


class RigStore:
    """Every rig the office has recorded."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def next_reference(self) -> Serial:
        """The reference the next rig will be filed under."""
        highest = scalar(self.connection, "SELECT max(reference) FROM rig")
        if highest is None:
            return RIG.format(1)
        return RIG.format(RIG.number(str(highest)) + 1)

    def add(self, carrier: str, config: Configuration, recorded_on: Day) -> FiledRig:
        """File a rig under the next reference."""
        owner = code(str(carrier))
        known = maybe_one(
            self.connection, "SELECT code FROM carrier WHERE code = ?", (str(owner),)
        )
        if known is None:
            raise NotFoundError("carrier", str(owner))
        reference = self.next_reference()
        self.connection.execute(
            "INSERT INTO rig (reference, carrier_code, name, recorded_on) VALUES (?, ?, ?, ?)",
            (str(reference), str(owner), str(config.name), format_day(recorded_on)),
        )
        self._write_axles(reference, config)
        return FiledRig(
            reference=reference, carrier=owner, config=config, recorded_on=recorded_on
        )

    def put(self, filed: FiledRig) -> FiledRig:
        """File a rig under a reference the caller has chosen."""
        if self.find(filed.reference) is not None:
            raise ConflictError("rig", filed.reference)
        known = maybe_one(
            self.connection, "SELECT code FROM carrier WHERE code = ?", (str(filed.carrier),)
        )
        if known is None:
            raise NotFoundError("carrier", str(filed.carrier))
        self.connection.execute(
            "INSERT INTO rig (reference, carrier_code, name, recorded_on) VALUES (?, ?, ?, ?)",
            (
                str(filed.reference),
                str(filed.carrier),
                str(filed.config.name),
                format_day(filed.recorded_on),
            ),
        )
        self._write_axles(filed.reference, filed.config)
        return filed

    def _write_axles(self, reference: Serial, config: Configuration) -> None:
        spacings = (0, *[int(s) for s in config.spacings])
        for position, (axle, ahead) in enumerate(zip(config.axles, spacings, strict=True)):
            self.connection.execute(
                "INSERT INTO rig_axle (rig_reference, position, weight, tires, tire_width,"
                " liftable, steering, spacing_ahead) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    str(reference),
                    position,
                    int(axle.weight),
                    axle.tires,
                    int(axle.tire_width),
                    int(axle.liftable),
                    int(axle.steering),
                    ahead,
                ),
            )

    def _read_config(self, reference: Serial, name: str) -> Configuration:
        found = rows(
            self.connection,
            "SELECT * FROM rig_axle WHERE rig_reference = ? ORDER BY position",
            (str(reference),),
        )
        if not found:
            raise NotFoundError("rig axles", str(reference))
        axles = tuple(
            Axle(
                weight=pounds(int(row["weight"])),
                tires=int(row["tires"]),
                tire_width=inches(int(row["tire_width"])),
                liftable=bool(row["liftable"]),
                steering=bool(row["steering"]),
            )
            for row in found
        )
        spacings = tuple(inches(int(row["spacing_ahead"])) for row in found[1:])
        return Configuration(name=Code(name), axles=axles, spacings=spacings)

    def _from_row(self, row: sqlite3.Row) -> FiledRig:
        reference = serial(row["reference"])
        return FiledRig(
            reference=reference,
            carrier=Code(row["carrier_code"]),
            config=self._read_config(reference, row["name"]),
            recorded_on=parse_day(row["recorded_on"]),
        )

    def get(self, key: str) -> FiledRig:
        """One rig by reference, raising if it is not there."""
        wanted = serial(str(key))
        row = one(
            self.connection, "SELECT * FROM rig WHERE reference = ?", (str(wanted),), kind="rig"
        )
        return self._from_row(row)

    def find(self, key: str) -> FiledRig | None:
        """One rig by reference, or ``None``."""
        wanted = serial(str(key))
        row = maybe_one(
            self.connection, "SELECT * FROM rig WHERE reference = ?", (str(wanted),)
        )
        return None if row is None else self._from_row(row)

    def for_carrier(self, carrier: str) -> list[FiledRig]:
        """Every rig filed against one carrier, oldest first."""
        owner = code(str(carrier))
        return [
            self._from_row(row)
            for row in rows(
                self.connection,
                "SELECT * FROM rig WHERE carrier_code = ? ORDER BY reference",
                (str(owner),),
            )
        ]

    def all(self) -> list[FiledRig]:
        """Every rig, in reference order."""
        return [
            self._from_row(row)
            for row in rows(self.connection, "SELECT * FROM rig ORDER BY reference")
        ]

    def remove(self, key: str) -> None:
        """Delete a rig and its axles."""
        self.get(key)
        self.connection.execute("DELETE FROM rig WHERE reference = ?", (str(serial(str(key))),))

    def count(self) -> int:
        """How many rigs are on file."""
        return int(scalar(self.connection, "SELECT count(*) FROM rig") or 0)

    def __len__(self) -> int:
        return self.count()
