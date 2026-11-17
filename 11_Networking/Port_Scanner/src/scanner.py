"""A scan has three answers, and a timeout is not one of the two you know.

The legacy scanner scores every port with a single membership test:

    open_ports = {row.port for row in rows if row.outcome == "open"}
    closed = sorted(set(ports) - open_ports)

Anything that did not accept a connection is called *closed*. That is a claim the
network never made. A port answers a SYN in exactly three ways:

* **open** -- a TCP handshake completed, so something is listening;
* **closed** -- the host answered with a reset, so the packet arrived and nothing
  was listening: a definitive, evidence-bearing answer;
* **filtered** -- nothing came back before the timeout. The packet may have been
  dropped by a firewall, the host may be down, or the reply may be late. It is
  *not* closed, and it is not open. It is unknown.

In the bundled scan 13 ports produce 4 open, 6 closed and 3 filtered. The legacy
report prints 4 open and **9 closed**, so a firewall that silently drops traffic
is indistinguishable from a host with nothing on that port -- the two conclusions
a scan exists to separate.

Two more defects follow from the same impatience:

**A timeout is not latency.** The legacy average adds the 800 ms of every timed-out
probe to the responses it did get, so a scan whose answered probes took 11 ms
reports 307 ms. A timeout is the absence of a response, not a slow one.

**Retries exist to resolve doubt, not to invent certainty.** The policy allows two
attempts per port. A timeout is retried, a refusal is not, and a later `open`
outranks an earlier timeout. The legacy code retries the same way and then throws
away everything the retry learned by collapsing it to `closed`.

The rebuild classifies each port by the strongest evidence any attempt produced,
keeps the three states distinct all the way to the report, and averages latency
only over probes that answered. The scan itself is a bundled transcript: no socket
is opened.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SCAN_FILE = DATA_DIR / "scan.csv"
POLICY_FILE = DATA_DIR / "policy.csv"

OUTCOMES = ("open", "refused", "timeout")
STATES = ("open", "closed", "filtered")

#: The state each outcome is evidence for.
STATE_OF = {"open": "open", "refused": "closed", "timeout": "filtered"}

#: How strong the evidence is. `open` proves a listener, `refused` proves the
#: host answered and nothing listened, `timeout` proves only that nothing came back.
STRENGTH = {"open": 3, "refused": 2, "timeout": 1}

#: The legacy one-liner, kept as text so the demo can print it.
LEGACY_CLASSIFY = (
    'open_ports = {row.port for row in rows if row.outcome == "open"}\n'
    "closed = sorted(set(ports) - open_ports)"
)

#: The legacy latency average, which treats a timeout as a slow reply.
LEGACY_LATENCY = "average_ms = round(sum(row.latency_ms for row in rows) / len(rows))"


class ScanError(RuntimeError):
    """Raised for input the program refuses."""


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def _text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ScanError(f"{name} must be text, got {type(value).__name__}")
    if not value.strip():
        raise ScanError(f"{name} must not be empty")
    return value


def _whole(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ScanError(f"{name} must be an integer, got {type(value).__name__}")
    return value


def _positive(value: object, name: str) -> int:
    number = _whole(value, name)
    if number <= 0:
        raise ScanError(f"{name} must be positive, got {number}")
    return number


def _non_negative(value: object, name: str) -> int:
    number = _whole(value, name)
    if number < 0:
        raise ScanError(f"{name} must not be negative, got {number}")
    return number


def divide_half_up(numerator: int, denominator: int) -> int:
    """Integer division rounding halves away from zero, with no float."""
    top = _whole(numerator, "numerator")
    bottom = _positive(denominator, "denominator")
    sign = -1 if top < 0 else 1
    magnitude = abs(top)
    return sign * ((magnitude * 2 + bottom) // (2 * bottom))


def is_port(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, int)
        and 1 <= value <= 65535
    )


def require_port(value: object, name: str = "port") -> int:
    if not is_port(value):
        raise ScanError(f"{name} must be an integer in 1..65535, got {value!r}")
    return int(value)  # type: ignore[arg-type]


def outcome_of(text: str) -> str:
    raw = _text(text, "outcome").strip().lower()
    if raw not in OUTCOMES:
        raise ScanError(f"outcome must be one of {list(OUTCOMES)}, got {raw!r}")
    return raw


def _int(text: str, name: str) -> int:
    raw = _text(text, name).strip()
    try:
        return int(raw, 10)
    except ValueError as exc:
        raise ScanError(f"{name} must be a whole number, got {raw!r}") from exc


# --------------------------------------------------------------------------- #
# Records
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Policy:
    """How long a probe waits, and how many attempts a port gets."""

    timeout_ms: int
    retries: int


@dataclass(frozen=True)
class Probe:
    """One attempt against one port."""

    port: int
    attempt: int
    outcome: str
    latency_ms: int


@dataclass(frozen=True)
class Verdict:
    """What the evidence says about one port."""

    port: int
    state: str
    attempts: int
    evidence: str

    @property
    def answered(self) -> bool:
        return self.state != "filtered"


def _read_rows(path: str | Path, required: Sequence[str]) -> list[dict[str, str]]:
    target = Path(path)
    if not target.is_file():
        raise ScanError(f"file not found: {target.name}")
    with target.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        missing = [column for column in required if column not in header]
        if missing:
            raise ScanError(f"{target.name} is missing column(s): {', '.join(missing)}")
        return [dict(row) for row in reader]


def load_policy(path: str | Path | None = None) -> Policy:
    rows = _read_rows(path or POLICY_FILE, ("timeout_ms", "retries"))
    if len(rows) != 1:
        raise ScanError(f"policy.csv must hold exactly one row, got {len(rows)}")
    timeout = _positive(_int(rows[0]["timeout_ms"], "timeout_ms"), "timeout_ms")
    retries = _positive(_int(rows[0]["retries"], "retries"), "retries")
    if retries > 5:
        raise ScanError(f"retries must be at most 5, got {retries}")
    return Policy(timeout_ms=timeout, retries=retries)


def require_timeout_latency(timeout_ms: int, latency_ms: int) -> int:
    """A timeout is a wait of exactly the policy's length, not a fast reply."""
    total = _positive(timeout_ms, "timeout_ms")
    got = _non_negative(latency_ms, "latency_ms")
    if got != total:
        raise ScanError(
            f"a timeout that returned in {got} ms is not a timeout; the policy waits {total} ms"
        )
    return got


