"""Pilot cars, height poles and the state trooper.

An escort is not a fee, it is a person the carrier has to hire and put in a
vehicle, and the permit says how many and where. The thresholds are the office's
own and they are held in a schedule rather than as constants so a route through a
metropolitan district can carry a stricter one.

Duplicate roles collapse. Two rules that each call for a rear pilot car produce
one rear pilot car and two reasons, because the carrier hires one vehicle and
the trooper at the roadside wants to know why it is there.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from jeepdolly.errors import BadValueError
from jeepdolly.rig.load import Load
from jeepdolly.units.length import Inches, feet, feet_inches, format_length, inches

__all__ = ["ORDINARY", "Escort", "EscortSchedule", "Role", "escort_count", "escorts_for"]


class Role(StrEnum):
    """Where the escort rides and what it is for."""

    FRONT = "front"
    REAR = "rear"
    HEIGHT_POLE = "height pole"
    POLICE = "police"


_ORDER = {Role.POLICE: 0, Role.HEIGHT_POLE: 1, Role.FRONT: 2, Role.REAR: 3}


@dataclass(frozen=True, slots=True)
class Escort:
    """One vehicle the carrier has to provide, and why."""

    role: Role
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "role", Role(self.role))
        object.__setattr__(self, "reasons", tuple(self.reasons))
        if not self.reasons:
            raise BadValueError("escort", self.role, "wants at least one reason")

    def __str__(self) -> str:
        return f"{self.role}: {', '.join(self.reasons)}"


@dataclass(frozen=True, slots=True)
class EscortSchedule:
    """The widths, lengths and heights that call for an escort."""

    name: str
    one_escort_width: Inches
    two_escort_width: Inches
    police_width: Inches
    escort_length: Inches
    pole_height: Inches
    escort_rear_overhang: Inches

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise BadValueError("name", self.name, "want some text")
        for field in (
            "one_escort_width",
            "two_escort_width",
            "police_width",
            "escort_length",
            "pole_height",
            "escort_rear_overhang",
        ):
            object.__setattr__(self, field, inches(int(getattr(self, field))))
        if int(self.two_escort_width) <= int(self.one_escort_width):
            raise BadValueError(
                "two escort width", self.two_escort_width, "not above the first"
            )
        if int(self.police_width) <= int(self.two_escort_width):
            raise BadValueError("police width", self.police_width, "not above the second")


#: The office's standing schedule.
ORDINARY = EscortSchedule(
    name="ordinary",
    one_escort_width=feet(12),
    two_escort_width=feet(14),
    police_width=feet(16),
    escort_length=feet(100),
    pole_height=feet_inches(15, 6),
    escort_rear_overhang=feet(20),
)


def _collect(load: Load, schedule: EscortSchedule) -> dict[Role, list[str]]:
    """Every rule that fires, gathered by the role it calls for."""
    wanted: dict[Role, list[str]] = {}

    def want(role: Role, reason: str) -> None:
        wanted.setdefault(role, []).append(reason)

    width = int(load.width)
    if width > int(schedule.one_escort_width):
        want(Role.REAR, f"width over {format_length(schedule.one_escort_width)}")
    if width > int(schedule.two_escort_width):
        want(Role.FRONT, f"width over {format_length(schedule.two_escort_width)}")
    if width > int(schedule.police_width):
        want(Role.POLICE, f"width over {format_length(schedule.police_width)}")
    if int(load.overall_length) > int(schedule.escort_length):
        want(Role.REAR, f"length over {format_length(schedule.escort_length)}")
    if int(load.height) > int(schedule.pole_height):
        want(Role.HEIGHT_POLE, f"height over {format_length(schedule.pole_height)}")
    if int(load.rear_overhang) > int(schedule.escort_rear_overhang):
        want(Role.REAR, f"rear overhang over {format_length(schedule.escort_rear_overhang)}")
    return wanted


def escorts_for(load: Load, schedule: EscortSchedule = ORDINARY) -> tuple[Escort, ...]:
    """Every escort this load calls for, most senior role first."""
    wanted = _collect(load, schedule)
    return tuple(
        Escort(role=role, reasons=tuple(wanted[role]))
        for role in sorted(wanted, key=lambda r: _ORDER[r])
    )


def escort_count(load: Load, schedule: EscortSchedule = ORDINARY) -> int:
    """How many vehicles the carrier has to put on the road."""
    return len(escorts_for(load, schedule))
