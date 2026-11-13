"""Release and rollback simulator: rollout state machine, health gates, SLO burn.

A release is promoted to a growing share of traffic (a canary: 5 -> 25 ->
50 -> 100). After each step the release is observed and a health gate
decides whether to continue. The first failed gate stops the rollout and
triggers a rollback to the previous release - which only helps if that
previous release is itself healthy.

Every observation is priced in error budget:

    bad_requests = soak_minutes * requests_per_minute * traffic_share * error_rate
    burn_rate    = bad_requests / (soak_minutes * requests_per_minute * (1 - target))
    budget_used  = total_bad_requests / (window_minutes * requests_per_minute
                                         * (1 - target))

so the blast radius of a bad release is measurable: a canary that fails at
5% traffic spends a small part of the window, while the same release
promoted blue-green at 100% blows the whole budget in one gate interval.

Fully offline: a local deployment document in, a deterministic rollout out.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

STRATEGY_CANARY = "canary"
STRATEGY_ROLLING = "rolling"
STRATEGY_BLUE_GREEN = "blue_green"
STRATEGIES = (STRATEGY_CANARY, STRATEGY_ROLLING, STRATEGY_BLUE_GREEN)

STRATEGY_STEPS = {
    STRATEGY_CANARY: (5, 25, 50, 100),
    STRATEGY_ROLLING: (25, 50, 75, 100),
    STRATEGY_BLUE_GREEN: (100,),
}

STATE_PENDING = "pending"
STATE_PROGRESSING = "progressing"
STATE_SUCCEEDED = "succeeded"
STATE_FAILED = "failed"
STATE_ROLLING_BACK = "rolling_back"
STATE_ROLLED_BACK = "rolled_back"
STATE_ROLLBACK_FAILED = "rollback_failed"
STATES = (STATE_PENDING, STATE_PROGRESSING, STATE_SUCCEEDED, STATE_FAILED,
          STATE_ROLLING_BACK, STATE_ROLLED_BACK, STATE_ROLLBACK_FAILED)

TRANSITIONS = {
    STATE_PENDING: (STATE_PROGRESSING,),
    STATE_PROGRESSING: (STATE_SUCCEEDED, STATE_FAILED),
    STATE_SUCCEEDED: (),
    STATE_FAILED: (STATE_ROLLING_BACK, STATE_ROLLBACK_FAILED),
    STATE_ROLLING_BACK: (STATE_ROLLED_BACK, STATE_ROLLBACK_FAILED),
    STATE_ROLLED_BACK: (),
    STATE_ROLLBACK_FAILED: (),
}

ALERT_LEVELS = ("ok", "slow", "fast", "critical")


class RolloutError(RuntimeError):
    """Raised for malformed documents, bad gates and illegal transitions."""


# --------------------------------------------------------------------------- #
# Configuration objects
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Gate:
    """Health thresholds that must all hold before traffic increases."""

    max_error_rate: float = 0.02
    max_latency_ms: float = 350.0
    max_saturation: float = 0.85

    def failures(self, release: "Release") -> tuple[str, ...]:
        reasons = []
        if release.error_rate > self.max_error_rate:
            reasons.append(f"error rate {release.error_rate:.2%} > "
                           f"{self.max_error_rate:.2%}")
        if release.latency_ms > self.max_latency_ms:
            reasons.append(f"latency {release.latency_ms:.1f} ms > "
                           f"{self.max_latency_ms:.1f} ms")
        if release.saturation > self.max_saturation:
            reasons.append(f"saturation {release.saturation:.2f} > "
                           f"{self.max_saturation:.2f}")
        return tuple(reasons)

    def describe(self) -> str:
        return (f"errors <= {self.max_error_rate:.2%}, "
                f"latency <= {self.max_latency_ms:.0f} ms, "
                f"saturation <= {self.max_saturation:.2f}")


@dataclass(frozen=True)
class Slo:
    """Service level objective used to price every observation."""

    target: float = 0.999
    window_minutes: int = 60
    requests_per_minute: int = 6000
    soak_minutes: int = 5

    @property
    def error_budget(self) -> float:
        """Allowed bad requests in the whole window."""
        return (self.window_minutes * self.requests_per_minute
                * (1.0 - self.target))

    def allowance(self, soak_minutes: int) -> float:
        """Allowed bad requests for one soak interval."""
        return soak_minutes * self.requests_per_minute * (1.0 - self.target)

    def describe(self) -> str:
        return (f"{self.target:.2%} over {self.window_minutes} min, "
                f"{self.requests_per_minute} req/min, "
                f"{self.soak_minutes} min soak")


@dataclass(frozen=True)
class Release:
    """One version and the behaviour it exhibits under load."""

    version: str
    error_rate: float
    latency_ms: float
    saturation: float

    def to_dict(self) -> dict[str, Any]:
        return {"version": self.version, "error_rate": self.error_rate,
                "latency_ms": self.latency_ms,
                "saturation": self.saturation}


@dataclass(frozen=True)
class Deployment:
    """A service, its gate, its SLO and its release history."""

    service: str
    gate: Gate
    slo: Slo
    releases: tuple[Release, ...]
    strategy: str = STRATEGY_CANARY

    def versions(self) -> tuple[str, ...]:
        return tuple(release.version for release in self.releases)

    def release(self, version: str) -> Release:
        for release in self.releases:
            if release.version == version:
                return release
        raise RolloutError(f"unknown release {version!r} "
                           f"(known: {', '.join(self.versions())})")

    def previous(self, version: str) -> Release | None:
        """The release immediately before `version` in the history."""
        versions = self.versions()
        if version not in versions:
            raise RolloutError(f"unknown release {version!r}")
        index = versions.index(version)
        return self.releases[index - 1] if index > 0 else None


# --------------------------------------------------------------------------- #
# Validation and parsing
# --------------------------------------------------------------------------- #
def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RolloutError(f"{label} must be a number, got {value!r}")
    return float(value)


def _integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RolloutError(f"{label} must be an integer, got {value!r}")
    return value


def _rate(value: Any, label: str) -> float:
    number = _number(value, label)
    if not 0.0 <= number <= 1.0:
        raise RolloutError(f"{label} must be in [0, 1], got {number}")
    return number


def parse_release(raw: Any, index: int) -> Release:
    label = f"release #{index + 1}"
    if not isinstance(raw, Mapping):
        raise RolloutError(f"{label} must be a mapping")
    version = raw.get("version")
    if not isinstance(version, str) or not version.strip():
        raise RolloutError(f"{label}: 'version' must be a non-empty string")
    latency = _number(raw.get("latency_ms"), f"{version}: 'latency_ms'")
    if latency <= 0:
        raise RolloutError(f"{version}: 'latency_ms' must be > 0")
    saturation = _rate(raw.get("saturation"), f"{version}: 'saturation'")
    return Release(
        version=version.strip(),
        error_rate=_rate(raw.get("error_rate"), f"{version}: 'error_rate'"),
        latency_ms=latency,
        saturation=saturation,
    )


def parse_gate(raw: Any) -> Gate:
    if raw is None:
        return Gate()
    if not isinstance(raw, Mapping):
        raise RolloutError("'gate' must be a mapping")
    gate = Gate(
        max_error_rate=_rate(raw.get("max_error_rate", 0.02),
                             "gate.max_error_rate"),
        max_latency_ms=_number(raw.get("max_latency_ms", 350.0),
                               "gate.max_latency_ms"),
        max_saturation=_rate(raw.get("max_saturation", 0.85),
                             "gate.max_saturation"),
    )
    if gate.max_latency_ms <= 0:
        raise RolloutError("gate.max_latency_ms must be > 0")
    if gate.max_saturation == 0:
        raise RolloutError("gate.max_saturation must be > 0")
    return gate


def parse_slo(raw: Any) -> Slo:
    if raw is None:
        return Slo()
    if not isinstance(raw, Mapping):
        raise RolloutError("'slo' must be a mapping")
    target = _number(raw.get("target", 0.999), "slo.target")
    if not 0.0 < target < 1.0:
        raise RolloutError(f"slo.target must be in (0, 1), got {target}")
    slo = Slo(
        target=target,
        window_minutes=_integer(raw.get("window_minutes", 60),
                                "slo.window_minutes"),
        requests_per_minute=_integer(raw.get("requests_per_minute", 6000),
                                     "slo.requests_per_minute"),
        soak_minutes=_integer(raw.get("soak_minutes", 5),
                              "slo.soak_minutes"),
    )
    if slo.window_minutes <= 0:
        raise RolloutError("slo.window_minutes must be > 0")
    if slo.requests_per_minute <= 0:
        raise RolloutError("slo.requests_per_minute must be > 0")
    if slo.soak_minutes <= 0:
        raise RolloutError("slo.soak_minutes must be > 0")
    if slo.soak_minutes > slo.window_minutes:
        raise RolloutError("slo.soak_minutes must not exceed the window")
    return slo


def parse_document(data: Mapping[str, Any]) -> Deployment:
    """Validate a decoded deployment document."""
    if not isinstance(data, Mapping):
        raise RolloutError("deployment document must be a mapping")
    service = data.get("service")
    if not isinstance(service, str) or not service.strip():
        raise RolloutError("'service' must be a non-empty string")

    raw_releases = data.get("releases")
    if not isinstance(raw_releases, (list, tuple)) or not raw_releases:
        raise RolloutError("'releases' must be a non-empty list")
    releases = tuple(parse_release(raw, index)
                     for index, raw in enumerate(raw_releases))
    versions = [release.version for release in releases]
    duplicates = sorted({v for v in versions if versions.count(v) > 1})
    if duplicates:
        raise RolloutError(f"duplicate release version(s): "
                           f"{', '.join(duplicates)}")

    strategy = data.get("strategy", STRATEGY_CANARY)
    if not isinstance(strategy, str) or strategy.strip().lower() not in \
            STRATEGIES:
        raise RolloutError(f"unknown strategy {strategy!r} "
                           f"(choose from {', '.join(STRATEGIES)})")

    return Deployment(
        service=service.strip(),
        gate=parse_gate(data.get("gate")),
        slo=parse_slo(data.get("slo")),
        releases=releases,
        strategy=strategy.strip().lower(),
    )


def load_deployment(path: str | Path) -> Deployment:
    source = Path(path)
    if not source.is_file():
        raise RolloutError(f"file not found: {source}")
    try:
        text = source.read_text(encoding="utf-8")
    except OSError as exc:
        raise RolloutError(f"could not read {source.name}: {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RolloutError(f"invalid JSON in {source.name}: {exc}") from exc
    return parse_document(data)


def plan_steps(strategy: str, steps: Sequence[int] | None = None
               ) -> tuple[int, ...]:
    """Resolve the traffic steps for a strategy, validating custom ones."""
    if not isinstance(strategy, str):
        raise RolloutError(f"strategy must be a string, got {strategy!r}")
    name = strategy.strip().lower()
    if name not in STRATEGIES:
        raise RolloutError(f"unknown strategy {strategy!r} "
                           f"(choose from {', '.join(STRATEGIES)})")
    if steps is None:
        return STRATEGY_STEPS[name]
    if len(steps) == 0:
        raise RolloutError("steps must not be empty")
    resolved: list[int] = []
    for step in steps:
        value = _integer(step, "step")
        if not 1 <= value <= 100:
            raise RolloutError(f"every step must be in [1, 100], got {value}")
        if resolved and value <= resolved[-1]:
            raise RolloutError(f"steps must strictly increase, "
                               f"got {resolved[-1]} then {value}")
        resolved.append(value)
    if resolved[-1] != 100:
        raise RolloutError(f"the last step must be 100%, "
                           f"got {resolved[-1]}")
    return tuple(resolved)


# --------------------------------------------------------------------------- #
# State machine
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Transition:
    state: str
    event: str
    step: int

    def to_dict(self) -> dict[str, Any]:
        return {"state": self.state, "event": self.event, "step": self.step}


class _Machine:
    """Tracks the rollout state and rejects illegal transitions."""

    def __init__(self) -> None:
        self.state = STATE_PENDING
        self.history: list[Transition] = []

    def advance(self, state: str, event: str, step: int) -> None:
        if state not in STATES:
            raise RolloutError(f"unknown state {state!r}")
        if state not in TRANSITIONS[self.state]:
            raise RolloutError(f"illegal transition {self.state} -> {state} "
                               f"({event})")
        self.history.append(Transition(state, event, step))
        self.state = state


# --------------------------------------------------------------------------- #
# Observation and pricing
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Observation:
    """One gate evaluation at one traffic level."""

    step: int
    traffic_percent: int
    version: str
    error_rate: float
    latency_ms: float
    saturation: float
    passed: bool
    reasons: tuple[str, ...]
    soak_minutes: int
    bad_requests: float
    burn_rate: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "traffic_percent": self.traffic_percent,
            "version": self.version,
            "error_rate": self.error_rate,
            "latency_ms": self.latency_ms,
            "saturation": self.saturation,
            "passed": self.passed,
            "reasons": list(self.reasons),
            "soak_minutes": self.soak_minutes,
            "bad_requests": round(self.bad_requests, 3),
            "burn_rate": round(self.burn_rate, 3),
        }


def alert_level(burn_rate: float) -> str:
    """SRE-style burn-rate classification: 1x = spending at exactly budget."""
    if burn_rate < 0:
        raise RolloutError(f"burn rate must be >= 0, got {burn_rate}")
    if burn_rate < 1.0:
        return "ok"
    if burn_rate < 2.0:
        return "slow"
    if burn_rate < 10.0:
        return "fast"
    return "critical"


def observe(release: Release, traffic_percent: int, step: int, gate: Gate,
            slo: Slo, version: str | None = None) -> Observation:
    """Evaluate the gate and price the observation in error budget."""
    if not isinstance(release, Release):
        raise RolloutError("observe() needs a Release")
    share = _integer(traffic_percent, "traffic_percent") / 100.0
    if not 0.0 < share <= 1.0:
        raise RolloutError(f"traffic_percent must be in (0, 100], "
                           f"got {traffic_percent}")
    soak = _integer(step, "step")
    if soak < 1:
        raise RolloutError(f"step must be >= 1, got {soak}")

    reasons = gate.failures(release)
    bad = (slo.soak_minutes * slo.requests_per_minute * share
           * release.error_rate)
    allowed = slo.allowance(slo.soak_minutes)
    return Observation(
        step=soak,
        traffic_percent=traffic_percent,
        version=version or release.version,
        error_rate=release.error_rate,
        latency_ms=release.latency_ms,
        saturation=release.saturation,
        passed=not reasons,
        reasons=reasons,
        soak_minutes=slo.soak_minutes,
        bad_requests=bad,
        burn_rate=bad / allowed if allowed > 0 else 0.0,
    )


# --------------------------------------------------------------------------- #
# Simulation
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class RolloutResult:
    """The full outcome of one rollout attempt."""

    service: str
    strategy: str
    target: str
    previous: str | None
    steps: tuple[int, ...]
    observations: tuple[Observation, ...]
    transitions: tuple[Transition, ...]
    state: str
    rolled_back_to: str | None
    budget_used: float
    peak_burn: float

    @property
    def healthy(self) -> bool:
        return self.state in (STATE_SUCCEEDED, STATE_ROLLED_BACK)

    @property
    def failed_steps(self) -> tuple[Observation, ...]:
        return tuple(item for item in self.observations if not item.passed)

    @property
    def alert(self) -> str:
        return alert_level(self.peak_burn)

    def to_dict(self) -> dict[str, Any]:
        return {
            "service": self.service,
            "strategy": self.strategy,
            "target": self.target,
            "previous": self.previous,
            "steps": list(self.steps),
            "observations": [item.to_dict() for item in self.observations],
            "transitions": [item.to_dict() for item in self.transitions],
            "state": self.state,
            "rolled_back_to": self.rolled_back_to,
            "healthy": self.healthy,
            "budget_used": round(self.budget_used, 4),
            "peak_burn": round(self.peak_burn, 3),
            "alert": self.alert,
        }


def execute(deployment: Deployment, version: str,
            strategy: str | None = None,
            steps: Sequence[int] | None = None) -> RolloutResult:
    """Run a rollout of `version` through the gate and roll back on failure."""
    if not isinstance(deployment, Deployment):
        raise RolloutError("execute() needs a Deployment")
    target = deployment.release(version)
    name = (strategy or deployment.strategy).strip().lower()
    plan = plan_steps(name, steps)
    previous = deployment.previous(version)

    machine = _Machine()
    machine.advance(STATE_PROGRESSING, "start", 0)
    observations: list[Observation] = []
    rolled_back_to: str | None = None

    for index, traffic in enumerate(plan, start=1):
        item = observe(target, traffic, index, deployment.gate,
                       deployment.slo)
        observations.append(item)
        if not item.passed:
            machine.advance(STATE_FAILED, "gate failed", index)
            break
        if index == len(plan):
            machine.advance(STATE_SUCCEEDED, "promoted", index)

    if machine.state == STATE_FAILED:
        rollback_step = len(observations) + 1
        if previous is None:
            machine.advance(STATE_ROLLBACK_FAILED, "no previous release",
                            rollback_step)
        else:
            machine.advance(STATE_ROLLING_BACK, "rollback", rollback_step)
            restore = observe(previous, 100, rollback_step, deployment.gate,
                              deployment.slo)
            observations.append(restore)
            if restore.passed:
                machine.advance(STATE_ROLLED_BACK, "previous release healthy",
                                rollback_step)
                rolled_back_to = previous.version
            else:
                machine.advance(STATE_ROLLBACK_FAILED,
                                "previous release also fails the gate",
                                rollback_step)

    budget = deployment.slo.error_budget
    spent = sum(item.bad_requests for item in observations)
    return RolloutResult(
        service=deployment.service,
        strategy=name,
        target=target.version,
        previous=previous.version if previous else None,
        steps=plan,
        observations=tuple(observations),
        transitions=tuple(machine.history),
        state=machine.state,
        rolled_back_to=rolled_back_to,
        budget_used=spent / budget if budget > 0 else 0.0,
        peak_burn=max((item.burn_rate for item in observations), default=0.0),
    )


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def render_report(result: RolloutResult) -> str:
    lines = [
        f"ROLLOUT - {result.service}",
        "=" * 78,
        f"strategy : {result.strategy} "
        f"({', '.join(f'{step}%' for step in result.steps)})",
        f"target   : {result.target}",
        f"previous : {result.previous or '(none)'}",
        "",
        f"  {'step':>4}{'traffic':>9}{'version':>14}{'errors':>9}"
        f"{'latency':>9}{'sat':>7}{'burn':>7}  result",
        "  " + "-" * 70,
    ]
    for item in result.observations:
        status = "pass" if item.passed else "FAIL"
        lines.append(
            f"  {item.step:>4}{item.traffic_percent:>8}%{item.version:>14}"
            f"{item.error_rate:>8.2%}{item.latency_ms:>8.0f}"
            f"{item.saturation:>7.2f}{item.burn_rate:>7.2f}  {status}")
        for reason in item.reasons:
            lines.append(f"  {'':>4}{'':>8} {reason}")

    lines += [
        "",
        "state    : " + result.state,
        f"budget   : {result.budget_used:.1%} of the SLO window consumed "
        f"(peak burn {result.peak_burn:.2f}x, alert {result.alert})",
        f"result   : {'HEALTHY' if result.healthy else 'UNHEALTHY'}",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Bundled data and the offline demo
# --------------------------------------------------------------------------- #
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
BUNDLED_DEPLOYMENT = DATA_DIR / "deployment.json"

EXPECTED_SERVICE = "checkout-api"
EXPECTED_VERSIONS = ("1.4.0", "1.5.0", "1.6.0-rc1", "1.6.0-rc2", "1.6.0")
# canary failure: 5 min at 5% with 8.1% errors, then the rollback soak
EXPECTED_CANARY_BUDGET = 0.629
# the same release promoted blue-green: 5 min at 100% first
EXPECTED_BLUE_BUDGET = 7.042


def run_demo(path: Path | None = None) -> int:
    """Roll the bundled releases forward under three strategies and assert."""
    print("=" * 78)
    print(" RELEASE / ROLLBACK SIMULATOR - offline demo")
    print(" Canary, rolling and blue-green rollouts with health gates and")
    print(" SLO error-budget accounting. No cluster, no network.")
    print("=" * 78)

    source = path or BUNDLED_DEPLOYMENT
    if not source.is_file():
        raise RolloutError(f"bundled sample not found: {source}")
    deployment = load_deployment(source)
    gate, slo = deployment.gate, deployment.slo

    # 1. the document parsed into the expected history
    assert deployment.service == EXPECTED_SERVICE
    assert deployment.versions() == EXPECTED_VERSIONS, deployment.versions()
    assert deployment.previous("1.6.0-rc1").version == "1.5.0"
    assert deployment.previous("1.4.0") is None

    # 2. strategy plans are the documented traffic ladders
    assert plan_steps(STRATEGY_CANARY) == (5, 25, 50, 100)
    assert plan_steps(STRATEGY_ROLLING) == (25, 50, 75, 100)
    assert plan_steps(STRATEGY_BLUE_GREEN) == (100,)
    # 3. custom steps are validated (negative control: 5 then 5, no 100)
    assert plan_steps("canary", [10, 50, 100]) == (10, 50, 100)
    for bad in ([10, 10, 100], [10, 50], [0, 100], [50, 100, 90]):
        try:
            plan_steps("canary", bad)
        except RolloutError:
            pass
        else:
            raise AssertionError(f"invalid steps accepted: {bad}")

    # --- 1: canary of a release that breaks the error gate ---------------- #
    canary = execute(deployment, "1.6.0-rc1", STRATEGY_CANARY)
    assert canary.state == STATE_ROLLED_BACK, canary.state
    assert canary.healthy, "a successful rollback is a healthy outcome"
    assert canary.rolled_back_to == "1.5.0"
    assert len(canary.observations) == 2, \
        f"expected one gate failure plus a rollback, got " \
        f"{len(canary.observations)}"
    assert canary.observations[0].traffic_percent == 5
    assert not canary.observations[0].passed
    assert "error rate" in canary.observations[0].reasons[0]
    # 4. the rollback soak is the previous release at full traffic, and it
    #    passes - which is why the rollback succeeds
    assert canary.observations[1].version == "1.5.0"
    assert canary.observations[1].traffic_percent == 100
    assert canary.observations[1].passed
    # 5. budget arithmetic: 121.5 bad requests out of a 360 budget
    assert canary.budget_used == pytest_approx(EXPECTED_CANARY_BUDGET,
                                               abs_tol=0.002)

    # 6. the same release promoted blue-green exposes 20x the traffic
    blue = execute(deployment, "1.6.0-rc1", STRATEGY_BLUE_GREEN)
    assert blue.state == STATE_ROLLED_BACK
    assert len(blue.observations) == 2
    assert blue.observations[0].traffic_percent == 100
    assert blue.budget_used == pytest_approx(EXPECTED_BLUE_BUDGET, abs_tol=0.01)
    # 7. and therefore blows the error budget, while the canary stayed in it
    assert blue.budget_used > 1.0 > canary.budget_used
    assert blue.budget_used / canary.budget_used > 10, \
        "blue-green should cost far more budget than a canary"
    assert canary.alert == "fast" and blue.alert == "critical"
    assert canary.peak_burn == pytest_approx(4.05, abs_tol=0.01)
    assert blue.peak_burn == pytest_approx(81.0, abs_tol=0.1)

    # 8. the state machine path is exactly pending -> progressing -> failed
    #    -> rolling_back -> rolled_back
    assert [t.state for t in canary.transitions] == [
        STATE_PROGRESSING, STATE_FAILED, STATE_ROLLING_BACK,
        STATE_ROLLED_BACK]
    assert [t.event for t in canary.transitions] == [
        "start", "gate failed", "rollback", "previous release healthy"]

    # --- 2: a release that breaks only the latency gate ------------------- #
    # rc2 follows rc1, which is itself unhealthy - so the rollback has
    # nowhere good to land. This is the hazard of shipping two bad versions
    # in a row, and it is asserted rather than glossed over.
    latency = execute(deployment, "1.6.0-rc2", STRATEGY_CANARY)
    assert latency.state == STATE_ROLLBACK_FAILED, latency.state
    assert not latency.healthy
    reasons = latency.observations[0].reasons
    assert len(reasons) == 1 and reasons[0].startswith("latency"), reasons
    assert latency.observations[1].version == "1.6.0-rc1"
    assert not latency.observations[1].passed
    assert "also fails the gate" in latency.transitions[-1].event
    # the latency failure itself is cheap - 6 bad requests, not 121.5 - but
    # the failed rollback pours full traffic back onto the broken rc1
    assert latency.observations[0].bad_requests < \
        canary.observations[0].bad_requests
    assert latency.observations[1].bad_requests == pytest_approx(
        2430.0, abs_tol=1e-6)
    assert latency.budget_used > 1.0 > canary.budget_used

    # --- 3: a good release promoted through the full ladder --------------- #
    good = execute(deployment, "1.6.0", STRATEGY_CANARY)
    assert good.state == STATE_SUCCEEDED
    assert good.healthy and good.rolled_back_to is None
    assert len(good.observations) == 4
    assert all(item.passed for item in good.observations)
    assert [item.traffic_percent for item in good.observations] == \
        [5, 25, 50, 100]
    # 9. a healthy release does not burn the whole window: 5+25+50+100 % of
    #    traffic at 0.09% errors stays far inside the budget
    assert 0.0 < good.budget_used < 0.2, good.budget_used
    assert good.alert == "ok", good.alert
    assert good.transitions[-1].state == STATE_SUCCEEDED
    # and every step passed on its own merits, not by luck of ordering
    assert good.peak_burn < 1.0

    # --- 4: a first release has nothing to roll back to ------------------- #
    first = Deployment(
        service="checkout-api",
        gate=gate,
        slo=slo,
        releases=(
            Release("0.9.0", error_rate=0.06, latency_ms=231.0,
                    saturation=0.58),
        ),
    )
    stuck = execute(first, "0.9.0", STRATEGY_CANARY)
    assert stuck.state == STATE_ROLLBACK_FAILED, stuck.state
    assert not stuck.healthy
    assert stuck.rolled_back_to is None and stuck.previous is None
    assert stuck.transitions[-1].event == "no previous release"
    # only the failed canary soak was paid for - there is nothing to soak
    assert len(stuck.observations) == 1

    # 10. illegal transitions are impossible by construction
    from_succeeded = _Machine()
    from_succeeded.advance(STATE_PROGRESSING, "start", 0)
    from_succeeded.advance(STATE_SUCCEEDED, "promoted", 4)
    try:
        from_succeeded.advance(STATE_ROLLING_BACK, "rollback", 5)
    except RolloutError:
        pass
    else:
        raise AssertionError("succeeded -> rolling_back was allowed")

    # 11. determinism
    assert execute(deployment, "1.6.0-rc1", STRATEGY_CANARY) == canary
    assert execute(deployment, "1.6.0", STRATEGY_CANARY) == good

    # 12. every observation is priced with the documented formula
    expected_bad = (slo.soak_minutes * slo.requests_per_minute * 0.05
                    * deployment.release("1.6.0-rc1").error_rate)
    assert canary.observations[0].bad_requests == pytest_approx(
        expected_bad, abs_tol=1e-9)
    expected_budget = (slo.window_minutes * slo.requests_per_minute
                       * (1.0 - slo.target))
    spent = sum(item.bad_requests for item in canary.observations)
    assert canary.budget_used == pytest_approx(spent / expected_budget,
                                               abs_tol=1e-12)

    print()
    print(render_report(canary))
    print()
    print(render_report(blue))
    print()
    print(render_report(good))

    print()
    print(f"Cross-checks OK: {len(deployment.releases)} releases parsed with "
          f"1.5.0 as the rollback target, canary 5/25/50/100 vs rolling "
          f"25/50/75/100 vs blue-green 100 only, invalid ladders rejected, "
          f"the canary fails the error gate at 5% and rolls back to 1.5.0, "
          f"blue-green exposes 20x the traffic and consumes "
          f"{blue.budget_used / canary.budget_used:.1f}x the budget "
          f"({blue.budget_used:.2f} vs {canary.budget_used:.2f} of the "
          f"window), the latency-only release fails on latency alone but its "
          f"rollback re-runs the broken rc1 at full traffic and costs "
          f"{latency.budget_used:.2f}x the window budget, a healthy release "
          f"climbs all "
          f"four steps inside {good.budget_used:.1%} of the window, the "
          f"first release has no rollback target and ends in "
          f"rollback_failed, illegal transitions are refused, budget "
          f"arithmetic matches the formula, deterministic re-run")
    print("\nDemo completed successfully.")
    return 0


def pytest_approx(value: float, abs_tol: float = 1e-6) -> Any:
    """Tiny local stand-in for pytest.approx so the demo needs no pytest.

    The parameter must NOT be called `abs`: a nested function closes over its
    enclosing scope, so `abs(...)` inside __eq__ would resolve to the float
    and quietly raise TypeError - swallowed by the except clause, which turns
    every tolerance check into a silent False.
    """
    tolerance = abs_tol

    class _Approx:
        def __eq__(self, other: Any) -> bool:
            try:
                return abs(float(other) - value) <= tolerance
            except (TypeError, ValueError):
                return False

        def __repr__(self) -> str:
            return f"approx({value}, abs_tol={tolerance})"

    return _Approx()