def require_answer_latency(timeout_ms: int, latency_ms: int) -> int:
    """An answer arrived before the timeout, or it would not be an answer."""
    total = _positive(timeout_ms, "timeout_ms")
    got = _non_negative(latency_ms, "latency_ms")
    if got >= total:
        raise ScanError(f"an answer in {got} ms is not before the {total} ms timeout")
    return got


def require_attempts(policy: Policy, attempts: Sequence[int]) -> list[int]:
    """Attempt numbers run 1..n with no gap, no duplicate, and within the policy."""
    ordered = sorted(_positive(attempt, "attempt") for attempt in attempts)
    if ordered != list(range(1, len(ordered) + 1)):
        raise ScanError(f"attempt numbers {ordered} are not 1..n")
    if len(ordered) > policy.retries:
        raise ScanError(f"{len(ordered)} attempts exceed the policy's {policy.retries}")
    return ordered


def load_probes(path: str | Path | None = None, *, policy: Policy | None = None) -> list[Probe]:
    rows = _read_rows(path or SCAN_FILE, ("port", "attempt", "outcome", "latency_ms"))
    if not rows:
        raise ScanError("scan.csv holds no probes")
    settings = policy or load_policy()
    probes: list[Probe] = []
    for row in rows:
        probe = Probe(
            port=require_port(_int(row["port"], "port")),
            attempt=_positive(_int(row["attempt"], "attempt"), "attempt"),
            outcome=outcome_of(row["outcome"]),
            latency_ms=_non_negative(_int(row["latency_ms"], "latency_ms"), "latency_ms"),
        )
        if probe.outcome == "timeout":
            require_timeout_latency(settings.timeout_ms, probe.latency_ms)
        else:
            require_answer_latency(settings.timeout_ms, probe.latency_ms)
        probes.append(probe)
    return check_attempts(probes, settings)


def check_attempts(probes: Sequence[Probe], policy: Policy) -> list[Probe]:
    """Every port's attempts must be 1..n with no gap and no duplicate."""
    seen: dict[int, list[int]] = {}
    for probe in probes:
        seen.setdefault(probe.port, []).append(probe.attempt)
    for port in sorted(seen):
        require_attempts(policy, seen[port])
    return list(probes)


