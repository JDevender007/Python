"""Command line entry point for the number guessing game.

Usage
-----
    python src/main.py --demo                     # self-checking demo
    python src/main.py                            # bisect the secret 42
    python src/main.py --secret 73                # any secret in range
    python src/main.py --secret 73 --strategy linear
    python src/main.py --seed 7                   # seed decides the secret
    python src/main.py --low 1 --high 1000 --secret 999
    python src/main.py --json out.json --quiet

The game is never interactive: the secret is known, so the run is a
reproducible transcript of the solver's guesses and the feedback it got.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

from guessing import (
    CORRECT,
    Game,
    GuessingError,
    optimal_attempts,
    play_seeded,
    run_demo,
    solve,
    solve_linearly,
)

BANNER = """
====================================
 NUMBER GUESSING GAME
   bisection solver + statistics
====================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Play a deterministic number-guessing round with a "
                    "bisection solver (offline)")
    parser.add_argument("--demo", action="store_true",
                        help="run the bundled self-checking demo")
    parser.add_argument("--secret", type=int, default=42,
                        help="the number to find (default: 42)")
    parser.add_argument("--seed", type=int, default=None,
                        help="let the seed pick the secret instead of --secret")
    parser.add_argument("--low", type=int, default=1, help="lower bound")
    parser.add_argument("--high", type=int, default=100, help="upper bound")
    parser.add_argument("--strategy", choices=("binary", "linear"),
                        default="binary", help="how the solver guesses")
    parser.add_argument("--json", type=Path, default=None,
                        help="write the round as JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text output")
    return parser


def play(secret: int, low: int, high: int, strategy: str) -> Game:
    return solve_linearly(secret, low, high) if strategy == "linear" \
        else solve(secret, low, high)


def transcript(game: Game) -> list[dict]:
    """Replay the recorded guesses to recover the feedback for each one."""
    steps: list[dict] = []
    low, high = game.initial_low, game.initial_high
    for value in game.guesses:
        if value == game.secret:
            feedback = CORRECT
        elif value < game.secret:
            feedback = "low"
            low = max(low, value + 1)
        else:
            feedback = "high"
            high = min(high, value - 1)
        steps.append({"guess": value, "feedback": feedback,
                      "range": f"{low}..{high}"})
    return steps


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
        except GuessingError as exc:
            print(f"Error: {exc}", file=sys.stderr)
        return 0

    try:
        if args.seed is not None:
            round_ = play_seeded(args.seed, args.low, args.high)
            secret = round_["secret"]
            game = play(secret, args.low, args.high, args.strategy)
            seed = args.seed
        else:
            secret = args.secret
            game = play(secret, args.low, args.high, args.strategy)
            seed = None
        steps = transcript(game)
        payload = {
            "seed": seed,
            "secret": secret,
            "range": f"{args.low}..{args.high}",
            "strategy": args.strategy,
            "attempts": game.attempts,
            "solved": game.solved,
            "worst_case": optimal_attempts(args.low, args.high),
            "steps": steps,
        }
    except GuessingError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(BANNER)
        print(f"  secret {secret} in {args.low}..{args.high} "
              f"({args.strategy} strategy)")
        for step in steps:
            print(f"    guess {step['guess']:>6}  {step['feedback']:<8}"
                  f"range {step['range']}")
        print(f"\n  solved in {game.attempts} guess(es); "
              f"bisection worst case is {payload['worst_case']}")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"  wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
