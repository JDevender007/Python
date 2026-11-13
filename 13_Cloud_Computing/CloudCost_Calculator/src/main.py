"""Command line entry point for the Cloud Cost Calculator.

Usage
-----
    python src/main.py --demo                       # bundled sample infrastructure
    python src/main.py --config infra.json          # price your own config
    python src/main.py --config infra.json --json
    python src/main.py --config infra.json --compare
    python src/main.py --config infra.json --provider gcp --budget 300

Config format (JSON):

    {
      "provider": "aws",
      "hours_per_month": 730,
      "budget": 400,
      "resources": [
        {"type": "compute",   "instance": "t3.medium", "count": 3, "plan": "ondemand"},
        {"type": "database",  "instance": "db.m5.large", "count": 1},
        {"type": "storage",   "class": "gp3", "size_gb": 500},
        {"type": "bandwidth", "gb_out": 2000}
      ]
    }

Exit codes: 0 = within budget, 1 = over budget, 2 = usage/config error.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from cost_calculator import (
    CostError,
    calculate,
    demo_config,
    load_config,
    plan_comparison,
    render_report,
    run_demo,
    savings_tips,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("cost")

BANNER = """
========================================
 CLOUD COST CALCULATOR
   illustrative bundled rates
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Estimate cloud infrastructure cost (offline)")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--demo", action="store_true", help="run the offline demo")
    source.add_argument("--config", default=None, help="JSON infrastructure config")
    parser.add_argument("--provider", default=None,
                        help="override the config's provider (aws/gcp)")
    parser.add_argument("--budget", type=float, default=None,
                        help="override the config's monthly budget")
    parser.add_argument("--compare", action="store_true",
                        help="also print ondemand vs 1yr vs 3yr totals")
    parser.add_argument("--tips", action="store_true", default=True,
                        help="print savings tips (default on)")
    parser.add_argument("--no-tips", dest="tips", action="store_false",
                        help="hide savings tips")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        return run_demo()

    try:
        config = load_config(args.config)
        if args.budget is not None:
            if args.budget < 0:
                print("Error: --budget must be non-negative", file=sys.stderr)
                return 2
            config["budget"] = args.budget
        report = calculate(config, provider_name=args.provider)
    except CostError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print(BANNER)
    if args.json:
        payload = report.to_dict()
        if args.compare:
            payload["plan_comparison"] = plan_comparison(config, args.provider)
        print(json.dumps(payload, indent=2))
    else:
        print(render_report(report))
        if args.compare:
            print("\nPlan comparison (compute + database):")
            baseline_name = "ondemand"
            comparison = plan_comparison(config, args.provider)
            baseline = comparison[baseline_name]
            for plan, total in comparison.items():
                delta = total - baseline
                note = " (baseline)" if plan == baseline_name else f" ({delta:+.2f})"
                print(f"  {plan:<9} ${total:>8.2f}/mo{note}")
        if args.tips:
            tips = savings_tips(report)
            if tips:
                print("\nSavings tips:")
                for tip in tips:
                    print(f"  - {tip}")

    print("\nDone.")
    return 0 if report.budget_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
