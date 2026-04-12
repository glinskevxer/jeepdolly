"""Who to ring at a carrier, and about what.

A carrier is a company and a company does not answer the phone. The office rings
a dispatcher about a route, an accounts clerk about a balance, and a safety
manager when a load has come off. Those are three different people and putting
one phone number on the carrier record means two of those calls go to the wrong
one.

A number is stored as the digits, with everything else thrown away. Carriers give
the office numbers in six formats and a report that groups by number has to see
them as the same number. The formatter puts the punctuation back.

Exactly one contact per carrier is the primary. The office rings that one when it
does not know which role it wants, and the constraint is enforced in the file
rather than only here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from jeepdolly.errors import BadValueError
from jeepdolly.ids.reference import Code, code

__all__ = ["MAX_EMAIL", "MAX_NAME", "Contact", "Role", "digits_of", "format_number"]

MAX_NAME = 60
MAX_EMAIL = 120

_DIGIT = re.compile(r"\D+")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class Role(StrEnum):
    """What the office would ring this person about."""

    DISPATCH = "dispatch"
    ACCOUNTS = "accounts"
    SAFETY = "safety"
    OWNER = "owner"


def digits_of(text: str) -> str:
    """The digits of a phone number, with everything else thrown away.

    A leading country code of one is dropped, because every number the office
    holds is domestic and half of them arrive with it.
    """
    if not isinstance(text, str):
        raise BadValueError("number", text, "want text")
    only = _DIGIT.sub("", text)
    if len(only) == 11 and only.startswith("1"):
        only = only[1:]
    if len(only) != 10:
        raise BadValueError("number", text, "want ten digits")
    return only


def format_number(digits: str) -> str:
    """A stored number, punctuated the way the office prints it."""
    kept = digits_of(digits)
    return f"({kept[:3]}) {kept[3:6]}-{kept[6:]}"


@dataclass(frozen=True, slots=True, order=True)
class Contact:
    """One person at a carrier."""

    carrier: Code
    role: Role
    name: str
    number: str
    email: str = ""
    primary: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "carrier", code(str(self.carrier)))
        object.__setattr__(self, "role", Role(self.role))
        if not isinstance(self.name, str) or not self.name.strip():
            raise BadValueError("name", self.name, "want some text")
        tidy = " ".join(self.name.split())
        if len(tidy) > MAX_NAME:
            raise BadValueError("name", self.name, f"over {MAX_NAME} characters")
        object.__setattr__(self, "name", tidy)
        object.__setattr__(self, "number", digits_of(str(self.number)))
        if not isinstance(self.email, str):
            raise BadValueError("email", self.email, "want text")
        address = self.email.strip().lower()
        if address:
            if len(address) > MAX_EMAIL:
                raise BadValueError("email", self.email, f"over {MAX_EMAIL} characters")
            if not _EMAIL.match(address):
                raise BadValueError("email", self.email, "not an address")
        object.__setattr__(self, "email", address)
        if not isinstance(self.primary, bool):
            raise BadValueError("primary", self.primary, "want true or false")

    @property
    def printed(self) -> str:
        """The number as it goes on a printed sheet."""
        return format_number(self.number)

    def promoted(self) -> Contact:
        """The same contact, marked the one to ring by default."""
        return Contact(
            carrier=self.carrier,
            role=self.role,
            name=self.name,
            number=self.number,
            email=self.email,
            primary=True,
        )

    def demoted(self) -> Contact:
        """The same contact, no longer the default."""
        return Contact(
            carrier=self.carrier,
            role=self.role,
            name=self.name,
            number=self.number,
            email=self.email,
            primary=False,
        )

    def __str__(self) -> str:
        star = " *" if self.primary else ""
        tail = f" {self.email}" if self.email else ""
        return f"{self.carrier} {self.role} {self.name} {self.printed}{tail}{star}"
