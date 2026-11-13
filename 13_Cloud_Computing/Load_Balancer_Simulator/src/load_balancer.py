"""Load balancer simulator: strategies, health checks, and failover stats.

Backends are simulated in-process (latency/failure rates, connection
counters), so the whole experiment runs offline with a seeded RNG - fully
deterministic and repeatable. Strategies: round-robin, least-connections,
smooth weighted round-robin, random, and source-IP hash.

No sockets are opened and nothing leaves this machine.
"""

from __future__ import annotations

import hashlib
import logging
import random
from typing import Any

LOG = logging.getLogger("lb.simulator")

STRATEGIES = ("round_robin", "least_connections", "weighted", "random", "ip_hash")


class LBError(RuntimeError):
    """Raised for configuration problems and exhausted backends."""


class NoHealthyBackendError(LBError):
    """Raised when every backend is down."""


# --------------------------------------------------------------------------- #
# Backends
# --------------------------------------------------------------------------- #
class Backend:
    """One simulated server with counters and a failure profile."""

    def __init__(
        self,
        name: str,
        host: str = "127.0.0.1",
        port: int = 8080,
        weight: int = 1,
        failure_rate: float = 0.0,
        healthy: bool = True,
    ) -> None:
        if weight < 1:
            raise LBError("weight must be >= 1")
        if not 0.0 <= failure_rate < 1.0:
            raise LBError("failure_rate must be in [0, 1)")
        self.name = name
        self.host = host
        self.port = port
        self.weight = weight
        self.failure_rate = failure_rate
        self.healthy = healthy

        self.total = 0          # successful requests served
        self.failures = 0       # requests that errored on this backend
        self.active = 0         # in-flight connections
        self.current_weight = 0  # smooth weighted round-robin state

    @property
    def address(self) -> str:
        return f"{self.host}:{self.port}"

    def serve(self, rng: random.Random) -> bool:
        """Handle one request; True on success, False on simulated failure."""
        self.active += 1
        try:
            ok = rng.random() >= self.failure_rate
        finally:
            self.active -= 1
        if ok:
            self.total += 1
        else:
            self.failures += 1
        return ok

    def snapshot(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "address": self.address,
            "weight": self.weight,
            "healthy": self.healthy,
            "served": self.total,
            "failures": self.failures,
            "active": self.active,
        }


# --------------------------------------------------------------------------- #
# Health checking
# --------------------------------------------------------------------------- #
class HealthChecker:
    """Consecutive-failure/success health state machine for backends."""

    def __init__(self, down_threshold: int = 3, up_threshold: int = 2) -> None:
        if down_threshold < 1 or up_threshold < 1:
            raise LBError("thresholds must be >= 1")
        self.down_threshold = down_threshold
        self.up_threshold = up_threshold
        self._failures: dict[str, int] = {}
        self._successes: dict[str, int] = {}

    def probe(self, backend: Backend, ok: bool) -> str | None:
        """Feed one probe result; returns an event message on state change."""
        if ok:
            self._failures[backend.name] = 0
            self._successes[backend.name] = self._successes.get(backend.name, 0) + 1
            if not backend.healthy and self._successes[backend.name] >= self.up_threshold:
                backend.healthy = True
                self._successes[backend.name] = 0
                LOG.info("health: %s back in rotation", backend.name)
                return f"{backend.name} recovered -> back in rotation"
            return None

        self._successes[backend.name] = 0
        self._failures[backend.name] = self._failures.get(backend.name, 0) + 1
        if backend.healthy and self._failures[backend.name] >= self.down_threshold:
            backend.healthy = False
            self._failures[backend.name] = 0
            LOG.info("health: %s marked unhealthy", backend.name)
            return f"{backend.name} marked unhealthy -> pulled from rotation"
        return None


