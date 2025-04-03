"""The carrier, which is whoever the permit is written to.

A carrier is identified two ways and the office uses both. The USDOT number is
the federal one and is what the roadside enforcement officer reads. The code is
the office's own short key and is what a clerk types. They are kept separate
because a carrier can be reassigned a USDOT number after a merger and the
office's own records have to survive that without renumbering every permit.

A carrier that is not active can still be looked up and still owns its old
permits. It just cannot be issued a new one.
"""

from __future__ import annotations

from dataclasses import dataclass

from jeepdolly.errors import BadValueError
from jeepdolly.ids.reference import Code, code

__all__ = ["MAX_NAME", "MAX_USDOT", "STATES", "Carrier"]

#: The two letter postal codes the office will record a home state as. Only the
#: states, the district and the territories that issue an apportioned plate.
STATES = frozenset(
    """
    AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS
    MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI
    WY PR
    """.split()
)

#: USDOT numbers are seven digits at the time of writing and climbing.
MAX_USDOT = 99_999_999

MAX_NAME = 80


@dataclass(frozen=True, slots=True, order=True)
class Carrier:
    """One trucking company, as the office has it on file."""

    code: Code
    name: str
    usdot: int
    home_state: str
    active: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", code(str(self.code)))
        if not isinstance(self.name, str) or not self.name.strip():
            raise BadValueError("name", self.name, "want some text")
        tidy = " ".join(self.name.split())
        if len(tidy) > MAX_NAME:
            raise BadValueError("name", self.name, f"over {MAX_NAME} characters")
        object.__setattr__(self, "name", tidy)
        if isinstance(self.usdot, bool) or not isinstance(self.usdot, int):
            raise BadValueError("usdot", self.usdot, "want a whole number")
        if not 1 <= self.usdot <= MAX_USDOT:
            raise BadValueError("usdot", self.usdot, f"want 1 to {MAX_USDOT}")
        if not isinstance(self.home_state, str):
            raise BadValueError("home state", self.home_state, "want two letters")
        state = self.home_state.strip().upper()
        if state not in STATES:
            raise BadValueError("home state", self.home_state, "not a state we record")
        object.__setattr__(self, "home_state", state)
        if not isinstance(self.active, bool):
            raise BadValueError("active", self.active, "want true or false")

    @property
    def issuable(self) -> bool:
        """May a new permit be written to this carrier."""
        return self.active

    def retired(self) -> Carrier:
        """The same carrier, marked inactive."""
        return Carrier(
            code=self.code,
            name=self.name,
            usdot=self.usdot,
            home_state=self.home_state,
            active=False,
        )

    def restored(self) -> Carrier:
        """The same carrier, marked active again."""
        return Carrier(
            code=self.code,
            name=self.name,
            usdot=self.usdot,
            home_state=self.home_state,
            active=True,
        )

    def renamed(self, name: str) -> Carrier:
        """The same carrier under a new trading name."""
        return Carrier(
            code=self.code,
            name=name,
            usdot=self.usdot,
            home_state=self.home_state,
            active=self.active,
        )

    def __str__(self) -> str:
        tail = "" if self.active else " (inactive)"
        return f"{self.code} {self.name}, USDOT {self.usdot}{tail}"
