"""Tests for the Load Balancer Simulator project."""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from load_balancer import (  # noqa: E402
    STRATEGIES,
    Backend,
    HealthChecker,
    LBError,
    LoadBalancer,
    NoHealthyBackendError,
    render_stats,
    run_demo,
)
from main import build_backends, main  # noqa: E402


class ScriptedRNG:
    """Returns pre-programmed values from random(); choice() takes the first."""

    def __init__(self, values: list[float]) -> None:
        self._values = list(values)

    def random(self) -> float:
        if not self._values:
            raise AssertionError("ran out of scripted RNG values")
        return self._values.pop(0)

    def choice(self, seq):
        return seq[0]


def _lb(strategy: str = "round_robin", backends: list[Backend] | None = None,
        rng=None, **kwargs) -> LoadBalancer:
    backends = backends or [
        Backend("a", port=1, weight=3),
        Backend("b", port=2, weight=2),
        Backend("c", port=3, weight=1),
    ]
    return LoadBalancer(backends, strategy=strategy, rng=rng, **kwargs)


# --------------------------------------------------------------------------- #
# Backend
# --------------------------------------------------------------------------- #
def test_backend_validation():
    with pytest.raises(LBError, match="weight"):
        Backend("x", weight=0)
    with pytest.raises(LBError, match="failure_rate"):
        Backend("x", failure_rate=1.0)
    with pytest.raises(LBError, match="failure_rate"):
        Backend("x", failure_rate=-0.1)


def test_backend_serve_success_and_failure():
    ok_backend = Backend("ok", failure_rate=0.0)
    assert ok_backend.serve(ScriptedRNG([0.99])) is True
    assert ok_backend.total == 1 and ok_backend.failures == 0
    assert ok_backend.active == 0  # connection released

    bad_backend = Backend("bad", failure_rate=0.5)
    assert bad_backend.serve(ScriptedRNG([0.1])) is False
    assert bad_backend.total == 0 and bad_backend.failures == 1
    assert bad_backend.active == 0


def test_backend_snapshot():
    snap = Backend("web", port=9000, weight=2).snapshot()
    assert snap["name"] == "web" and snap["address"] == "127.0.0.1:9000"
    assert snap["weight"] == 2 and snap["healthy"] is True
    assert set(snap) == {"name", "address", "weight", "healthy",
                         "served", "failures", "active"}


# --------------------------------------------------------------------------- #
# Health checker
# --------------------------------------------------------------------------- #
def test_health_down_after_threshold():
    checker = HealthChecker(down_threshold=3, up_threshold=2)
    backend = Backend("web")
    assert checker.probe(backend, ok=False) is None
    assert checker.probe(backend, ok=False) is None
    assert backend.healthy is True
    event = checker.probe(backend, ok=False)
    assert event is not None and "unhealthy" in event
    assert backend.healthy is False


def test_health_success_resets_failure_count():
    checker = HealthChecker(down_threshold=3, up_threshold=2)
    backend = Backend("web")
    checker.probe(backend, ok=False)
    checker.probe(backend, ok=False)
    checker.probe(backend, ok=True)   # resets failures
    checker.probe(backend, ok=False)
    checker.probe(backend, ok=False)
    assert backend.healthy is True    # needs 3 consecutive again


def test_health_recovery_after_up_threshold():
    checker = HealthChecker(down_threshold=1, up_threshold=2)
    backend = Backend("web", healthy=False)
    assert checker.probe(backend, ok=True) is None
    event = checker.probe(backend, ok=True)
    assert event is not None and "recovered" in event
    assert backend.healthy is True


def test_health_validation():
    with pytest.raises(LBError, match="thresholds"):
        HealthChecker(down_threshold=0)


# --------------------------------------------------------------------------- #
# Construction
# --------------------------------------------------------------------------- #
def test_lb_requires_backends():
    with pytest.raises(LBError, match="at least one"):
        LoadBalancer([])


def test_lb_rejects_unknown_strategy():
    with pytest.raises(LBError, match="unknown strategy"):
        _lb(strategy="magic")


