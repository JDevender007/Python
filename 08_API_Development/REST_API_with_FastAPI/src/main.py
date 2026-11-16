"""Command line front end for the retry lab."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from retries import (                                       # noqa: E402
    MAX_TRIES,
    SCENARIOS,
    Order,
    RetryError,
    Server,
    Store,
    audit,
    backoff_delays,
    legacy_post,
    offset_for,
    parse_order,
    post_with_key,
    problems,
    read_order,
    run_demo,
    script_for,
    start_for,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="retry-lab",
        description="Retry a POST with and without an idempotency key, and "
                    "count the orders each loop creates.")
    parser.add_argument("--order", default=None, metavar="PATH",
                        help="an order bundle (default: the bundled one)")
    parser.add_argument("--scenario", default=None,
                        help="run one scripted scenario instead of all five")
    parser.add_argument("--tries", default=3, type=int, metavar="N",
                        help=f"attempts per loop (default: 3, at most "
                             f"{MAX_TRIES})")
    parser.add_argument("--key", default="order-7f3a", metavar="KEY",
                        help="the idempotency key the keyed loop sends")
    parser.add_argument("--backoff", action="store_true",
                        help="print the waits for 1 to 5 tries")
    parser.add_argument("--audit", action="store_true",
                        help="print every check with its verdict")
    parser.add_argument("--json", default=None, metavar="PATH",
                        help="write the runs to PATH as JSON")
    parser.add_argument("--quiet", action="store_true", help="print nothing")
    parser.add_argument("--demo", action="store_true",
                        help="run the offline demonstration")
    return parser


def _run_json(run) -> dict:
    return {
        "mode": run.mode,
        "outcome": run.outcome,
        "order_id": run.order_id,
        "attempts": run.attempts(),
        "statuses": list(run.statuses()),
        "replies": [
            {"status": reply.status, "order_id": reply.order_id,
             "detail": reply.detail}
            for reply in run.replies
        ],
        "waited": run.waited,
        "rows": run.rows,
    }


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if args.demo:
        if args.quiet:
            with contextlib.redirect_stdout(io.StringIO()):
                return run_demo()
        return run_demo()

    try:
        order, token, now = read_order(args.order)
        names = ([args.scenario] if args.scenario is not None
                 else [name for name, _, _ in SCENARIOS])
        scripts = {name: script_for(name) for name in names}
        starts = {name: start_for(token, now, offset_for(name))
                  for name in names}
    except RetryError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if args.tries < 1 or args.tries > MAX_TRIES:
        print(f"error: a try count is between 1 and {MAX_TRIES}, got "
              f"{args.tries}", file=sys.stderr)
        return 2

    if args.backoff:
        if not args.quiet:
            for tries in range(1, MAX_TRIES + 1):
                print(f"  {tries} try/tries: {backoff_delays(tries)}")
        return 0

    runs: dict[str, tuple] = {}
    try:
        for name, script in scripts.items():
            legacy_server = Server(Store(), token, script)
            legacy = legacy_post(legacy_server, order, args.tries,
                                 starts[name])
            keyed_server = Server(Store(), token, script)
            keyed = post_with_key(keyed_server, order, args.key, args.tries,
                                  starts[name])
            runs[name] = (legacy, keyed)
    except RetryError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(f"  the order: {order.line()}")
        print(f"  {token.line()}")
        print(f"  {'scenario':<20} {'at':>3} {'mode':<7} {'attempts':>8} "
              f"{'outcome':<15} {'id':<5} {'rows':>4} {'waited':>6}  statuses")
        for name in scripts:
            for run in runs[name]:
                ident = "-" if run.order_id is None else str(run.order_id)
                statuses = " ".join(str(status) for status in run.statuses())
                print(f"  {name:<20} {starts[name]:>3} {run.mode:<7} "
                      f"{run.attempts():>8} {run.outcome:<15} {ident:<5} "
                      f"{run.rows:>4} {run.waited:>6}  {statuses}")
        legacy_rows = sum(pair[0].rows for pair in runs.values())
        keyed_rows = sum(pair[1].rows for pair in runs.values())
        print(f"  the legacy loop left {legacy_rows} row(s); the keyed loop "
              f"left {keyed_rows}")

    failed_checks = []
    checks = []
    if args.audit:
        checks = audit(runs, order, backoff_delays(MAX_TRIES), Store)
        print()
        for name, okay in checks:
            print(f"  {'PASS' if okay else 'FAIL'}  {name}")
        failed_checks = problems(checks)

    if args.json:
        destination = Path(args.json)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "order": {"quantity": order.quantity,
                      "unit_cents": order.unit_cents,
                      "total_cents": order.total_cents()},
            "token": {"issued": token.issued, "lifetime": token.lifetime,
                      "expires_at": token.expires_at()},
            "now": now,
            "tries": args.tries,
            "key": args.key,
            "runs": {name: {run.mode: _run_json(run) for run in pair}
                     for name, pair in runs.items()},
            "starts": starts,
            "backoff": {tries: list(backoff_delays(tries))
                        for tries in range(1, MAX_TRIES + 1)},
            "checks": [{"name": name, "ok": okay} for name, okay in checks],
        }
        destination.write_text(json.dumps(payload, indent=2) + "\n",
                               encoding="utf-8")
        if not args.quiet:
            print(f"  wrote the runs to {destination}")

    if failed_checks:
        print(f"  {len(failed_checks)} check(s) failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
