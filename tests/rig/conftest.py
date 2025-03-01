"""Rigs the whole rig suite builds on."""

import pytest

from jeepdolly.rig.axle import Axle
from jeepdolly.rig.config import Configuration
from jeepdolly.units.length import Inches, feet, inches
from jeepdolly.units.mass import Pounds, pounds


def steer(weight: int = 12000) -> Axle:
    """The front axle, two tires."""
    return Axle(weight=pounds(weight), tires=2, tire_width=inches(11), steering=True)


def drive(weight: int = 17000, tires: int = 4, width: int = 11) -> Axle:
    """An ordinary load carrying axle."""
    return Axle(weight=pounds(weight), tires=tires, tire_width=inches(width))


def rig(name: str, axles: list[Axle], gaps: list[Inches]) -> Configuration:
    """Assemble a configuration without repeating the tuple calls."""
    return Configuration(name=name, axles=tuple(axles), spacings=tuple(gaps))  # type: ignore[arg-type]


@pytest.fixture
def five_axle() -> Configuration:
    """A legal 3S2: steer, tandem drive, tandem trailer."""
    return rig(
        "3S2",
        [steer(), drive(), drive(), drive(), drive()],
        [feet(15), feet(4), feet(30), feet(4)],
    )


@pytest.fixture
def seven_axle() -> Configuration:
    """A permit rig with a tridem trailer group."""
    return rig(
        "3S4",
        [steer(), drive(), drive(), drive(21000), drive(21000), drive(21000), drive(21000)],
        [feet(15), feet(4), feet(26), feet(5), feet(5), feet(5)],
    )


@pytest.fixture
def heavy_weights() -> tuple[Pounds, ...]:
    """Weights used where the arithmetic matters more than the rig."""
    return tuple(pounds(w) for w in (12000, 17000, 17000, 17000, 17000))