def test_lb_rejects_duplicate_names():
    with pytest.raises(LBError, match="unique"):
        LoadBalancer([Backend("a"), Backend("a")])


def test_lb_rejects_bad_attempts():
    with pytest.raises(LBError, match="max_attempts"):
        _lb(max_attempts=0)


def test_strategy_list():
    assert set(STRATEGIES) == {"round_robin", "least_connections",
                               "weighted", "random", "ip_hash"}


# --------------------------------------------------------------------------- #
# Strategies
# --------------------------------------------------------------------------- #
def test_round_robin_cycles():
    lb = _lb()
    picks = [lb.select_backend().name for _ in range(6)]
    assert picks == ["a", "b", "c", "a", "b", "c"]


def test_round_robin_skips_unhealthy():
    lb = _lb()
    lb.backends[1].healthy = False
    picks = [lb.select_backend().name for _ in range(4)]
    assert picks == ["a", "c", "a", "c"]


def test_least_connections_picks_min():
    lb = _lb(strategy="least_connections")
    lb.backends[0].active = 5
    lb.backends[1].active = 1
    lb.backends[2].active = 3
    assert lb.select_backend().name == "b"
    # tie on active -> alphabetical for determinism
    lb.backends[0].active = lb.backends[1].active = 1
    assert lb.select_backend().name == "a"


def test_weighted_is_exactly_proportional():
    lb = _lb(strategy="weighted")
    picks = {b.name: 0 for b in lb.backends}
    for _ in range(600):
        picks[lb.select_backend().name] += 1
    # smooth WRR with weights 3:2:1 -> exactly 300/200/100 over 600 picks
    assert picks == {"a": 300, "b": 200, "c": 100}


def test_random_uses_rng_choice():
    lb = _lb(strategy="random", rng=ScriptedRNG([]))
    assert lb.select_backend().name == "a"  # choice() takes first candidate


def test_ip_hash_is_stable():
    lb = _lb(strategy="ip_hash")
    for ip in ("10.0.0.1", "192.168.1.5", "203.0.113.9"):
        first = lb.select_backend(ip).name
        for _ in range(5):
            assert lb.select_backend(ip).name == first


def test_ip_hash_skips_unhealthy():
    lb = _lb(strategy="ip_hash")
    target = lb.select_backend("10.0.0.42")
    target.healthy = False
    replacement = lb.select_backend("10.0.0.42")
    assert replacement.healthy is True
    assert replacement.name != target.name


def test_select_backend_all_down():
    lb = _lb()
    for backend in lb.backends:
        backend.healthy = False
    with pytest.raises(NoHealthyBackendError, match="unhealthy"):
        lb.select_backend()


# --------------------------------------------------------------------------- #
# Requests and failover
# --------------------------------------------------------------------------- #
def test_request_success_counts():
    lb = _lb(rng=ScriptedRNG([0.99, 0.99]))
    backend, ok, attempts = lb.request()
    assert ok is True and attempts == 1
    assert backend.name == "a"
    assert lb.served == {"a": 1, "b": 0, "c": 0}
    assert lb.failed_requests == 0


def test_request_failover_retries_other_backend():
    # 'a' fails (0.1 < 0.5), retry lands on 'b' which succeeds
    backends = [Backend("a", port=1, failure_rate=0.5),
                Backend("b", port=2, failure_rate=0.5)]
    lb = LoadBalancer(backends, strategy="round_robin",
                      rng=ScriptedRNG([0.1, 0.99]), max_attempts=2)
    backend, ok, attempts = lb.request()
    assert ok is True and attempts == 2
    assert backend.name == "b"
    assert lb.retries == 1 and lb.failed_requests == 0
    assert any("failed on a" in e for e in lb.events)


def test_request_all_attempts_fail():
    backends = [Backend("a", port=1, failure_rate=0.5),
                Backend("b", port=2, failure_rate=0.5)]
    lb = LoadBalancer(backends, strategy="round_robin",
                      rng=ScriptedRNG([0.1, 0.1]), max_attempts=2)
    backend, ok, attempts = lb.request()
    assert backend is None and ok is False and attempts == 2
    assert lb.failed_requests == 1
    assert "request failed on all attempts" in lb.events


