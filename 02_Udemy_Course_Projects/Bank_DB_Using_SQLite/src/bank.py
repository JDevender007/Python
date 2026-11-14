"""A small bank built on SQLite: schema, ledger, atomic transfers, audit.

Three tables, one rule each:

    customers     one row per person, email UNIQUE
    accounts      one row per account, opening balance, FOREIGN KEY to customer
    transactions  the ledger: signed amounts in integer cents

The legacy version stored ``accounts.balance`` *and* wrote transactions, which
means the same fact lived in two places and could disagree with itself after a
failed transfer. Here the balance is **derived**:

    balance = opening + SUM(amount_cents)

so a stale balance is not a bug you have to avoid, it is a number that cannot
exist. Money is stored as integer cents for the same reason: 0.1 + 0.2 is not
0.3 in binary floating point, and a bank that rounds per row drifts.

A transfer is two ledger rows in one ``BEGIN IMMEDIATE`` transaction:

    transfer_out  -25000   on the source account
    transfer_in   +25000   on the destination account
    both rows share one ``ref`` so the pair can be audited

If the destination does not exist, the foreign key rejects the second row and
the whole transaction rolls back — the source is not debited. That is the
property the legacy three-script version could not offer: it opened a
connection per operation and committed whatever happened to succeed.

Fully offline: ``:memory:`` by default, a file path if you want one.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

ACCOUNT_TYPES = ("Savings", "Checking")
TRANSFER_OUT = "transfer_out"
TRANSFER_IN = "transfer_in"
DEPOSIT = "deposit"
WITHDRAWAL = "withdrawal"
KINDS = (DEPOSIT, WITHDRAWAL, TRANSFER_IN, TRANSFER_OUT)


class BankError(ValueError):
    """A database, account or amount that cannot be used."""


class InsufficientFunds(BankError):
    """A withdrawal or transfer larger than the balance."""


class NotFound(BankError):
    """A lookup found nothing."""


# --------------------------------------------------------------------------- #
# Money
# --------------------------------------------------------------------------- #
def to_cents(amount) -> int:
    """Convert a decimal amount to integer cents, refusing sub-cent precision."""
    if isinstance(amount, bool):
        raise BankError("amount must be a number, not a boolean")
    if isinstance(amount, str):
        text = amount.strip().replace(",", "")
        try:
            amount = float(text)
        except ValueError:
            raise BankError(f"amount {text!r} is not a number") from None
    if not isinstance(amount, (int, float)):
        raise BankError(f"amount {amount!r} is not a number")
    if amount != amount:
        raise BankError("amount must not be NaN")
    scaled = round(float(amount) * 100, 6)
    cents = int(round(scaled))
    if abs(scaled - cents) > 1e-6:
        raise BankError(f"amount {amount!r} has more than two decimals")
    return cents


def money(cents: int) -> str:
    """Format integer cents as a two-decimal string, sign preserved."""
    if not isinstance(cents, int) or isinstance(cents, bool):
        raise BankError("cents must be an integer")
    sign = "-" if cents < 0 else ""
    whole, part = divmod(abs(cents), 100)
    return f"{sign}{whole}.{part:02d}"


# --------------------------------------------------------------------------- #
# Schema
# --------------------------------------------------------------------------- #
SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    cust_id     INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    address     TEXT NOT NULL DEFAULT '',
    email       TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS accounts (
    acc_id      INTEGER PRIMARY KEY,
    cust_id     INTEGER NOT NULL REFERENCES customers(cust_id),
    acc_type    TEXT NOT NULL CHECK (acc_type IN ('Savings', 'Checking')),
    opening     INTEGER NOT NULL CHECK (opening >= 0)
);

CREATE TABLE IF NOT EXISTS transactions (
    trans_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    acc_id      INTEGER NOT NULL REFERENCES accounts(acc_id),
    kind        TEXT NOT NULL CHECK (kind IN
                    ('deposit', 'withdrawal', 'transfer_in', 'transfer_out')),
    amount      INTEGER NOT NULL,
    ref         TEXT,
    note        TEXT NOT NULL DEFAULT '',
    CHECK (kind <> 'deposit' OR amount > 0),
    CHECK (kind <> 'transfer_in' OR amount > 0),
    CHECK (kind <> 'withdrawal' OR amount < 0),
    CHECK (kind <> 'transfer_out' OR amount < 0),
    UNIQUE (ref, kind)
);

CREATE INDEX IF NOT EXISTS ix_transactions_acc ON transactions(acc_id);
CREATE INDEX IF NOT EXISTS ix_accounts_cust ON accounts(cust_id);
"""


