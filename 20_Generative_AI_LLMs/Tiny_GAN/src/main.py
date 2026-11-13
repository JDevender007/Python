"""Command line entry point for the Tiny GAN.

Usage
-----
    python src/main.py --demo                      # bundled two moons
    python src/main.py --data data/moons.csv       # train on a CSV
    python src/main.py --data data/moons.csv --steps 600 --seed 3
    python src/main.py --demo --json run.json

Fully offline: a local CSV in, training report and generated points out.
No network, no downloads (the two-moons dataset ships in data/).
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
from pathlib import Path

from gan import (
    COVERAGE_RADIUS,
    DEFAULT_BATCH,
    DEFAULT_STEPS,
    LATENT_DIM,
    GanError,
    coverage,
    load_moons,
    mean_nearest_distance,
    mode_balance,
    run_demo,
    sample,
    standardize,
    train_gan,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("gan")

BANNER = """
========================================
 TINY GAN
   MLP generator + MLP discriminator
   two moons, CPU, offline
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train a tiny GAN on a 2-D CSV dataset")
    mode = parser.add_mutually_exclusive_group(required=False)
    mode.add_argument("--demo", action="store_true",
                      help="run the offline demo on the bundled dataset")
    mode.add_argument("--data", type=Path, default=None,
                      help="CSV with x,y,label columns")
    parser.add_argument("--steps", type=int, default=DEFAULT_STEPS,
                        help=f"training steps (default {DEFAULT_STEPS})")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH,
                        help=f"batch size (default {DEFAULT_BATCH})")
    parser.add_argument("--latent", type=int, default=LATENT_DIM,
                        help=f"noise dimension (default {LATENT_DIM})")
    parser.add_argument("--seed", type=int, default=0,
                        help="training seed (default 0)")
    parser.add_argument("--json", type=Path, default=None,
                        help="write the run summary as JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text report")
    return parser


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
        except GanError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        return 0

    if args.data is None:
        parser.error("one of the arguments --demo --data is required")

    # fast-fail: validate flags before loading the dataset
    if args.steps < 1:
        print(f"Error: steps must be >= 1, got {args.steps}", file=sys.stderr)
        return 2
    if args.latent < 1:
        print(f"Error: latent must be >= 1, got {args.latent}",
              file=sys.stderr)
        return 2
    if args.batch_size < 2:
        print(f"Error: batch-size must be >= 2, got {args.batch_size}",
              file=sys.stderr)
        return 2

    try:
        moons = load_moons(args.data)
        result = train_gan(moons, steps=args.steps, batch_size=args.batch_size,
                           latent_dim=args.latent, seed=args.seed)
    except GanError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    data, _, _ = standardize(moons.points)
    fake = sample(result, 1000, seed=args.seed + 1)
    report = {
        **result.to_dict(),
        "rows": moons.size,
        "coverage": round(coverage(data, fake, COVERAGE_RADIUS), 4),
        "nearest_distance": round(mean_nearest_distance(data, fake), 4),
        "mode_balance": mode_balance(data, moons.labels, fake),
    }

    if not args.quiet:
        print(BANNER)
        print(f"Dataset         : {moons.size} rows, "
              f"second-moon share {moons.balance():.3f}")
        print(f"Training        : {args.steps} steps, batch {args.batch_size}, "
              f"latent {args.latent}, seed {args.seed}")
        print(f"Discriminator   : loss {result.initial_d_loss:.3f} -> "
              f"{result.final_d_loss:.3f}")
        print(f"Generator       : loss {result.initial_g_loss:.3f} -> "
              f"{result.final_g_loss:.3f}")
        print(f"Coverage        : {report['coverage']:.1%}")
        print(f"Nearest real    : mean distance "
              f"{report['nearest_distance']:.3f}")
        print(f"Mode balance    : moon0 {report['mode_balance']['moon0']:.1%}, "
              f"moon1 {report['mode_balance']['moon1']:.1%}")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"\nWrote {args.json}")

    if not args.quiet:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
