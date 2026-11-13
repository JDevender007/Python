"""Command line entry point for the password generator.

Usage
-----
    python src/main.py --demo                    # self-checking demo
    python src/main.py                           # one standard password
    python src/main.py --policy strong --count 5
    python src/main.py --check "CorrectHorse9!"  # score an existing password
    python src/main.py --length 20 --no-symbols --no-ambiguous
    python src/main.py --seed 42 --json out.json

Generated passwords go to stdout only; nothing is written to disk unless you
pass ``--json``, which records length and entropy rather than the secrets.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import random
import sys
from pathlib import Path

from passwords import (
    PasswordError,
    PasswordHistory,
    Policy,
    generate_unique,
    run_demo,
    strength,
)

BANNER = """
====================================
 PASSWORD GENERATOR
   policy, entropy, validation
====================================
"""

PROJECT = Path(__file__).resolve().parent.parent
DEFAULT_POLICIES = PROJECT / "data" / "policies.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate passwords from an explicit policy and report "
                    "their entropy (offline)")
    parser.add_argument("--demo", action="store_true",
                        help="run the bundled self-checking demo")
    parser.add_argument("--policy", default="standard",
                        help="named policy from data/policies.json")
    parser.add_argument("--policies", type=Path, default=None,
                        help="policies JSON (default: the bundled one)")
    parser.add_argument("--length", type=int, default=None,
                        help="override the policy length")
    parser.add_argument("--count", type=int, default=1,
                        help="how many passwords to generate")
    parser.add_argument("--no-symbols", action="store_true",
                        help="drop the symbol requirement")
    parser.add_argument("--no-ambiguous", action="store_true",
                        help="exclude O 0 o I l 1 | and similar")
    parser.add_argument("--seed", type=int, default=None,
                        help="reproducible run (omit for system randomness)")
    parser.add_argument("--check", metavar="PASSWORD", default=None,
                        help="score an existing password instead of generating")
    parser.add_argument("--json", type=Path, default=None,
                        help="write a summary (never the passwords)")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text output")
    return parser


def load_policies(path: Path | None) -> dict[str, Policy]:
    source = path or DEFAULT_POLICIES
    if not source.exists():
        raise PasswordError(f"file not found: {source}")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PasswordError(f"{source.name} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict) or not payload:
        raise PasswordError(f"{source.name} must map names to policies")
    policies: dict[str, Policy] = {}
    for name, settings in payload.items():
        policies[name] = Policy.from_dict(settings, name=name)
    return policies


def choose_policy(args, policies: dict[str, Policy]) -> Policy:
    if args.policy not in policies:
        raise PasswordError(
            f"unknown policy {args.policy!r} "
            f"(known: {', '.join(sorted(policies))})")
    policy = policies[args.policy]
    changes: dict[str, object] = {}
    if args.length is not None:
        changes["length"] = args.length
    if args.no_symbols and policy.min_symbols:
        changes["min_symbols"] = 0
    if args.no_ambiguous:
        changes["forbid_ambiguous"] = True
    if not changes:
        return policy
    return Policy(**{**policy.to_dict(), **changes})


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
        except PasswordError as exc:
            print(f"Error: {exc}", file=sys.stderr)
        return 0

    try:
        if args.check is not None:
            report = strength(args.check)
            payload = {"checked": True, **report}
        else:
            policies = load_policies(args.policies)
            policy = choose_policy(args, policies)
            rng = random.Random(args.seed) if args.seed is not None else None
            history = PasswordHistory(limit=max(10, args.count))
            generated = [generate_unique(policy, history, rng)
                         for _ in range(args.count)]
            payload = {
                "checked": False,
                "policy": policy.name,
                "length": policy.length,
                "pool_size": policy.pool_size,
                "entropy_bits": policy.entropy_bits,
                "label": policy.label,
                "passwords": generated,
            }
    except PasswordError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(BANNER)
        if payload["checked"]:
            print(f"  length {payload['length']}, "
                  f"pool {payload['pool_size']}, "
                  f"{payload['entropy_bits']} bits -> {payload['label']}")
            for warning in payload["warnings"]:
                print(f"  warning: {warning}")
        else:
            print(f"  policy {payload['policy']}: {payload['length']} chars, "
                  f"pool {payload['pool_size']}, "
                  f"{payload['entropy_bits']} bits -> {payload['label']}")
            for password in payload["passwords"]:
                print(f"  {password}")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        summary = {key: value for key, value in payload.items()
                   if key != "passwords"}
        summary["count"] = len(payload.get("passwords", []))
        args.json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"  wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
