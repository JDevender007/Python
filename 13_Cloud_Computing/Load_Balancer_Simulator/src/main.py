"""Command line entry point for the Load Balancer Simulator.

Usage
-----
    python src/main.py --demo                              # outage + recovery story
    python src/main.py --requests 5000 --strategy weighted
    python src/main.py --requests 1000 --strategy ip_hash --clients 64 --json

Everything is simulated in-process with a seeded RNG: no sockets, no network.
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys

from load_balancer import (
    STRATEGIES,
    Backend,
    LBError,
    LoadBalancer,
    NoHealthyBackendError,
    render_stats,
    run_demo,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("lb")

BANNER = """
========================================
 LOAD BALANCER SIMULATOR
   in-process backends, no sockets
========================================
"""


def build_backends(count: int, seed: int) -> list[Backend]:
    """Build `count` simulated backends with varied weights/failure rates."""
    if count < 1:
        raise LBError("--backends must be >= 1")
    rng = random.Random(seed)
    backends = []
    for i in range(1, count + 1):
        backends.append(
            Backend(
                name=f"web-{i}",
                port=8080 + i,
                weight=1 + (i % 3),          # 1..3
                failure_rate=0.0 if i == 1 else round(rng.uniform(0.02, 0.12), 3),
            )
        )
    return backends


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline load balancer simulator")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--demo", action="store_true", help="run the offline demo")
    source.add_argument("--requests", type=int, default=None, metavar="N",
                        help="simulate N requests")
    parser.add_argument("--strategy", default="round_robin", choices=STRATEGIES,
                        help="balancing strategy")
    parser.add_argument("--backends", type=int, default=3, help="number of backends")
    parser.add_argument("--clients", type=int, default=16,
                        help="distinct client IPs for hashing (default 16)")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed")
    parser.add_argument("--json", action="store_true", help="emit JSON stats")
    parser.add_argument("--failover", type=int, default=2,
                        help="max attempts per request (default 2)")
    args = parser.parse_args(argv)

    if args.demo:
        return run_demo()

    if args.requests < 1:
        print("Error: --requests must be >= 1", file=sys.stderr)
        return 2
    if args.clients < 1:
        print("Error: --clients must be >= 1", file=sys.stderr)
        return 2

    print(BANNER)
    try:
        backends = build_backends(args.backends, args.seed)
        lb = LoadBalancer(backends, strategy=args.strategy,
                          rng=random.Random(args.seed), max_attempts=args.failover)
        ips = [f"10.0.0.{(i * 7) % 254 + 1}" for i in range(args.clients)]
        lb.run(args.requests, client_ips=ips)
    except (LBError, NoHealthyBackendError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(lb.to_dict(), indent=2))
    else:
        print(render_stats(lb))
        print("\nDistribution:")
        for name, share in lb.distribution().items():
            bar = "#" * round(share * 40)
            print(f"  {name:<8} {share * 100:>5.1f}%  {bar}")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