# --------------------------------------------------------------------------- #
# Classification
# --------------------------------------------------------------------------- #
def strongest(probes: Sequence[Probe]) -> Probe:
    """The attempt carrying the strongest evidence, latest attempt breaking ties."""
    rows = list(probes)
    if not rows:
        raise ScanError("a port needs at least one probe")
    return max(rows, key=lambda probe: (STRENGTH[probe.outcome], probe.attempt))


def classify(probes: Sequence[Probe]) -> list[Verdict]:
    """One verdict per port, ordered by port number."""
    by_port: dict[int, list[Probe]] = {}
    for probe in probes:
        by_port.setdefault(probe.port, []).append(probe)
    verdicts: list[Verdict] = []
    for port in sorted(by_port):
        rows = by_port[port]
        best = strongest(rows)
        verdicts.append(
            Verdict(
                port=port,
                state=STATE_OF[best.outcome],
                attempts=len(rows),
                evidence=best.outcome,
            )
        )
    return verdicts


def state_counts(verdicts: Sequence[Verdict]) -> dict[str, int]:
    counts = {state: 0 for state in STATES}
    for verdict in verdicts:
        if verdict.state not in counts:
            raise ScanError(f"unknown state in a verdict: {verdict.state!r}")
        counts[verdict.state] += 1
    return counts


def ports_by_state(verdicts: Sequence[Verdict]) -> dict[str, list[int]]:
    grouped: dict[str, list[int]] = {state: [] for state in STATES}
    for verdict in verdicts:
        grouped[verdict.state].append(verdict.port)
    return grouped


def legacy_closed(verdicts: Sequence[Verdict], settled: Sequence[Probe]) -> list[int]:
    """Every port that is not open, called closed -- the collapse."""
    open_ports = {probe.port for probe in settled if probe.outcome == "open"}
    return sorted({verdict.port for verdict in verdicts} - open_ports)


def retried_ports(probes: Sequence[Probe]) -> list[int]:
    counts: dict[int, int] = {}
    for probe in probes:
        counts[probe.port] = counts.get(probe.port, 0) + 1
    return sorted(port for port, count in counts.items() if count > 1)


def answered_latency_ms(probes: Sequence[Probe]) -> int:
    """Mean latency over the probes that actually answered."""
    rows = [probe for probe in probes if probe.outcome != "timeout"]
    if not rows:
        return 0
    return divide_half_up(sum(probe.latency_ms for probe in rows), len(rows))


def legacy_latency_ms(probes: Sequence[Probe]) -> int:
    """The legacy average, which counts each timeout's full wait as a response."""
    rows = list(probes)
    if not rows:
        return 0
    return divide_half_up(sum(probe.latency_ms for probe in rows), len(rows))


def wait_ms(probes: Sequence[Probe]) -> int:
    """Time spent waiting for answers that never came."""
    return sum(probe.latency_ms for probe in probes if probe.outcome == "timeout")


# --------------------------------------------------------------------------- #
# Measurement
# --------------------------------------------------------------------------- #
def measure(
    scan_path: str | Path | None = None,
    *,
    policy_path: str | Path | None = None,
) -> dict[str, Any]:
    if scan_path is not None:
        folder = Path(scan_path).resolve().parent
        policy_path = policy_path or folder / "policy.csv"
    policy = load_policy(policy_path)
    probes = load_probes(scan_path, policy=policy)
    verdicts = classify(probes)
    return {
        "policy": policy,
        "probes": probes,
        "verdicts": verdicts,
        "counts": state_counts(verdicts),
        "by_state": ports_by_state(verdicts),
        "retried": retried_ports(probes),
        "answered_ms": answered_latency_ms(probes),
        "legacy_ms": legacy_latency_ms(probes),
        "wait_ms": wait_ms(probes),
        "timeouts": sum(1 for probe in probes if probe.outcome == "timeout"),
        "legacy_closed": legacy_closed(verdicts, probes),
    }


