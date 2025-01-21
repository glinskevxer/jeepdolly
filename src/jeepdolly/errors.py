"""The error vocabulary.

Every failure this package raises is one of these. Callers that want to tell a
bad input from a bad state from a bad question should catch the specific class,
not ``JeepdollyError``, which exists so a top level handler has one thing to
catch.
"""

from __future__ import annotations

__all__ = [
    "BadValueError",
    "ConflictError",
    "JeepdollyError",
    "NotAllowedError",
    "NotFoundError",
]


class JeepdollyError(Exception):
    """Base for everything raised on purpose in this package."""


class BadValueError(JeepdollyError):
    """A value does not parse, or is outside the range the office accepts.

    This is for input that is wrong on its face, before anything is looked up.
    A width of negative four inches is a ``BadValueError``. A width of forty feet is
    not, because that is a legal question and the answer depends on the route.
    """

    def __init__(self, what: str, given: object, why: str = "") -> None:
        self.what = what
        self.given = given
        self.why = why
        tail = f": {why}" if why else ""
        super().__init__(f"{what} {given!r} is not usable{tail}")


class NotFoundError(JeepdollyError):
    """A record was asked for by key and is not there."""

    def __init__(self, kind: str, key: object) -> None:
        self.kind = kind
        self.key = key
        super().__init__(f"no {kind} with key {key!r}")


class ConflictError(JeepdollyError):
    """A write would collide with a record that is already there."""

    def __init__(self, kind: str, key: object) -> None:
        self.kind = kind
        self.key = key
        super().__init__(f"{kind} {key!r} already exists")


class NotAllowedError(JeepdollyError):
    """The record exists and the operation is refused on its current state.

    Voiding a permit that is already void is the shape of this. Nothing is
    missing and nothing is malformed, the office just will not do it twice.
    """

    def __init__(self, what: str, state: str, wanted: str) -> None:
        self.what = what
        self.state = state
        self.wanted = wanted
        super().__init__(f"cannot {wanted} a {what} that is {state}")
