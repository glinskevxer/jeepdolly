"""Loads and applications the permit suite builds on."""

import datetime as dt

import pytest

from jeepdolly.permit.application import Application, Kind
from jeepdolly.rig.load import Load
from jeepdolly.units.clock import DaySpan
from jeepdolly.units.length import feet, feet_inches
from jeepdolly.units.mass import pounds

FILED = dt.date(2025, 6, 16)
TRIP = DaySpan(dt.date(2025, 6, 18), dt.date(2025, 6, 20))


def a_load(**over: object) -> Load:
    """A transformer on a lowboy."""
    kw: dict[str, object] = {
        "description": "step-up transformer",
        "weight": pounds(148000),
        "width": feet_inches(12, 6),
        "height": feet_inches(14, 2),
        "length": feet(48),
        "divisible": False,
        "reason": "single-piece",
    }
    kw.update(over)
    return Load(**kw)  # type: ignore[arg-type]


def an_application(**over: object) -> Application:
    """A single trip application, with any part of it swapped out."""
    kw: dict[str, object] = {
        "carrier": "VANCE",
        "rig": "R-00001",
        "load": a_load(),
        "span": TRIP,
        "filed_on": FILED,
        "kind": Kind.TRIP,
        "origin": "JCT-A",
        "destination": "JCT-D",
    }
    kw.update(over)
    return Application(**kw)  # type: ignore[arg-type]


@pytest.fixture
def trip() -> Application:
    """The standard single trip application."""
    return an_application()