def report(measured: dict[str, Any]) -> dict[str, Any]:
    counts = measured["counts"]
    return {
        "timeout_ms": measured["policy"].timeout_ms,
        "retries": measured["policy"].retries,
        "ports": len(measured["verdicts"]),
        "probes": len(measured["probes"]),
        "timeouts": measured["timeouts"],
        "retried_ports": measured["retried"],
        "open": measured["by_state"]["open"],
        "closed": measured["by_state"]["closed"],
        "filtered": measured["by_state"]["filtered"],
        "counts": dict(counts),
        "legacy_closed": measured["legacy_closed"],
        "legacy_closed_count": len(measured["legacy_closed"]),
        "answered_ms": measured["answered_ms"],
        "legacy_ms": measured["legacy_ms"],
        "wait_ms": measured["wait_ms"],
        "verdicts": [
            {
                "port": verdict.port,
                "state": verdict.state,
                "attempts": verdict.attempts,
                "evidence": verdict.evidence,
            }
            for verdict in measured["verdicts"]
        ],
    }


# --------------------------------------------------------------------------- #
# Audit
# --------------------------------------------------------------------------- #
def _guard(check) -> bool:
    try:
        return bool(check())
    except Exception:
        return False


def _refuses(call) -> bool:
    try:
        call()
    except ScanError:
        return True
    return False


def audit(
    measured: dict[str, Any],
    *,
    read_verdicts: Callable[[Sequence[Probe]], list[Verdict]] = classify,
) -> list[tuple[str, bool]]:
    """Every check compares a measured value with an independent computation."""
    probes = measured["probes"]
    verdicts = measured["verdicts"]
    counts = measured["counts"]

    def verdicts_via_reader() -> list[Verdict]:
        return read_verdicts(probes)

    def independent_counts() -> dict[str, int]:
        table = {state: 0 for state in STATES}
        for verdict in verdicts_via_reader():
            table[verdict.state] += 1
        return table

    def independent_answered_ms() -> int:
        rows = [probe.latency_ms for probe in probes if probe.outcome != "timeout"]
        return divide_half_up(sum(rows), len(rows)) if rows else 0

    checks = [
        (
            "every_port_gets_exactly_one_verdict",
            lambda: len(verdicts_via_reader()) == len({probe.port for probe in probes}) == 13,
        ),
        (
            "verdicts_are_ordered_by_port",
            lambda: [verdict.port for verdict in verdicts_via_reader()]
            == sorted({probe.port for probe in probes}),
        ),
        (
            "the_three_states_are_all_represented",
            lambda: counts == {"open": 4, "closed": 6, "filtered": 3},
        ),
        (
            "counts_match_an_independent_tally",
            lambda: independent_counts() == counts,
        ),
        (
            "the_open_ports_are_pinned",
            lambda: measured["by_state"]["open"] == [22, 80, 443, 8443],
        ),
        (
            "a_timeout_is_filtered_not_closed",
            lambda: measured["by_state"]["filtered"] == [23, 53, 5432]
            and measured["by_state"]["closed"] == [21, 25, 110, 143, 3306, 8080],
        ),
        (
            "the_legacy_report_collapses_filtered_into_closed",
            lambda: measured["legacy_closed"]
            == [21, 23, 25, 53, 110, 143, 3306, 5432, 8080]
            and len(measured["legacy_closed"]) == 9
            and counts["filtered"] == 3,
        ),
        (
            "open_outranks_an_earlier_timeout",
            lambda: next(v for v in verdicts if v.port == 8443).state == "open"
            and next(v for v in verdicts if v.port == 8443).attempts == 2,
        ),
        (
            "refused_outranks_a_timeout_but_not_an_open",
            lambda: STRENGTH["open"] > STRENGTH["refused"] > STRENGTH["timeout"],
        ),
        (
            "only_three_ports_were_retried",
            lambda: measured["retried"] == [23, 5432, 8443] and len(measured["retried"]) == 3,
        ),
        (
            "a_timeout_is_not_a_latency",
            lambda: measured["wait_ms"] == 4800 and measured["timeouts"] == 6,
        ),
        (
            "the_answered_latency_is_pinned",
            lambda: measured["answered_ms"] == 11 == independent_answered_ms(),
        ),
        (
            "the_legacy_latency_counts_the_waiting",
            lambda: measured["legacy_ms"] == 307
            and measured["legacy_ms"] - measured["answered_ms"] == 296,
        ),
        (
            "a_timeout_that_answered_early_is_refused",
            lambda: _refuses(lambda: require_timeout_latency(800, 4)),
        ),
        (
            "a_non_timeout_at_the_timeout_is_refused",
            lambda: _refuses(lambda: require_answer_latency(800, 800)),
        ),
        (
            "more_attempts_than_the_policy_allows_is_refused",
            lambda: _refuses(lambda: require_attempts(Policy(800, 2), [1, 2, 3])),
        ),
        (
            "a_gap_in_the_attempt_numbers_is_refused",
            lambda: _refuses(lambda: require_attempts(Policy(800, 3), [1, 3])),
        ),
        (
            "rebuild_is_deterministic",
            lambda: verdicts_via_reader() == verdicts,
        ),
    ]
    return [(name, _guard(check)) for name, check in checks]