# --------------------------------------------------------------------------- #
# Load balancer
# --------------------------------------------------------------------------- #
class LoadBalancer:
    """Distributes requests across healthy backends by strategy."""

    def __init__(
        self,
        backends: list[Backend],
        strategy: str = "round_robin",
        rng: random.Random | None = None,
        max_attempts: int = 2,
    ) -> None:
        if not backends:
            raise LBError("at least one backend is required")
        if strategy not in STRATEGIES:
            raise LBError(f"unknown strategy {strategy!r} (choose {', '.join(STRATEGIES)})")
        if max_attempts < 1:
            raise LBError("max_attempts must be >= 1")
        names = [b.name for b in backends]
        if len(set(names)) != len(names):
            raise LBError("backend names must be unique")
        self.backends = backends
        self.strategy = strategy
        self.rng = rng or random.Random(0)
        self.max_attempts = max_attempts
        self.health = HealthChecker()

        self._rr_index = 0
        self.served: dict[str, int] = {b.name: 0 for b in backends}
        self.failed_requests = 0
        self.retries = 0
        self.events: list[str] = []

    # --- selection ------------------------------------------------------ #
    def healthy_backends(self) -> list[Backend]:
        return [b for b in self.backends if b.healthy]

    def select_backend(self, client_ip: str = "127.0.0.1") -> Backend:
        """Pick one healthy backend according to the strategy."""
        pool = self.healthy_backends()
        if not pool:
            raise NoHealthyBackendError("all backends are unhealthy")
        return self._choose(pool, client_ip)

    def _choose(self, pool: list[Backend], client_ip: str) -> Backend:
        """Apply the strategy to an explicit candidate pool (failover-safe)."""
        if not pool:
            raise NoHealthyBackendError("all backends are unhealthy")

        if self.strategy == "round_robin":
            for _ in range(len(self.backends)):
                candidate = self.backends[self._rr_index % len(self.backends)]
                self._rr_index += 1
                if any(candidate is b for b in pool):
                    return candidate
            raise NoHealthyBackendError("no candidate in rotation")

        if self.strategy == "least_connections":
            return min(pool, key=lambda b: (b.active, b.name))

        if self.strategy == "weighted":
            return self._smooth_weighted(pool)

        if self.strategy == "random":
            return self.rng.choice(pool)

        # ip_hash: stable slot, linear probe to the next candidate in pool
        digest = hashlib.md5(client_ip.encode("utf-8")).digest()
        start = int.from_bytes(digest[:4], "big") % len(self.backends)
        for offset in range(len(self.backends)):
            candidate = self.backends[(start + offset) % len(self.backends)]
            if any(candidate is b for b in pool):
                return candidate
        raise NoHealthyBackendError("no candidate for client hash")

    def _smooth_weighted(self, pool: list[Backend]) -> Backend:
        """nginx-style smooth weighted round-robin over the candidate pool."""
        total = sum(b.weight for b in pool)
        best: Backend | None = None
        for backend in pool:
            backend.current_weight += backend.weight
            if best is None or backend.current_weight > best.current_weight:
                best = backend
        assert best is not None
        best.current_weight -= total
        return best

    # --- traffic -------------------------------------------------------- #
    def request(self, client_ip: str = "127.0.0.1") -> tuple[Backend | None, bool, int]:
        """Serve one request with failover.

        Returns (backend, success, attempts). `backend` is None when every
        attempt failed. Each retry picks a different healthy backend.
        """
        attempts = 0
        tried: set[str] = set()
        while attempts < self.max_attempts:
            pool = [b for b in self.healthy_backends() if b.name not in tried]
            if not pool:
                break
            backend = self._choose(pool, client_ip)
            tried.add(backend.name)
            attempts += 1
            if backend.serve(self.rng):
                self.served[backend.name] += 1
                return backend, True, attempts
            self.events.append(f"request failed on {backend.name} (attempt {attempts})")
            self.retries += 1

        self.failed_requests += 1
        self.events.append("request failed on all attempts")
        return None, False, attempts

    def run(self, count: int, client_ips: list[str] | None = None) -> dict[str, int]:
        """Serve `count` requests; returns the served distribution."""
        for i in range(count):
            ip = client_ips[i % len(client_ips)] if client_ips else "127.0.0.1"
            self.request(ip)
        return dict(self.served)

    # --- reporting ------------------------------------------------------ #
    @property
    def total_served(self) -> int:
        return sum(self.served.values())

    def distribution(self) -> dict[str, float]:
        """Share of successful requests per backend (0.0 when none)."""
        total = self.total_served
        if total == 0:
            return {name: 0.0 for name in self.served}
        return {name: count / total for name, count in self.served.items()}

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "served": dict(self.served),
            "total_served": self.total_served,
            "failed_requests": self.failed_requests,
            "retries": self.retries,
            "distribution": {k: round(v, 4) for k, v in self.distribution().items()},
            "backends": [b.snapshot() for b in self.backends],
            "events": list(self.events),
        }


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def render_stats(lb: LoadBalancer) -> str:
    """Human-readable distribution table used by the CLI and demo."""
    lines = [
        f"Strategy : {lb.strategy}",
        f"Served   : {lb.total_served} ok, {lb.failed_requests} failed, "
        f"{lb.retries} retries",
        "",
        f"{'Backend':<14} {'Addr':<16} {'State':<11} {'Served':>7} {'Fail':>6} {'Share':>8}",
        "-" * 66,
    ]
    for backend in lb.backends:
        state = "healthy" if backend.healthy else "DOWN"
        share = lb.distribution().get(backend.name, 0.0)
        lines.append(
            f"{backend.name:<14} {backend.address:<16} {state:<11} "
            f"{backend.total:>7} {backend.failures:>6} {share * 100:>7.1f}%"
        )
    if lb.events:
        lines.append("")
        lines.append(f"Events ({len(lb.events)}):")
        for event in lb.events[:10]:
            lines.append(f"  - {event}")
        if len(lb.events) > 10:
            lines.append(f"  ... {len(lb.events) - 10} more")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