def test_request_when_all_unhealthy():
    lb = _lb()
    for backend in lb.backends:
        backend.healthy = False
    backend, ok, attempts = lb.request()
    assert backend is None and ok is False and attempts == 0
    assert lb.failed_requests == 1


def test_run_counts_and_distribution():
    lb = _lb(rng=random.Random(42))
    # zero failure rates so every request succeeds
    for backend in lb.backends:
        backend.failure_rate = 0.0
    served = lb.run(300)
    assert sum(served.values()) == 300
    assert lb.total_served == 300
    shares = lb.distribution()
    assert sum(shares.values()) == pytest.approx(1.0)
    assert all(0 < share < 1 for share in shares.values())


def test_distribution_empty():
    lb = _lb()
    assert lb.distribution() == {"a": 0.0, "b": 0.0, "c": 0.0}


def test_run_with_client_ips():
    lb = _lb(strategy="ip_hash", rng=random.Random(42))
    for backend in lb.backends:
        backend.failure_rate = 0.0
    ips = [f"10.0.0.{i}" for i in range(1, 17)]
    served = lb.run(160, client_ips=ips)
    assert sum(served.values()) == 160
    assert all(count > 0 for count in served.values())  # hashes spread


def test_to_dict_shape():
    lb = _lb(rng=random.Random(42))
    lb.run(30)
    payload = lb.to_dict()
    for key in ("strategy", "served", "total_served", "failed_requests",
                "retries", "distribution", "backends", "events"):
        assert key in payload
    assert payload["strategy"] == "round_robin"
    assert len(payload["backends"]) == 3


def test_render_stats_sections():
    lb = _lb(rng=random.Random(42))
    lb.run(60)
    text = render_stats(lb)
    assert "Strategy" in text
    assert "Backend" in text
    assert "web" not in text  # names are a/b/c here
    assert "127.0.0.1:1" in text
    assert "Share" in text


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Phase 1" in out and "Phase 2" in out and "Phase 3" in out
    assert "marked unhealthy" in out
    assert "recovered" in out
    assert "Strategy showcase" in out


def test_run_demo_is_deterministic(capsys):
    assert run_demo() == 0
    first = capsys.readouterr().out
    assert run_demo() == 0
    second = capsys.readouterr().out
    assert first == second  # seeded RNG -> byte-identical output


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(capsys):
    assert main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out


def test_cli_requests_run(capsys):
    assert main(["--requests", "200", "--strategy", "weighted"]) == 0
    out = capsys.readouterr().out
    assert "Served   : 200 ok" in out
    assert "Distribution:" in out


def test_cli_json_output(capsys):
    assert main(["--requests", "100", "--json"]) == 0
    out = capsys.readouterr().out
    payload = json.loads(out[out.index("{"):out.rindex("}") + 1])
    assert payload["total_served"] == 100
    assert payload["strategy"] == "round_robin"


def test_cli_bad_requests(capsys):
    assert main(["--requests", "0"]) == 2
    assert "must be >= 1" in capsys.readouterr().err


def test_cli_bad_clients(capsys):
    assert main(["--requests", "10", "--clients", "0"]) == 2
    assert "clients" in capsys.readouterr().err


def test_cli_bad_backends(capsys):
    assert main(["--requests", "10", "--backends", "0"]) == 2
    assert "--backends must be >= 1" in capsys.readouterr().err


def test_cli_unknown_strategy(capsys):
    with pytest.raises(SystemExit):
        main(["--requests", "10", "--strategy", "magic"])


def test_cli_requires_action(capsys):
    with pytest.raises(SystemExit):
        main([])


def test_build_backends_shapes():
    backends = build_backends(5, seed=7)
    assert len(backends) == 5
    assert backends[0].failure_rate == 0.0
    assert all(1 <= b.weight <= 3 for b in backends)
    assert build_backends(5, seed=7)[1].failure_rate == \
        backends[1].failure_rate  # deterministic


def test_build_backends_rejects_zero():
    with pytest.raises(LBError, match=">= 1"):
        build_backends(0, seed=1)
