"""Reading and writing carrier accounts.

Entries are append only. There is no update and no delete, and a mistake is
corrected by posting an adjustment against it rather than by editing it away.
That is not fastidiousness: the account is what the office bills from, and a
carrier who is told their balance moved with no entry to explain it will ask,
and there has to be an answer.

The sequence number is per carrier and is handed out by the store rather than by
the caller, which is the only way two clerks posting at the same moment cannot
both take number fourteen.
"""

from __future__ import annotations

import sqlite3

from jeepdolly.billing.account import DEFAULT_FLOOR, Account, Entry, EntryKind
from jeepdolly.errors import NotFoundError
from jeepdolly.ids.reference import Code, code
from jeepdolly.store.sqlite import maybe_one, rows, scalar
from jeepdolly.units.clock import Day, format_day, parse_day
from jeepdolly.units.money import Money, cents

__all__ = ["AccountStore", "entry_from_row"]


def entry_from_row(row: sqlite3.Row) -> Entry:
    """Build an entry out of one row."""
    return Entry(
        day=parse_day(row["day"]),
        sequence=int(row["sequence"]),
        carrier=Code(row["carrier_code"]),
        kind=EntryKind(row["kind"]),
        amount=cents(int(row["amount"])),
        reference=row["reference"],
        note=row["note"],
    )


class AccountStore:
    """Every carrier's entries and terms."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def _known(self, carrier: str) -> Code:
        wanted = code(str(carrier))
        found = maybe_one(
            self.connection, "SELECT 1 FROM carrier WHERE code = ?", (str(wanted),)
        )
        if found is None:
            raise NotFoundError("carrier", str(wanted))
        return wanted

    def next_sequence(self, carrier: str) -> int:
        """The number the next entry on this account will take."""
        wanted = self._known(carrier)
        highest = scalar(
            self.connection,
            "SELECT max(sequence) FROM account_entry WHERE carrier_code = ?",
            (str(wanted),),
        )
        return 1 if highest is None else int(highest) + 1

    def set_floor(self, carrier: str, floor: Money) -> Money:
        """Set how far into the red this carrier may go."""
        wanted = self._known(carrier)
        self.connection.execute(
            "INSERT INTO account_terms (carrier_code, floor) VALUES (?, ?)"
            " ON CONFLICT (carrier_code) DO UPDATE SET floor = excluded.floor",
            (str(wanted), int(floor)),
        )
        return floor

    def floor_of(self, carrier: str) -> Money:
        """This carrier's credit floor, or the office's standing one."""
        wanted = self._known(carrier)
        found = scalar(
            self.connection,
            "SELECT floor FROM account_terms WHERE carrier_code = ?",
            (str(wanted),),
        )
        return DEFAULT_FLOOR if found is None else cents(int(found))

    def post(
        self,
        carrier: str,
        day: Day,
        kind: EntryKind,
        amount: Money,
        reference: str = "",
        note: str = "",
    ) -> Entry:
        """Write one entry, taking the next sequence number."""
        wanted = self._known(carrier)
        entry = Entry(
            day=day,
            sequence=self.next_sequence(str(wanted)),
            carrier=wanted,
            kind=EntryKind(kind),
            amount=amount,
            reference=reference,
            note=note,
        )
        self.connection.execute(
            "INSERT INTO account_entry (carrier_code, sequence, day, kind, amount,"
            " reference, note) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(entry.carrier),
                entry.sequence,
                format_day(entry.day),
                str(entry.kind),
                int(entry.amount),
                entry.reference,
                entry.note,
            ),
        )
        return entry

    def charge(self, carrier: str, day: Day, amount: Money, permit: str) -> Entry:
        """Charge a permit to an account, refusing to go past the floor."""
        account = self.account(carrier)
        account.check(amount)
        return self.post(carrier, day, EntryKind.CHARGE, amount, reference=permit)

    def deposit(self, carrier: str, day: Day, amount: Money, note: str = "") -> Entry:
        """Take money onto an account."""
        return self.post(carrier, day, EntryKind.DEPOSIT, amount, note=note)

    def entries(self, carrier: str) -> list[Entry]:
        """Every entry on one account, oldest first."""
        wanted = self._known(carrier)
        return [
            entry_from_row(row)
            for row in rows(
                self.connection,
                "SELECT * FROM account_entry WHERE carrier_code = ? ORDER BY day, sequence",
                (str(wanted),),
            )
        ]

    def account(self, carrier: str) -> Account:
        """One carrier's account, built from its entries and its terms."""
        wanted = self._known(carrier)
        return Account(
            carrier=wanted,
            entries=tuple(self.entries(str(wanted))),
            floor=self.floor_of(str(wanted)),
        )

    def balance(self, carrier: str) -> Money:
        """What one carrier's balance stands at."""
        return self.account(carrier).balance

    def owing(self) -> list[tuple[Code, Money]]:
        """Every carrier with a negative balance, worst first."""
        out: list[tuple[Code, Money]] = []
        for row in rows(self.connection, "SELECT code FROM carrier ORDER BY code"):
            balance = self.balance(row["code"])
            if int(balance) < 0:
                out.append((Code(row["code"]), balance))
        return sorted(out, key=lambda pair: (int(pair[1]), str(pair[0])))

    def count(self) -> int:
        """How many entries are on file across every account."""
        return int(scalar(self.connection, "SELECT count(*) FROM account_entry") or 0)

    def __len__(self) -> int:
        return self.count()
