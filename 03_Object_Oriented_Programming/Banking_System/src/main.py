"""Command line interface for the bank.

    python src/main.py --demo
    python src/main.py                      # every account, one line each
    python src/main.py --statement AC-0001
    python src/main.py --balance AC-0003
    python src/main.py --audit
    python src/main.py --deposit AC-0002:250.00
    python src/main.py --withdraw AC-0001:150.00
    python src/main.py --transfer AC-0001:AC-0003:250.00
    python src/main.py --legacy
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

from banking import (
    DATA_FILE,
    LEGACY_HEAD,
    Bank,
    BankingError,
    Money,
    MoneyError,
    load_bank,
    run_demo,
    save_bank,
)

BANNER = """
========================================
 LEDGER BANK
   accounts, transfers, an audit
========================================
"""

KINDS = ("savings", "current")


def _money(text: str) -> Money:
    return Money.from_str(text)


def _split(spec: str, parts: int, shape: str) -> list[str]:
    pieces = spec.split(":")
    if len(pieces) != parts or not all(piece.strip() for piece in pieces):
        raise BankingError(f"expected {shape}, got {spec!r}")
    return [piece.strip() for piece in pieces]


def _line(account) -> str:
    return (f"  {account.number:<8} {account.KIND:<8} {account.holder:<20.20} "
            f"{account.balance.format():>14}"
            + ("" if account.is_open else f"  closed {account.closed_on}"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="A bank whose balance is derived from its ledger.")
    parser.add_argument("--demo", action="store_true",
                        help="run the bundled self-checking demo")
    parser.add_argument("--file", type=Path, default=DATA_FILE,
                        help="bank file (default: data/bank.json)")
    parser.add_argument("--list", action="store_true",
                        help="one line per account (the default)")
    parser.add_argument("--balance", metavar="ACCOUNT",
                        help="show one balance")
    parser.add_argument("--statement", metavar="ACCOUNT",
                        help="print one ledger")
    parser.add_argument("--audit", action="store_true",
                        help="run the seven invariants")
    parser.add_argument("--open", metavar="KIND:HOLDER[:OPENING]",
                        help="open an account (kind: savings or current)")
    parser.add_argument("--deposit", metavar="ACCOUNT:AMOUNT",
                        help="deposit into an account")
    parser.add_argument("--withdraw", metavar="ACCOUNT:AMOUNT",
                        help="withdraw from an account")
    parser.add_argument("--transfer", metavar="FROM:TO:AMOUNT",
                        help="move money between two accounts")
    parser.add_argument("--date", metavar="YYYY-MM-DD",
                        help="the date to write on today's entries")
    parser.add_argument("--legacy", action="store_true",
                        help="show the two legacy defects the demo proves")
    parser.add_argument("--write", type=Path, metavar="PATH",
                        help="save the bank after the change")
    parser.add_argument("--json", type=Path, metavar="PATH",
                        help="write the result as JSON to PATH")
    parser.add_argument("--quiet", action="store_true",
                        help="write no standard output")
    args = parser.parse_args(argv)

    if args.demo:
        if args.quiet:
            with contextlib.redirect_stdout(io.StringIO()):
                run_demo()
        else:
            run_demo()
        return 0

    try:
        if args.legacy:
            payload = {
                "mode": "legacy",
                "stray": LEGACY_HEAD,
                "float_column": ["balance = Column(Float)",
                                 "account.balance += amount"],
                "note": "the stray assignment rebinds the builtin id()",
            }
            if not args.quiet:
                print(BANNER)
                print(f"  first line   {LEGACY_HEAD}")
                print("  money column balance = Column(Float)")
                print("  update       account.balance += amount")
                print(f"  note         {payload['note']}")
            if args.json:
                args.json.write_text(json.dumps(payload, indent=2),
                                     encoding="utf-8")
            return 0

        bank = load_bank(args.file)
        when = args.date or "2026-03-01"
        payload: dict = {"mode": "list", "bank": bank.name, "date": when}

        if args.balance:
            account = bank.get(args.balance)
            payload = {"mode": "balance", "number": account.number,
                       "holder": account.holder, "kind": account.KIND,
                       "cents": account.balance.cents,
                       "balance": account.balance.format(),
                       "entries": len(account)}
            if not args.quiet:
                print(BANNER)
                print(f"  {account.number}  {account.holder}")
                print(f"  balance {account.balance.format()} "
                      f"over {len(account)} entries")
        elif args.statement:
            account = bank.get(args.statement)
            lines = account.statement()
            payload = {"mode": "statement", "number": account.number,
                       "lines": lines, "cents": account.balance.cents}
            if not args.quiet:
                print(BANNER)
                for line in lines:
                    print(line)
        elif args.audit:
            checks = bank.audit()
            payload = {"mode": "audit",
                       "checks": [{"name": name, "passed": passed}
                                  for name, passed in checks],
                       "clean": all(passed for _, passed in checks)}
            if not args.quiet:
                print(BANNER)
                for name, passed in checks:
                    print(f"  {'PASS' if passed else 'FAIL'}  {name}")
                print(f"\n  {sum(1 for _, ok in checks if ok)}/{len(checks)} "
                      f"checks passed")
        elif args.open:
            pieces = args.open.split(":")
            if len(pieces) < 2:
                raise BankingError("expected KIND:HOLDER[:OPENING]")
            kind = pieces[0].strip().casefold()
            if kind not in KINDS:
                raise BankingError(f"{kind!r} is not one of {', '.join(KINDS)}")
            holder = ":".join(pieces[1:-1]).strip() if len(pieces) > 2 \
                else pieces[1].strip()
            opening = _money(pieces[-1]) if len(pieces) > 2 else Money.zero()
            account = bank.open(kind, holder, when, opening)
            payload = {"mode": "open", "number": account.number,
                       "kind": account.KIND, "holder": account.holder,
                       "cents": account.balance.cents}
            if not args.quiet:
                print(BANNER)
                print(f"  opened {account.number} for {account.holder} "
                      f"with {account.balance.format()}")
        elif args.deposit:
            number, amount = _split(args.deposit, 2, "ACCOUNT:AMOUNT")
            account = bank.get(number)
            entry = account.deposit(_money(amount), when, "deposit")
            payload = {"mode": "deposit", "number": account.number,
                       "cents": entry.amount.cents,
                       "balance": account.balance.format()}
            if not args.quiet:
                print(BANNER)
                print(f"  {entry.amount.format()} into {account.number}; "
                      f"balance {account.balance.format()}")
        elif args.withdraw:
            number, amount = _split(args.withdraw, 2, "ACCOUNT:AMOUNT")
            account = bank.get(number)
            rows = account.withdraw(_money(amount), when, "withdrawal")
            payload = {"mode": "withdraw", "number": account.number,
                       "rows": len(rows),
                       "balance": account.balance.format()}
            if not args.quiet:
                print(BANNER)
                print(f"  {len(rows)} row(s) written; balance "
                      f"{account.balance.format()}")
        elif args.transfer:
            source, destination, amount = _split(args.transfer, 3,
                                                 "FROM:TO:AMOUNT")
            out, incoming = bank.transfer(source, destination, _money(amount),
                                          when, "transfer")
            payload = {"mode": "transfer", "from": source, "to": destination,
                       "cents": out.amount.cents,
                       "reference": out.reference,
                       "balances": {source: bank.get(source).balance.format(),
                                    destination:
                                        bank.get(destination).balance.format()}}
            if not args.quiet:
                print(BANNER)
                print(f"  {out.amount.format()} {source} -> {destination} "
                      f"({out.reference})")
                print(f"  {source} now {bank.get(source).balance.format()}")
                print(f"  {destination} now "
                      f"{bank.get(destination).balance.format()}")
        else:
            accounts = bank.accounts
            payload = {"mode": "list",
                       "accounts": [{"number": account.number,
                                     "kind": account.KIND,
                                     "holder": account.holder,
                                     "cents": account.balance.cents,
                                     "open": account.is_open}
                                    for account in accounts],
                       "total": bank.total.format()}
            if not args.quiet:
                print(BANNER)
                for account in accounts:
                    print(_line(account))
                print(f"\n  {len(accounts)} accounts, total "
                      f"{bank.total.format()}")

        if args.write:
            save_bank(args.write, bank)
            payload["written"] = args.write.name
            if not args.quiet:
                print(f"\n  written to {payload['written']}")

        if args.json:
            args.json.write_text(json.dumps(payload, indent=2),
                                 encoding="utf-8")
        return 0
    except BankingError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
