"""Tests for Bank_DB_Using_SQLite: schema, money, ledger, transfers, audit."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import bank                                              # noqa: E402
import main as cli                                       # noqa: E402
from bank import (                                       # noqa: E402
    ACCOUNT_TYPES,
    DEPOSIT,
    TRANSFER_IN,
    TRANSFER_OUT,
    WITHDRAWAL,
    BankError,
    InsufficientFunds,
    NotFound,
    account_of,
    accounts,
    audit,
    balance,
    connect,
    create_schema,
    customers,
    deposit,
    ledger,
    load_seed,
    money,
    next_ref,
    open_database,
    run_demo,
    to_cents,
    total_assets,
    transactions,
    transfer,
    withdraw,
)


@pytest.fixture()
def db():
    connection = open_database()
    yield connection
    connection.close()


# --------------------------------------------------------------------------- #
# Money
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("amount, cents", [
    (0, 0), (1, 100), (12.5, 1250), ("250.00", 25000), ("1,234.56", 123456),
    (-3.25, -325), (0.01, 1), ("0.10", 10),
])
def test_to_cents_converts(amount, cents):
    assert to_cents(amount) == cents


def test_to_cents_rejects_sub_cent_precision():
    with pytest.raises(BankError, match="more than two decimals"):
        to_cents(0.001)


def test_to_cents_rejects_text_that_is_not_a_number():
    with pytest.raises(BankError, match="is not a number"):
        to_cents("twelve")


def test_to_cents_rejects_nan():
    with pytest.raises(BankError, match="NaN"):
        to_cents(float("nan"))


def test_to_cents_rejects_booleans():
    with pytest.raises(BankError, match="not a boolean"):
        to_cents(True)


def test_to_cents_rejects_none():
    with pytest.raises(BankError, match="is not a number"):
        to_cents(None)


def test_to_cents_avoids_float_noise():
    # 0.1 + 0.2 != 0.3 in binary floating point
    assert to_cents(0.1) + to_cents(0.2) == to_cents(0.3)


@pytest.mark.parametrize("cents, text", [
    (0, "0.00"), (5, "0.05"), (100, "1.00"), (2550, "25.50"),
    (-325, "-3.25"), (123456, "1234.56"),
])
def test_money_formats(cents, text):
    assert money(cents) == text


def test_money_rejects_non_integer():
    with pytest.raises(BankError, match="cents must be an integer"):
        money(1.5)
    with pytest.raises(BankError, match="cents must be an integer"):
        money(True)


def test_money_round_trips_through_to_cents():
    for cents in (0, 1, 99, 100, 12345, -7):
        assert to_cents(money(cents)) == cents


# --------------------------------------------------------------------------- #
# Schema
# --------------------------------------------------------------------------- #
def test_foreign_keys_are_enabled(db):
    assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_schema_creates_three_tables(db):
    names = [row[0] for row in db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    assert names == ["accounts", "customers", "transactions"]


def test_schema_is_idempotent():
    connection = connect()
    create_schema(connection)
    create_schema(connection)
    assert len(customers(connection)) == 0
    connection.close()


def test_seed_loads_four_of_each(db):
    assert len(customers(db)) == 4
    assert len(accounts(db)) == 4
    assert len(transactions(db)) == 4


def test_seed_is_idempotent(db):
    load_seed(db)
    assert len(transactions(db)) == 4
    assert len(customers(db)) == 4


def test_seed_customers_are_ordered(db):
    assert [row["name"] for row in customers(db)] == \
        ["Anil", "Smith", "Ramesh", "Khan"]


def test_seed_accounts_carry_their_type(db):
    assert [row["acc_type"] for row in accounts(db)] == \
        ["Savings", "Checking", "Savings", "Checking"]


def test_account_types_are_documented():
    assert ACCOUNT_TYPES == ("Savings", "Checking")


def test_row_factory_returns_mappings(db):
    row = db.execute("SELECT * FROM customers WHERE cust_id = 110").fetchone()
    assert row["name"] == "Anil"


# --------------------------------------------------------------------------- #
# Derived balances
# --------------------------------------------------------------------------- #
def test_balances_derive_from_opening_and_ledger(db):
    assert {row["acc_id"]: row["balance"] for row in accounts(db)} == {
        101: 300_000, 102: 90_050, 103: 230_000, 104: 150_000}


def test_balance_of_one_account(db):
    assert balance(db, 101) == 300_000
    assert money(balance(db, 101)) == "3000.00"


def test_balance_of_a_missing_account(db):
    with pytest.raises(NotFound, match="no account with id 999"):
        balance(db, 999)


def test_total_assets_sums_every_account(db):
    assert total_assets(db) == 770_050


def test_balance_equals_opening_plus_transactions(db):
    for row in accounts(db):
        rows = db.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM transactions "
            "WHERE acc_id = ?", (row["acc_id"],)).fetchone()
        assert row["balance"] == row["opening"] + int(rows["total"])


def test_account_of_joins_the_customer(db):
    record = account_of(db, 102)
    assert record["name"] == "Smith"
    assert record["email"] == "smith@gmail.com"


def test_account_of_missing_account(db):
    with pytest.raises(NotFound):
        account_of(db, 42)


# --------------------------------------------------------------------------- #
# Deposits and withdrawals
# --------------------------------------------------------------------------- #
def test_deposit_increases_the_balance(db):
    deposit(db, 101, "500.00", "bonus")
    assert balance(db, 101) == 350_000


def test_deposit_records_the_note(db):
    trans_id = deposit(db, 101, "1.00", "coffee refund")
    row = db.execute("SELECT * FROM transactions WHERE trans_id = ?",
                     (trans_id,)).fetchone()
    assert row["note"] == "coffee refund"
    assert row["kind"] == DEPOSIT
    assert row["amount"] == 100


def test_deposit_rejects_non_positive_amounts(db):
    with pytest.raises(BankError, match="must be positive"):
        deposit(db, 101, "0")
    with pytest.raises(BankError, match="must be positive"):
        deposit(db, 101, "-5")


def test_deposit_to_a_missing_account(db):
    with pytest.raises(NotFound):
        deposit(db, 999, "5.00")


def test_withdrawal_decreases_the_balance(db):
    withdraw(db, 101, "200.00", "fuel")
    assert balance(db, 101) == 280_000


def test_withdrawal_records_a_negative_amount(db):
    trans_id = withdraw(db, 101, "1.50")
    row = db.execute("SELECT * FROM transactions WHERE trans_id = ?",
                     (trans_id,)).fetchone()
    assert row["kind"] == WITHDRAWAL
    assert row["amount"] == -150


def test_withdrawal_of_the_whole_balance_is_allowed(db):
    amount = money(balance(db, 102))
    withdraw(db, 102, amount)
    assert balance(db, 102) == 0


def test_overdraft_is_refused_and_writes_nothing(db):
    count = len(transactions(db))
    with pytest.raises(InsufficientFunds, match="has 900.50"):
        withdraw(db, 102, "1000.00")
    assert len(transactions(db)) == count
    assert balance(db, 102) == 90_050


def test_withdrawal_rejects_non_positive_amounts(db):
    with pytest.raises(BankError, match="must be positive"):
        withdraw(db, 101, "-1")


# --------------------------------------------------------------------------- #
# Transfers
# --------------------------------------------------------------------------- #
def test_transfer_moves_money(db):
    transfer(db, 101, 102, "250.00")
    assert balance(db, 101) == 275_000
    assert balance(db, 102) == 115_050


def test_transfer_writes_two_legs_under_one_ref(db):
    ref = transfer(db, 101, 102, "250.00")
    rows = db.execute("SELECT kind, amount FROM transactions WHERE ref = ? "
                      "ORDER BY acc_id", (ref,)).fetchall()
    assert [(row["kind"], row["amount"]) for row in rows] == \
        [(TRANSFER_OUT, -25_000), (TRANSFER_IN, 25_000)]


def test_transfer_refs_are_sequential(db):
    assert transfer(db, 101, 102, "10.00") == "TR-001"
    assert transfer(db, 101, 102, "10.00") == "TR-002"


def test_next_ref_skips_used_numbers(db):
    db.execute("INSERT INTO transactions (acc_id, kind, amount, ref) "
               "VALUES (101, 'transfer_out', -100, 'TR-001')")
    assert next_ref(db) == "TR-002"


def test_transfer_conserves_total_assets(db):
    before = total_assets(db)
    transfer(db, 103, 104, "123.45")
    assert total_assets(db) == before


def test_transfer_to_the_same_account_is_refused(db):
    with pytest.raises(BankError, match="same account"):
        transfer(db, 101, 101, "10.00")


def test_transfer_larger_than_the_balance_changes_nothing(db):
    snapshot = {row["acc_id"]: row["balance"] for row in accounts(db)}
    count = len(transactions(db))
    with pytest.raises(InsufficientFunds, match="cannot transfer"):
        transfer(db, 104, 101, "9999.00")
    assert len(transactions(db)) == count
    assert {row["acc_id"]: row["balance"] for row in accounts(db)} == snapshot


def test_transfer_to_a_missing_account_rolls_back(db):
    count = len(transactions(db))
    with pytest.raises(NotFound):
        transfer(db, 101, 999, "10.00")
    assert len(transactions(db)) == count
    assert balance(db, 101) == 300_000
    assert db.execute(
        "SELECT COUNT(*) FROM transactions WHERE ref IS NULL "
        "AND kind = 'transfer_out'").fetchone()[0] == 0


def test_transfer_rejects_non_positive_amounts(db):
    with pytest.raises(BankError, match="must be positive"):
        transfer(db, 101, 102, "0")


def test_transfer_can_empty_an_account(db):
    transfer(db, 102, 101, money(balance(db, 102)))
    assert balance(db, 102) == 0


# --------------------------------------------------------------------------- #
# Ledger
# --------------------------------------------------------------------------- #
def test_ledger_has_a_running_balance(db):
    rows = ledger(db, 101)
    assert [row["kind"] for row in rows] == [DEPOSIT]
    assert [row["running"] for row in rows] == [300_000]


def test_ledger_running_balance_after_activity(db):
    deposit(db, 101, "500.00")
    withdraw(db, 101, "200.00")
    transfer(db, 101, 102, "250.00")
    rows = ledger(db, 101)
    assert [row["kind"] for row in rows] == \
        [DEPOSIT, DEPOSIT, WITHDRAWAL, TRANSFER_OUT]
    assert [row["running"] for row in rows] == \
        [300_000, 350_000, 330_000, 305_000]


def test_ledger_starts_at_the_opening_balance(db):
    rows = ledger(db, 102)
    assert rows[0]["running"] == 120_050 - 30_000


def test_ledger_ends_at_the_derived_balance(db):
    transfer(db, 101, 102, "50.00")
    assert ledger(db, 101)[-1]["running"] == balance(db, 101)


def test_ledger_of_an_empty_account(db):
    db.execute("INSERT INTO accounts (acc_id, cust_id, acc_type, opening) "
               "VALUES (105, 110, 'Savings', 0)")
    assert ledger(db, 105) == []


def test_ledger_of_a_missing_account(db):
    with pytest.raises(NotFound):
        ledger(db, 999)


# --------------------------------------------------------------------------- #
# Constraints
# --------------------------------------------------------------------------- #
def test_duplicate_email_is_rejected(db):
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        db.execute("INSERT INTO customers (cust_id, name, email) "
                   "VALUES (114, 'Copy', 'anil@gmail.com')")


def test_unknown_account_type_is_rejected(db):
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        db.execute("INSERT INTO accounts (acc_id, cust_id, acc_type, opening) "
                   "VALUES (105, 110, 'Premium', 0)")


def test_negative_opening_balance_is_rejected(db):
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        db.execute("INSERT INTO accounts (acc_id, cust_id, acc_type, opening) "
                   "VALUES (105, 110, 'Savings', -1)")


def test_positive_withdrawal_is_rejected(db):
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        db.execute("INSERT INTO transactions (acc_id, kind, amount) "
                   "VALUES (101, 'withdrawal', 500)")


def test_negative_deposit_is_rejected(db):
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        db.execute("INSERT INTO transactions (acc_id, kind, amount) "
                   "VALUES (101, 'deposit', -500)")


def test_unknown_kind_is_rejected(db):
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        db.execute("INSERT INTO transactions (acc_id, kind, amount) "
                   "VALUES (101, 'interest', 500)")


def test_orphan_account_is_rejected(db):
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        db.execute("INSERT INTO accounts (acc_id, cust_id, acc_type, opening) "
                   "VALUES (105, 999, 'Savings', 0)")


def test_orphan_transaction_is_rejected(db):
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        db.execute("INSERT INTO transactions (acc_id, kind, amount) "
                   "VALUES (999, 'deposit', 500)")


def test_one_ref_can_hold_only_one_leg_of_each_kind(db):
    db.execute("INSERT INTO transactions (acc_id, kind, amount, ref) "
               "VALUES (101, 'transfer_out', -100, 'TR-500')")
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        db.execute("INSERT INTO transactions (acc_id, kind, amount, ref) "
                   "VALUES (102, 'transfer_out', -100, 'TR-500')")


def test_several_rows_may_have_no_ref(db):
    db.execute("INSERT INTO transactions (acc_id, kind, amount) "
               "VALUES (101, 'deposit', 100)")
    db.execute("INSERT INTO transactions (acc_id, kind, amount) "
               "VALUES (101, 'deposit', 100)")
    assert db.execute("SELECT COUNT(*) FROM transactions WHERE ref IS NULL"
                      ).fetchone()[0] == 6


# --------------------------------------------------------------------------- #
# Audit
# --------------------------------------------------------------------------- #
def test_fresh_bank_is_clean(db):
    assert audit(db) == []


def test_audit_accepts_a_transfer(db):
    transfer(db, 101, 102, "250.00")
    assert audit(db) == []


def test_audit_reports_an_unpaired_leg(db):
    db.execute("INSERT INTO transactions (acc_id, kind, amount, ref) "
               "VALUES (101, 'transfer_out', -1000, 'TR-999')")
    db.commit()
    problems = audit(db)
    assert any("TR-999" in p and "expected 2" in p for p in problems)


def test_audit_reports_a_transfer_that_does_not_net_to_zero(db):
    db.executemany("INSERT INTO transactions (acc_id, kind, amount, ref) "
                   "VALUES (?, ?, ?, 'TR-777')",
                   [(101, "transfer_out", -1000), (102, "transfer_in", 900)])
    db.commit()
    assert any("does not net to zero" in p for p in audit(db))


def test_audit_reports_a_negative_balance(db):
    db.execute("INSERT INTO transactions (acc_id, kind, amount) "
               "VALUES (104, 'withdrawal', -500000)")
    db.commit()
    assert any("negative balance" in p for p in audit(db))


def test_audit_reports_a_wrong_sign(db):
    # the CHECK constraints reject a wrong-sign row, so the audit's own sign
    # rule can only be exercised on a hand-built table without them
    relaxed = connect()
    relaxed.executescript(
        "CREATE TABLE accounts (acc_id INTEGER PRIMARY KEY, "
        "  cust_id INTEGER, acc_type TEXT, opening INTEGER NOT NULL);"
        "CREATE TABLE transactions (trans_id INTEGER PRIMARY KEY, "
        "  acc_id INTEGER NOT NULL, kind TEXT NOT NULL, "
        "  amount INTEGER NOT NULL, ref TEXT);"
        "INSERT INTO accounts VALUES (1, 1, 'Savings', 10000);"
        "INSERT INTO transactions VALUES (1, 1, 'deposit', -100, NULL);")
    relaxed.commit()
    problems = audit(relaxed)
    relaxed.close()
    assert any("not positive" in p for p in problems), problems


def test_audit_reports_a_transfer_leg_without_a_ref(db):
    db.execute("INSERT INTO transactions (acc_id, kind, amount) "
               "VALUES (101, 'transfer_out', -100)")
    db.commit()
    assert any("no ref" in p for p in audit(db))


def test_audit_reports_a_broken_foreign_key(db):
    db.execute("PRAGMA foreign_keys = OFF")
    db.execute("INSERT INTO transactions (acc_id, kind, amount) "
               "VALUES (999, 'deposit', 100)")
    db.commit()
    problems = audit(db)
    db.execute("DELETE FROM transactions WHERE acc_id = 999")
    db.commit()
    assert any("foreign key" in p for p in problems)


# --------------------------------------------------------------------------- #
# File-backed database
# --------------------------------------------------------------------------- #
def test_database_survives_a_reopen(tmp_path):
    path = tmp_path / "bank.db"
    first = open_database(path)
    transfer(first, 103, 104, "100.00")
    first.close()
    again = open_database(path, seed=False)
    assert balance(again, 103) == 220_000
    assert balance(again, 104) == 160_000
    assert audit(again) == []
    again.close()


def test_seed_false_opens_an_empty_bank(tmp_path):
    connection = open_database(tmp_path / "empty.db", seed=False)
    assert customers(connection) == []
    assert accounts(connection) == []
    connection.close()


# --------------------------------------------------------------------------- #
# Demo, determinism and CLI
# --------------------------------------------------------------------------- #
def test_demo_returns_zero(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out
    assert "Demo completed successfully." in out


def test_demo_is_deterministic(capsys):
    run_demo()
    first = capsys.readouterr().out
    run_demo()
    assert capsys.readouterr().out == first


def test_two_fresh_banks_are_identical():
    first = open_database()
    second = open_database()
    assert accounts(first) == accounts(second)
    first.close()
    second.close()


def test_cli_demo(capsys):
    assert cli.main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_demo_quiet(capsys):
    assert cli.main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_lists_accounts(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "3000.00" in out
    assert "total assets 7700.50" in out


def test_cli_lists_customers(capsys):
    assert cli.main(["--customers"]) == 0
    out = capsys.readouterr().out
    assert "Anil" in out and "khan@gmail.com" in out


def test_cli_ledger(capsys):
    assert cli.main(["--ledger", "101"]) == 0
    out = capsys.readouterr().out
    assert "ledger for account 101" in out
    assert "balance 3000.00" in out


def test_cli_audit_clean(capsys):
    assert cli.main(["--audit"]) == 0
    assert "audit clean" in capsys.readouterr().out


def test_cli_withdraw_overdraft_exits_two(capsys):
    assert cli.main(["--withdraw", "102", "1000.00"]) == 2
    assert "cannot withdraw" in capsys.readouterr().err


def test_cli_transfer(capsys):
    assert cli.main(["--transfer", "101", "102", "250.00"]) == 0
    out = capsys.readouterr().out
    assert "2750.00" in out
    assert "the requested change was applied" in out


def test_cli_deposit_to_missing_account_exits_two(capsys):
    assert cli.main(["--deposit", "999", "5.00"]) == 2
    assert "no account with id 999" in capsys.readouterr().err


def test_cli_json_accounts(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["total"] == 770050
    assert [row["acc_id"] for row in payload["accounts"]] == [101, 102, 103, 104]


def test_cli_json_audit(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--audit", "--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload == {"audit": [], "ok": True}


def test_cli_writes_to_a_file_database(tmp_path, capsys):
    path = tmp_path / "bank.db"
    assert cli.main(["--db", str(path), "--transfer", "101", "102", "10.00"]) == 0
    capsys.readouterr()
    connection = open_database(path, seed=False)
    assert balance(connection, 101) == 299_000
    connection.close()


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""
