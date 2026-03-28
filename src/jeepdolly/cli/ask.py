"""The small conversions every command does before it calls anything.

Four modules had their own ``_today``, three of them identical and one of them a
line that would have used UTC on a machine set to anything else. One module had
its own comma separated list reader. None of that was a decision, and the copies
are the sort of thing that stay in step until the day they do not.

Everything here turns what a person typed into what the package takes. Nothing
here touches the file, and nothing below the command line imports it.
"""

from __future__ import annotations

import datetime as dt

import click

from jeepdolly.units.clock import Day, Window, parse_clock, parse_day
from jeepdolly.units.length import Inches, parse_length

__all__ = ["bytes_of", "county_list", "day_or_today", "length_or", "today", "window_of"]


def today() -> Day:
    """The office's idea of today.

    The machine's local date, not UTC. A permit office in Montana writing a
    permit at five in the afternoon would otherwise date it tomorrow for seven
    hours of every day, which is exactly the sort of thing nobody notices until
    an auditor lines up two records.
    """
    return dt.datetime.now().astimezone().date()


def day_or_today(text: str) -> Day:
    """A date typed at the prompt, or today when nothing was typed."""
    return parse_day(text) if text else today()


def county_list(text: str) -> frozenset[str]:
    """A comma separated county list, tidied and with the blanks dropped."""
    return frozenset(" ".join(part.split()) for part in text.split(",") if part.strip())


def window_of(start: str, end: str) -> Window | None:
    """A daily window from two times, or nothing when neither was given."""
    if bool(start) != bool(end):
        raise click.BadParameter("a window needs both ends")
    if not start:
        return None
    return Window(parse_clock(start), parse_clock(end))


def length_or(text: str, fallback: Inches) -> Inches:
    """A length typed at the prompt, or a fallback when nothing was typed."""
    return parse_length(text) if text else fallback


def bytes_of(count: int) -> str:
    """A byte count in the units a clerk reads."""
    if count < 1024:
        return f"{count} B"
    if count < 1024 * 1024:
        return f"{count / 1024:.1f} kB"
    return f"{count / (1024 * 1024):.1f} MB"