def connect(path: str | Path = ":memory:") -> sqlite3.Connection:
    """Open a connection with foreign keys enforced and rows as mappings."""
    if isinstance(path, Path):
        path = str(path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA)
    connection.commit()


def open_database(path: str | Path = ":memory:",
                  seed: bool = True) -> sqlite3.Connection:
    connection = connect(path)
    create_schema(connection)
    if seed:
        load_seed(connection)
    return connection


# --------------------------------------------------------------------------- #
# Seed data
# --------------------------------------------------------------------------- #
CUSTOMERS = (
    (110, "Anil", "Mumbai", "anil@gmail.com"),
    (111, "Smith", "Delhi", "smith@gmail.com"),
    (112, "Ramesh", "Mumbai", "ramesh@gmail.com"),
    (113, "Khan", "Delhi", "khan@gmail.com"),
)

ACCOUNTS = (
    # acc_id, cust_id, type, opening in cents
    (101, 110, "Savings", 250_000),
    (102, 111, "Checking", 120_050),
    (103, 112, "Savings", 150_000),
    (104, 113, "Checking", 170_000),
)

HISTORY = (
    # acc_id, kind, amount in cents, note
    (101, DEPOSIT, 50_000, "payroll"),
    (102, WITHDRAWAL, -30_000, "rent"),
    (103, DEPOSIT, 80_000, "freelance"),
    (104, WITHDRAWAL, -20_000, "groceries"),
)


def load_seed(connection: sqlite3.Connection) -> None:
    """Insert the four customers, four accounts and four history rows.

    Customers and accounts are keyed, so ``INSERT OR IGNORE`` makes them
    idempotent. Ledger rows are not keyed — a second call would double every
    balance — so the history is only written into an empty ledger.
    """
    connection.executemany(
        "INSERT OR IGNORE INTO customers (cust_id, name, address, email) "
        "VALUES (?, ?, ?, ?)", CUSTOMERS)
    connection.executemany(
        "INSERT OR IGNORE INTO accounts (acc_id, cust_id, acc_type, opening) "
        "VALUES (?, ?, ?, ?)", ACCOUNTS)
    already = connection.execute(
        "SELECT COUNT(*) FROM transactions").fetchone()[0]
    if not already:
        for acc_id, kind, amount, note in HISTORY:
            connection.execute(
                "INSERT INTO transactions (acc_id, kind, amount, note) "
                "VALUES (?, ?, ?, ?)", (acc_id, kind, amount, note))
    connection.commit()


# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #
def balance(connection: sqlite3.Connection, acc_id: int) -> int:
    """Opening plus every ledger row, in cents."""
    row = connection.execute(
        "SELECT a.opening + COALESCE(SUM(t.amount), 0) AS total "
        "FROM accounts a LEFT JOIN transactions t ON t.acc_id = a.acc_id "
        "WHERE a.acc_id = ? GROUP BY a.acc_id", (acc_id,)).fetchone()
    if row is None:
        raise NotFound(f"no account with id {acc_id}")
    return int(row["total"])


def accounts(connection: sqlite3.Connection) -> list[dict]:
    rows = connection.execute(
        "SELECT a.acc_id, c.name, a.acc_type, a.opening, "
        "       a.opening + COALESCE(SUM(t.amount), 0) AS balance "
        "FROM accounts a "
        "JOIN customers c ON c.cust_id = a.cust_id "
        "LEFT JOIN transactions t ON t.acc_id = a.acc_id "
        "GROUP BY a.acc_id ORDER BY a.acc_id").fetchall()
    return [{"acc_id": row["acc_id"], "name": row["name"],
             "acc_type": row["acc_type"], "opening": row["opening"],
             "balance": int(row["balance"])} for row in rows]


def customers(connection: sqlite3.Connection) -> list[dict]:
    rows = connection.execute(
        "SELECT cust_id, name, address, email FROM customers "
        "ORDER BY cust_id").fetchall()
    return [dict(row) for row in rows]


def account_of(connection: sqlite3.Connection, acc_id: int) -> dict:
    row = connection.execute(
        "SELECT a.acc_id, a.cust_id, a.acc_type, c.name, c.email "
        "FROM accounts a JOIN customers c ON c.cust_id = a.cust_id "
        "WHERE a.acc_id = ?", (acc_id,)).fetchone()
    if row is None:
        raise NotFound(f"no account with id {acc_id}")
    return dict(row)


