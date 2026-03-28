"""Account commands: deposit, charge, statement."""

from __future__ import annotations

import click

from jeepdolly.billing.account import running
from jeepdolly.cli.ask import today
from jeepdolly.cli.context import Session, office_of
from jeepdolly.report.layout import LEFT, RIGHT, banner, pairs, table
from jeepdolly.units.clock import DaySpan, format_day, parse_day
from jeepdolly.units.money import format_money, parse_money

__all__ = ["account"]


@click.group()
def account() -> None:
    """Take money, charge permits and print statements."""


@account.command("deposit")
@click.argument("carrier")
@click.option("--amount", required=True, help="How much is being taken.")
@click.option("--on", default="", help="Day the money was taken.")
@click.option("--note", default="", help="Anything worth recording.")
@click.pass_obj
def deposit(session: Session, carrier: str, amount: str, on: str, note: str) -> None:
    """Take money onto a carrier's account."""
    with office_of(session) as office, office.writing():
        made = office.accounts.deposit(
            carrier, parse_day(on) if on else today(), parse_money(amount), note
        )
        balance = office.accounts.balance(carrier)
    click.echo(f"{made} balance {format_money(balance)}")


@account.command("charge")
@click.argument("carrier")
@click.option("--permit", required=True, help="Which permit is being charged.")
@click.option("--amount", default="", help="Override the permit's own fee.")
@click.option("--on", default="", help="Day the charge is posted.")
@click.pass_obj
def charge(session: Session, carrier: str, permit: str, amount: str, on: str) -> None:
    """Charge a permit to a carrier's account."""
    with office_of(session) as office, office.writing():
        owed = parse_money(amount) if amount else office.permits.get(permit).fee
        made = office.accounts.charge(carrier, parse_day(on) if on else today(), owed, permit)
        balance = office.accounts.balance(carrier)
    click.echo(f"{made} balance {format_money(balance)}")


@account.command("floor")
@click.argument("carrier")
@click.option("--amount", required=True, help="How far into the red this carrier may go.")
@click.pass_obj
def floor(session: Session, carrier: str, amount: str) -> None:
    """Set a carrier's credit floor."""
    with office_of(session) as office, office.writing():
        made = office.accounts.set_floor(carrier, parse_money(amount))
    click.echo(f"{carrier} floor {format_money(made)}")


@account.command("statement")
@click.argument("carrier")
@click.option("--first", default="", help="First day of the statement.")
@click.option("--last", default="", help="Last day of the statement.")
@click.pass_obj
def statement(session: Session, carrier: str, first: str, last: str) -> None:
    """Print a carrier's statement."""
    with office_of(session) as office:
        held = office.accounts.account(carrier)
        entries = list(held.entries)
        if first and last:
            entries = list(held.within(DaySpan(parse_day(first), parse_day(last))))
        lines = banner(f"statement for {held.carrier}")
        if not entries:
            lines.append("no entries")
        else:
            lines.extend(
                table(
                    ["day", "no", "kind", "reference", "amount", "balance"],
                    [
                        [
                            format_day(entry.day),
                            str(entry.sequence),
                            str(entry.kind),
                            entry.reference or entry.note or "-",
                            format_money(entry.signed),
                            format_money(balance),
                        ]
                        for entry, balance in running(entries)
                    ],
                    aligns=[LEFT, RIGHT, LEFT, LEFT, RIGHT, RIGHT],
                )
            )
        lines.append("")
        lines.extend(
            pairs(
                [
                    ("balance", format_money(held.balance)),
                    ("floor", format_money(held.floor)),
                    ("headroom", format_money(held.headroom)),
                ]
            )
        )
    for line in lines:
        click.echo(line)


@account.command("owing")
@click.pass_obj
def owing(session: Session) -> None:
    """List the carriers with a negative balance."""
    with office_of(session) as office:
        found = office.accounts.owing()
    if not found:
        click.echo("nobody owes anything")
        return
    for carrier, balance in found:
        click.echo(f"{carrier} {format_money(balance)}")
