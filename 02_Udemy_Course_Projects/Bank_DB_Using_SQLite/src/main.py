"""Command line entry point for the bank database.

Usage
-----
    python src/main.py --demo                        # self-checking demo
    python src/main.py                               # accounts and balances
    python src/main.py --customers
    python src/main.py --ledger 101
    python src/main.py --audit
    python src/main.py --transfer 101 102 250.00
    python src/main.py --db bank.db --deposit 101 50.00
    python src/main.py --json out.json --quiet

Without ``--db`` the bank is built in memory from the bundled seed and thrown
away when the process exits, so nothing on disk changes by accident.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sqlite3
import sys
from pathlib import Path

from bank import (
    BankError,
    InsufficientFunds,
    NotFound,
    accounts,
    audit,
    balance,
    customers,
    deposit,
    ledger,
    money,
    open_database,
    run_demo,
    total_assets,
    transactions,
    transfer,
    withdraw,
)

BANNER = """
====================================
 BANK DB (SQLite)
   ledger, derived balances, audit
====================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="A three-table bank with a derived balance and atomic "
                    "transfers (offline)")
    parser.add_argument("--demo", action="store_true",
                        help="run the bundled self-checking demo")
    parser.add_argument("--db", type=Path, default=None,
                        help="database file (default: in-memory seed)")
    parser.add_argument("--customers", action="store_true",
                        help="list customers instead of accounts")
    parser.add_argument("--ledger", type=int, metavar="ACC_ID", default=None,
                        help="print one account's ledger with a running total")
    parser.add_argument("--audit", action="store_true",
                        help="check every invariant and report findings")
    parser.add_argument("--deposit", nargs=2, metavar=("ACC_ID", "AMOUNT"),
                        default=None, help="add money")
    parser.add_argument("--withdraw", nargs=2, metavar=("ACC_ID", "AMOUNT"),
                        default=None, help="remove money, never below zero")
    parser.add_argument("--transfer", nargs=3,
                        metavar=("FROM", "TO", "AMOUNT"), default=None,
                        help="move money between two accounts atomically")
    parser.add_argument("--json", type=Path, default=None,
                        help="write the report as JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text output")
    return parser


def render_accounts(rows: list[dict]) -> str:
    lines = [f"  {'acc':>5}  {'name':<10}{'type':<10}{'opening':>10}"
             f"{'balance':>10}", "  " + "-" * 46]
    for row in rows:
        lines.append(f"  {row['acc_id']:>5}  {row['name']:<10}"
                     f"{row['acc_type']:<10}{money(row['opening']):>10}"
                     f"{money(row['balance']):>10}")
    return "\n".join(lines)


def render_ledger(acc_id: int, rows: list[dict]) -> str:
    lines = [f"  ledger for account {acc_id}",
             f"  {'id':>4}  {'kind':<13}{'amount':>10}{'running':>10}  note",
             "  " + "-" * 56]
    for row in rows:
        lines.append(f"  {row['trans_id']:>4}  {row['kind']:<13}"
                     f"{money(row['amount']):>10}{money(row['running']):>10}"
                     f"  {row['note']}")
    if not rows:
        lines.append("  (no transactions)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        if not args.quiet:
            print(BANNER)
        try:
            if args.quiet:
                with contextlib.redirect_stdout(io.StringIO()):
                    run_demo()
            else:
                run_demo()
        except (BankError, OSError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
        return 0

    try:
        connection = open_database(args.db) if args.db else open_database()
        changed = False
        if args.deposit:
            acc_id, amount = args.deposit
            deposit(connection, int(acc_id), amount)
            changed = True
        if args.withdraw:
            acc_id, amount = args.withdraw
            withdraw(connection, int(acc_id), amount)
            changed = True
        if args.transfer:
            source, target, amount = args.transfer
            transfer(connection, int(source), int(target), amount)
            changed = True

        if args.customers:
            payload = {"customers": customers(connection)}
        elif args.ledger is not None:
            payload = {"ledger": ledger(connection, args.ledger),
                       "balance": balance(connection, args.ledger)}
        elif args.audit:
            problems = audit(connection)
            payload = {"audit": problems, "ok": not problems}
        else:
            payload = {"accounts": accounts(connection),
                       "total": total_assets(connection),
                       "transactions": len(transactions(connection)),
                       "changed": changed}
    except (BankError, InsufficientFunds, NotFound,
            sqlite3.DatabaseError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(BANNER)
        if args.customers:
            for row in payload["customers"]:
                print(f"  {row['cust_id']:>4}  {row['name']:<10}"
                      f"{row['address']:<10}{row['email']}")
        elif args.ledger is not None:
            print(render_ledger(args.ledger, payload["ledger"]))
            print(f"  balance {money(payload['balance'])}")
        elif args.audit:
            if payload["ok"]:
                print("  audit clean: no findings")
            else:
                for problem in payload["audit"]:
                    print(f"  ! {problem}")
        else:
            print(render_accounts(payload["accounts"]))
            print(f"\n  total assets {money(payload['total'])}, "
                  f"{payload['transactions']} ledger row(s)")
            if payload["changed"]:
                print("  the requested change was applied")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"  wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
