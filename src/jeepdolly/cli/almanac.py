"""Almanac commands: seasonal orders, embargoes and the holiday load."""

from __future__ import annotations

import click

from jeepdolly.almanac.embargo import Embargo
from jeepdolly.almanac.season import Season
from jeepdolly.cli.ask import county_list, window_of
from jeepdolly.cli.context import Session, office_of
from jeepdolly.report.layout import LEFT, RIGHT, banner, table
from jeepdolly.units.clock import DaySpan, parse_day

__all__ = ["almanac"]


@click.group()
def almanac() -> None:
    """Record the seasonal orders and the embargoes."""


@almanac.command("season")
@click.option("--code", required=True, help="The office's key for the order.")
@click.option("--first", required=True, help="First day the order is in force.")
@click.option("--last", required=True, help="Last day it is in force.")
@click.option("--percent", required=True, type=int, help="Percent of the usual limits.")
@click.option("--counties", required=True, help="Comma separated county list.")
@click.option("--note", default="", help="Anything worth recording.")
@click.pass_obj
def season(
    session: Session,
    code: str,
    first: str,
    last: str,
    percent: int,
    counties: str,
    note: str,
) -> None:
    """Put a frost law or a winter premium on the books."""
    with office_of(session) as office, office.writing():
        made = office.almanac.add_season(
            Season(
                code=code,  # type: ignore[arg-type]
                span=DaySpan(parse_day(first), parse_day(last)),
                percent=percent,
                counties=county_list(counties),
                note=note,
            )
        )
    click.echo(str(made))


@almanac.command("embargo")
@click.option("--code", required=True, help="The office's key for the order.")
@click.option("--first", required=True, help="First day movement is stopped.")
@click.option("--last", required=True, help="Last day it is stopped.")
@click.option("--reason", required=True, help="Why movement is stopped.")
@click.option("--from-time", default="", help="Start of a daily window, like 07:00.")
@click.option("--to-time", default="", help="End of that window.")
@click.option("--counties", default="", help="Comma separated list, or blank for statewide.")
@click.option("--weekends-only", is_flag=True, help="Only Saturdays and Sundays.")
@click.pass_obj
def embargo(
    session: Session,
    code: str,
    first: str,
    last: str,
    reason: str,
    from_time: str,
    to_time: str,
    counties: str,
    weekends_only: bool,
) -> None:
    """Stop movement over a span of days, or an hour of each of them."""
    window = window_of(from_time, to_time)
    with office_of(session) as office, office.writing():
        made = office.almanac.add_embargo(
            Embargo(
                code=code,  # type: ignore[arg-type]
                span=DaySpan(parse_day(first), parse_day(last)),
                reason=reason,
                window=window,
                counties=county_list(counties) or None,
                weekends_only=weekends_only,
            )
        )
    click.echo(str(made))


@almanac.command("holidays")
@click.argument("year", type=int)
@click.pass_obj
def holidays(session: Session, year: int) -> None:
    """Put a year of holiday embargoes on the books."""
    with office_of(session) as office, office.writing():
        written = office.almanac.load_holidays(year)
    if not written:
        click.echo(f"{year} was already on the books")
        return
    for one in written:
        click.echo(str(one))
    click.echo(f"{len(written)} holiday embargoes for {year}")


@almanac.command("list")
@click.pass_obj
def listing(session: Session) -> None:
    """List every seasonal order and every embargo."""
    with office_of(session) as office:
        seasons = office.almanac.seasons()
        embargoes = office.almanac.embargoes()
        lines: list[str] = []
        if seasons:
            lines.extend(banner("seasonal orders"))
            lines.extend(
                table(
                    ["code", "span", "percent", "counties"],
                    [
                        [str(s.code), str(s.span), str(s.percent), str(len(s.counties))]
                        for s in seasons
                    ],
                    aligns=[LEFT, LEFT, RIGHT, RIGHT],
                )
            )
        if embargoes:
            if lines:
                lines.append("")
            lines.extend(banner("embargoes"))
            lines.extend(
                table(
                    ["code", "span", "hours", "where", "reason"],
                    [
                        [
                            str(e.code),
                            str(e.span),
                            "all day" if e.window is None else str(e.window),
                            "statewide" if e.statewide else f"{len(e.counties or ())} counties",
                            e.reason,
                        ]
                        for e in embargoes
                    ],
                )
            )
    if not lines:
        click.echo("the almanac is empty")
        return
    for line in lines:
        click.echo(line)


@almanac.command("on")
@click.argument("day")
@click.option("--county", required=True, help="Which county to look at.")
@click.pass_obj
def on_day(session: Session, day: str, county: str) -> None:
    """Say what is in force in one county on one day."""
    with office_of(session) as office:
        wanted = parse_day(day)
        seasons = office.almanac.season_book().in_force(wanted, county)
        embargoes = office.almanac.embargo_book().on_day(wanted, county)
    if not seasons and not embargoes:
        click.echo("nothing in force")
        return
    for order in seasons:
        click.echo(f"season {order}")
    for stop in embargoes:
        click.echo(f"embargo {stop}")
