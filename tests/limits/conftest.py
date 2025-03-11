"""Rigs shared by the limits suite."""

import pytest

from jeepdolly.rig.axle import Axle
from jeepdolly.rig.config import Configuration
from jeepdolly.units.length import Inches, feet, inches
from jeepdolly.units.mass import pounds


def steer(weight: int = 12000) -> Axle:
    return Axle(weight=pounds(weight), tires=2, tire_width=inches(11), steering=True)


def drive(weight: int = 17000, tires: int = 4, width: int = 11) -> Axle:
    return Axle(weight=pounds(weight), tires=tires, tire_width=inches(width))


def rig(name: str, axles: list[Axle], gaps: list[Inches]) -> Configuration:
    return Configuration(name=name, axles=tuple(axles), spacings=tuple(gaps))  # type: ignore[arg-type]


@pytest.fixture
def legal_five() -> Configuration:
    """A 3S2 right at the federal numbers."""
    return rig(
        "3S2",
        [steer(), drive(), drive(), drive(), drive()],
        [feet(15), feet(4), feet(30), feet(4)],
    )


@pytest.fixture
def heavy_five() -> Configuration:
    """The same rig loaded well past every flat limit."""
    return rig(
        "3S2H",
        [steer(14000), drive(23000), drive(23000), drive(22000), drive(22000)],
        [feet(15), feet(4), feet(30), feet(4)],
    )