def ledger(connection: sqlite3.Connection, acc_id: int) -> list[dict]:
    """Every row for one account, oldest first, with a running balance."""
    account_of(connection, acc_id)                      # existence check
    opening = int(connection.execute(
        "SELECT opening FROM accounts WHERE acc_id = ?",
        (acc_id,)).fetchone()["opening"])
    running = opening
    rows: list[dict] = []
    for row in connection.execute(
            "SELECT trans_id, kind, amount, ref, note FROM transactions "
            "WHERE acc_id = ? ORDER BY trans_id", (acc_id,)):
        running += int(row["amount"])
        rows.append({"trans_id": row["trans_id"], "kind": row["kind"],
                     "amount": int(row["amount"]), "ref": row["ref"],
                     "note": row["note"], "running": running})
    return rows


def total_assets(connection: sqlite3.Connection) -> int:
    return sum(entry["balance"] for entry in accounts(connection))


def transactions(connection: sqlite3.Connection) -> list[dict]:
    rows = connection.execute(
        "SELECT trans_id, acc_id, kind, amount, ref, note FROM transactions "
        "ORDER BY trans_id").fetchall()
    return [dict(row) for row in rows]


# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #
def deposit(connection: sqlite3.Connection, acc_id: int, amount,
            note: str = "") -> int:
    cents = to_cents(amount)
    if cents <= 0:
        raise BankError(f"deposit must be positive, got {money(cents)}")
    account_of(connection, acc_id)
    cursor = connection.execute(
        "INSERT INTO transactions (acc_id, kind, amount, note) "
        "VALUES (?, ?, ?, ?)", (acc_id, DEPOSIT, cents, note))
    connection.commit()
    return int(cursor.lastrowid)


def withdraw(connection: sqlite3.Connection, acc_id: int, amount,
             note: str = "") -> int:
    cents = to_cents(amount)
    if cents <= 0:
        raise BankError(f"withdrawal must be positive, got {money(cents)}")
    available = balance(connection, acc_id)
    if cents > available:
        raise InsufficientFunds(
            f"account {acc_id} has {money(available)}, "
            f"cannot withdraw {money(cents)}")
    cursor = connection.execute(
        "INSERT INTO transactions (acc_id, kind, amount, note) "
        "VALUES (?, ?, ?, ?)", (acc_id, WITHDRAWAL, -cents, note))
    connection.commit()
    return int(cursor.lastrowid)


def next_ref(connection: sqlite3.Connection) -> str:
    """The smallest ``TR-nnn`` not already used by a transfer."""
    used = {row[0] for row in connection.execute(
        "SELECT DISTINCT ref FROM transactions WHERE ref IS NOT NULL")}
    number = 1
    while f"TR-{number:03d}" in used:
        number += 1
    return f"TR-{number:03d}"


def transfer(connection: sqlite3.Connection, source: int, target: int,
             amount, note: str = "") -> str:
    """Move money between accounts atomically. Returns the shared ref."""
    cents = to_cents(amount)
    if cents <= 0:
        raise BankError(f"transfer must be positive, got {money(cents)}")
    if source == target:
        raise BankError("cannot transfer to the same account")
    available = balance(connection, source)
    if cents > available:
        raise InsufficientFunds(
            f"account {source} has {money(available)}, "
            f"cannot transfer {money(cents)}")
    account_of(connection, target)              # fail before writing anything
    ref = next_ref(connection)
    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute(
            "INSERT INTO transactions (acc_id, kind, amount, ref, note) "
            "VALUES (?, ?, ?, ?, ?)",
            (source, TRANSFER_OUT, -cents, ref, note))
        connection.execute(
            "INSERT INTO transactions (acc_id, kind, amount, ref, note) "
            "VALUES (?, ?, ?, ?, ?)",
            (target, TRANSFER_IN, cents, ref, note))
        connection.commit()
    except sqlite3.DatabaseError as exc:
        connection.rollback()
        raise BankError(f"transfer {ref} rolled back: {exc}") from exc
    return ref