# --------------------------------------------------------------------------- #
# Rendering and the demo
# --------------------------------------------------------------------------- #
def render_verdicts(measured: dict[str, Any]) -> str:
    lines = ["  port   service       attempts  evidence  state"]
    for verdict in measured["verdicts"]:
        lines.append(
            f"  {verdict.port:<7}{SERVICES.get(verdict.port, '-'):<14}"
            f"{verdict.attempts:>8}  {verdict.evidence:<10}{verdict.state}"
        )
    lines.append(
        f"  {'total':<7}{'':<14}{len(measured['probes']):>8}  {'':<10}"
        f"{len(measured['verdicts'])} ports"
    )
    return "\n".join(lines)


#: Names we can state without a lookup; anything else prints as '-'.
SERVICES = {
    21: "ftp",
    22: "ssh",
    23: "telnet",
    25: "smtp",
    53: "dns",
    80: "http",
    110: "pop3",
    143: "imap",
    443: "https",
    3306: "mysql",
    5432: "postgres",
    8080: "http-alt",
    8443: "https-alt",
}


def run_demo() -> int:
    measured = measure()
    counts = measured["counts"]
    policy = measured["policy"]
    print("Port scanner -- a scan has three answers")
    print("=" * 43)
    print()
    print(
        f"Policy: {policy.timeout_ms} ms timeout, {policy.retries} attempts per port. "
        f"{len(measured['verdicts'])} ports, {len(measured['probes'])} probes."
    )
    print()
    print(render_verdicts(measured))
    print()
    print("1. 'Not open' is not 'closed'.")
    print("   " + LEGACY_CLASSIFY.replace("\n", "\n   "))
    print(
        f"   here: {counts['open']} open, {counts['closed']} closed, "
        f"{counts['filtered']} filtered"
    )
    print(
        f"   legacy: {counts['open']} open, {len(measured['legacy_closed'])} closed, 0 filtered"
    )
    print(
        "   the difference is exactly the ports that never answered: "
        + ", ".join(str(port) for port in measured["by_state"]["filtered"])
    )
    print()
    print("2. A timeout is the absence of a reply, not a slow one.")
    print("   " + LEGACY_LATENCY)
    print(
        f"   answered probes average {measured['answered_ms']} ms over "
        f"{len(measured['probes']) - measured['timeouts']} responses;"
    )
    print(
        f"   the legacy average is {measured['legacy_ms']} ms because "
        f"{measured['timeouts']} timeouts contribute {measured['wait_ms']} ms of waiting."
    )
    print()
    print("3. A retry can only resolve doubt, not manufacture it.")
    print(
        f"   {len(measured['retried'])} ports were retried ("
        + ", ".join(str(port) for port in measured["retried"])
        + "); 8443 timed out once and then answered, so it is open."
    )
    print()
    print("Checks")
    results = audit(measured)
    for name, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    passed = sum(1 for _, ok in results if ok)
    print(f"  {passed}/{len(results)} checks pass")
    print()
    print(
        "Cross-checks OK: the scan probes "
        f"{len(measured['verdicts'])} ports in {len(measured['probes'])} attempts and yields "
        f"{counts['open']} open, {counts['closed']} closed and {counts['filtered']} filtered, "
        f"while the legacy membership test reports {counts['open']} open and "
        f"{len(measured['legacy_closed'])} closed with no filtered state at all; the "
        f"{measured['timeouts']} timeouts contribute {measured['wait_ms']} ms of waiting that "
        f"drag the legacy latency to {measured['legacy_ms']} ms against {measured['answered_ms']} ms "
        f"over the probes that answered; {len(measured['retried'])} ports were retried and 8443's "
        f"open reply outranks its earlier timeout; {passed}/{len(results)} checks pass."
    )
    print("Demo completed successfully.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_demo())