def run_demo(requests: int = 1200, seed: int = 42) -> int:
    """Simulate traffic, a backend outage, and a recovery - fully offline."""
    print("=" * 60)
    print(" LOAD BALANCER SIMULATOR - offline demo")
    print(" Seeded RNG, in-process backends, no sockets.")
    print("=" * 60)

    rng = random.Random(seed)
    backends = [
        Backend("web-1", port=8081, weight=3, failure_rate=0.02),
        Backend("web-2", port=8082, weight=2, failure_rate=0.10),
        Backend("web-3", port=8083, weight=1, failure_rate=0.0),
    ]
    lb = LoadBalancer(backends, strategy="round_robin", rng=rng)
    checker = lb.health

    phase1 = requests // 3
    phase2 = requests // 3
    phase3 = requests - phase1 - phase2

    print(f"\n[Phase 1] {phase1} requests, all backends up")
    lb.run(phase1)
    print(render_stats(lb))

    print(f"\n[Phase 2] web-3 fails 3 consecutive health probes -> pulled")
    web3 = backends[2]
    for i in range(3):
        event = checker.probe(web3, ok=False)
        if event:
            lb.events.append(event)
            print(f"  health: {event}")
    print(f"  health: {web3.name} healthy={web3.healthy}")
    lb.run(phase2)
    print(f"  served now: {lb.served}")

    print(f"\n[Phase 3] web-3 recovers (2 good probes), {phase3} requests")
    for i in range(2):
        event = checker.probe(web3, ok=True)
        if event:
            lb.events.append(event)
            print(f"  health: {event}")
    lb.run(phase3)
    print(render_stats(lb))

    # strategy showcase on a fresh balancer (same seed -> same traffic)
    print("\nStrategy showcase (same traffic, fresh balancers):")
    ips = [f"10.0.0.{(i * 7) % 250 + 1}" for i in range(300)]
    for strategy in ("round_robin", "least_connections", "weighted", "ip_hash"):
        fresh = LoadBalancer(
            [Backend(b.name, port=b.port, weight=b.weight) for b in backends],
            strategy=strategy, rng=random.Random(seed),
        )
        fresh.run(300, client_ips=ips)
        shares = ", ".join(
            f"{name}:{count}" for name, count in fresh.served.items()
        )
        print(f"  {strategy:<18} -> {shares}")

    print("\nDemo completed successfully.")
    return 0