# --------------------------------------------------------------------------- #
# Audit
# --------------------------------------------------------------------------- #
def audit(connection: sqlite3.Connection) -> list[str]:
    """Every invariant that can be checked from the data alone.

    An empty list means the bank is consistent. Each finding names the rule,
    not just that something is wrong.
    """
    problems: list[str] = []

    for row in connection.execute("PRAGMA foreign_key_check"):
        problems.append(
            f"foreign key: table {row[0]} row {row[1]} references a missing "
            f"row in {row[2]}")

    for acc_id, total in connection.execute(
            "SELECT acc_id, opening + COALESCE(SUM(amount), 0) "
            "FROM accounts LEFT JOIN transactions USING (acc_id) "
            "GROUP BY acc_id"):
        if int(total) < 0:
            problems.append(
                f"negative balance: account {acc_id} holds {money(int(total))}")

    for ref, total, count in connection.execute(
            "SELECT ref, SUM(amount), COUNT(*) FROM transactions "
            "WHERE ref IS NOT NULL GROUP BY ref"):
        if int(count) != 2:
            problems.append(
                f"transfer {ref} has {count} leg(s), expected 2")
        if int(total) != 0:
            problems.append(
                f"transfer {ref} does not net to zero: {money(int(total))}")

    for kind, expected_sign, label in ((TRANSFER_IN, 1, "positive"),
                                       (TRANSFER_OUT, -1, "negative"),
                                       (DEPOSIT, 1, "positive"),
                                       (WITHDRAWAL, -1, "negative")):
        for row in connection.execute(
                "SELECT trans_id, amount FROM transactions "
                "WHERE kind = ? AND amount * ? <= 0", (kind, expected_sign)):
            problems.append(
                f"transaction {row['trans_id']} is a {kind} but not {label}")

    if connection.execute(
            "SELECT 1 FROM transactions WHERE ref IS NULL "
            "AND kind IN (?, ?) LIMIT 1",
            (TRANSFER_IN, TRANSFER_OUT)).fetchone():
        problems.append("a transfer leg has no ref, so it cannot be paired")

    return problems


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def run_demo() -> int:
    print("=" * 70)
    print(" BANK DB - SQLite schema, derived balances, atomic transfers")
    print("=" * 70)

    connection = open_database()

    # 1. the schema and the seed are in place, with foreign keys enforced
    assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    names = [row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    assert names == ["accounts", "customers", "transactions"], names
    assert len(customers(connection)) == 4
    assert len(accounts(connection)) == 4
    print(f"  tables {names}; 4 customers, 4 accounts")

    # 2. balances are derived from the ledger, not stored
    expected = {101: 300_000, 102: 90_050, 103: 230_000, 104: 150_000}
    actual = {entry["acc_id"]: entry["balance"] for entry in accounts(connection)}
    assert actual == expected, actual
    assert [money(value) for value in actual.values()] == \
        ["3000.00", "900.50", "2300.00", "1500.00"]
    assert total_assets(connection) == 770_050
    print(f"  balances {[money(v) for v in actual.values()]}; "
          f"total {money(total_assets(connection))}")

    # 3. money is integer cents, and sub-cent input is refused
    assert to_cents("250.00") == 25_000
    assert to_cents(12.5) == 1_250
    for bad, needle in ((0.001, "more than two decimals"),
                        ("12x", "is not a number"),
                        (float("nan"), "NaN")):
        try:
            to_cents(bad)
        except BankError as exc:
            assert needle in str(exc), (bad, str(exc))
        else:
            raise AssertionError(f"{bad!r} should have been rejected")
    assert money(-5) == "-0.05" and money(0) == "0.00"

    # 4. deposit and withdrawal both move the derived balance
    deposit(connection, 101, "500.00", "bonus")
    assert balance(connection, 101) == 350_000
    withdraw(connection, 101, "200.00", "fuel")
    assert balance(connection, 101) == 330_000
    print(f"  after deposit 500 and withdrawal 200, 101 holds "
          f"{money(balance(connection, 101))}")

    # 5. negative control: an overdraft is refused and nothing is written
    rows_before = len(transactions(connection))
    try:
        withdraw(connection, 102, "1000.00")
    except InsufficientFunds as exc:
        assert "has 900.50" in str(exc)
    else:
        raise AssertionError("overdraft should be refused")
    assert len(transactions(connection)) == rows_before
    assert balance(connection, 102) == 90_050

    # 6. a transfer writes two legs under one ref and conserves the total
    before_total = total_assets(connection)
    ref = transfer(connection, 101, 102, "250.00", "split bill")
    assert ref == "TR-001", ref
    assert balance(connection, 101) == 305_000
    assert balance(connection, 102) == 115_050
    assert total_assets(connection) == before_total
    legs = connection.execute(
        "SELECT kind, amount FROM transactions WHERE ref = ? "
        "ORDER BY acc_id", (ref,)).fetchall()
    assert [(row["kind"], row["amount"]) for row in legs] == \
        [(TRANSFER_OUT, -25_000), (TRANSFER_IN, 25_000)]
    print(f"  transfer {ref}: 101 -> 102 250.00, total unchanged at "
          f"{money(before_total)}")

    # 7. a transfer larger than the balance touches neither account
    snapshot = {entry["acc_id"]: entry["balance"]
                for entry in accounts(connection)}
    count = len(transactions(connection))
    try:
        transfer(connection, 104, 101, "9999.00")
    except InsufficientFunds as exc:
        assert "cannot transfer" in str(exc)
    else:
        raise AssertionError("oversized transfer should be refused")
    assert len(transactions(connection)) == count
    assert {entry["acc_id"]: entry["balance"]
            for entry in accounts(connection)} == snapshot

    # 8. a missing destination rolls the first leg back: no orphan row
    count = len(transactions(connection))
    try:
        transfer(connection, 101, 999, "10.00")
    except NotFound as exc:
        assert "no account with id 999" in str(exc)
    else:
        raise AssertionError("missing destination should be refused")
    assert len(transactions(connection)) == count
    assert connection.execute(
        "SELECT COUNT(*) FROM transactions WHERE ref IS NULL "
        "AND kind = 'transfer_out'").fetchone()[0] == 0

    # 9. the ledger's running balance ends at the derived balance
    rows = ledger(connection, 101)
    assert [row["kind"] for row in rows] == \
        [DEPOSIT, DEPOSIT, WITHDRAWAL, TRANSFER_OUT]
    assert [row["running"] for row in rows] == \
        [300_000, 350_000, 330_000, 305_000]
    assert rows[-1]["running"] == balance(connection, 101)
    print(f"  ledger for 101: {len(rows)} rows, running "
          f"{money(rows[-1]['running'])}")

    # 10. a duplicate email is a UNIQUE violation, caught as a bank error
    try:
        connection.execute(
            "INSERT INTO customers (cust_id, name, email) "
            "VALUES (114, 'Copy', 'anil@gmail.com')")
    except sqlite3.IntegrityError as exc:
        assert "UNIQUE" in str(exc)
        connection.rollback()
    else:
        raise AssertionError("duplicate email should be rejected")

    # 11. a CHECK constraint refuses a positive withdrawal
    try:
        connection.execute(
            "INSERT INTO transactions (acc_id, kind, amount) "
            "VALUES (101, 'withdrawal', 500)")
    except sqlite3.IntegrityError as exc:
        assert "CHECK" in str(exc)
        connection.rollback()
    else:
        raise AssertionError("positive withdrawal should be rejected")

    # 12. the audit is clean, then a deliberately unbalanced leg is caught
    assert audit(connection) == [], audit(connection)
    connection.execute(
        "INSERT INTO transactions (acc_id, kind, amount, ref) "
        "VALUES (101, 'transfer_out', -1000, 'TR-999')")
    connection.commit()
    problems = audit(connection)
    assert any("TR-999" in problem and "expected 2" in problem
               for problem in problems), problems
    connection.execute("DELETE FROM transactions WHERE ref = 'TR-999'")
    connection.commit()
    assert audit(connection) == []
    print(f"  audit clean; a planted orphan leg was reported and removed")

    # 13. a file-backed database survives a reopen
    with tempfile.TemporaryDirectory(prefix="bank-") as folder:
        path = Path(folder) / "bank.db"
        first = open_database(path)
        transfer(first, 103, 104, "100.00")
        first.close()
        again = open_database(path, seed=False)
        assert balance(again, 103) == 220_000
        assert balance(again, 104) == 160_000
        assert audit(again) == []
        again.close()

    # 14. two fresh in-memory banks are identical
    assert accounts(open_database()) == accounts(open_database())

    connection.close()
    print()
    print("Cross-checks OK: 3 tables with enforced foreign keys, 4 customers "
          "and 4 derived balances totalling 7700.50, integer cents with "
          "sub-cent input refused, deposit/withdrawal moving the balance, an "
          "overdraft refused with no row written, a 2-leg transfer under one "
          "ref conserving the total, an oversized transfer touching neither "
          "account, a missing destination rolled back with no orphan, a "
          "running ledger matching the balance, UNIQUE email and CHECK sign "
          "constraints, a clean audit that catches a planted orphan leg, and "
          "a file database surviving reopen")
    print("\nDemo completed successfully.")
    return 0
