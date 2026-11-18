"""Log Monitor: parse, aggregate, and alert on log files - fully offline.

Parses both structured log lines (``timestamp LEVEL service=... msg="..."``)
and unstructured/bracketed lines (``timestamp LEVEL [service] message``),
aggregates error rates per service, raises threshold alerts, and renders a
top-offenders report. Local files only - no network, no daemons, no log
shippers. Every sample ships in ``data/``.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------- #
# Constants and validation
# --------------------------------------------------------------------------- #
LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
ERROR_LEVELS = frozenset({"ERROR", "CRITICAL"})

# 2025-03-10 09:00:00 INFO service=api-gateway msg="GET /health" duration=12ms
STRUCTURED_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+"
    r"(?P<level>[A-Za-z]+)\s+"
    r"service=(?P<service>\S+)\s+"
    r'msg="(?P<msg>[^"]*)"'
    r"(?P<attrs>.*)$"
)
# 2025-03-10 09:30:00 ERROR [payment-adapter] timeout talking to upstream
UNSTRUCTURED_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+"
    r"(?P<level>[A-Za-z]+)\s+"
    r"\[(?P<service>[^\]]+)\]\s+"
    r"(?P<msg>.+)$"
)
# Fallback used only to report *why* a line failed (missing vs bad level).
GENERIC_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(?P<level>[A-Za-z]+)\b"
)
ATTR_RE = re.compile(r"(\w+)=([^\s]+)")


class LogError(RuntimeError):
    """Raised for missing files, malformed lines, and bad arguments."""


@dataclass(frozen=True)
class LogRecord:
    """One parsed log line."""

    timestamp: datetime
    level: str
    service: str
    message: str
    source: str = ""
    attributes: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    @property
    def is_error(self) -> bool:
        return self.level in ERROR_LEVELS

    @property
    def minute(self) -> str:
        """Minute bucket key, e.g. '2025-03-10 09:00'."""
        return self.timestamp.strftime("%Y-%m-%d %H:%M")


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
def parse_line(text: str, source: str = "", line_no: int = 0) -> LogRecord:
    """Parse one structured or unstructured log line into a LogRecord."""
    where = f"{source}:{line_no}" if source else f"line {line_no}"
    stripped = text.strip()
    if not stripped:
        raise LogError(f"{where}: empty log line")

    match = STRUCTURED_RE.match(stripped)
    if match:
        level = match.group("level").upper()
        if level not in LEVELS:
            raise LogError(f"{where}: unknown log level {match.group('level')!r}")
        service = match.group("service")
        if not service:
            raise LogError(f"{where}: missing service")
        message = match.group("msg")
        attributes = tuple(ATTR_RE.findall(match.group("attrs")))
        try:
            stamp = datetime.strptime(match.group("ts"), "%Y-%m-%d %H:%M:%S")
        except ValueError as exc:
            raise LogError(f"{where}: invalid timestamp") from exc
        return LogRecord(stamp, level, service, message, source, attributes)

    match = UNSTRUCTURED_RE.match(stripped)
    if match:
        level = match.group("level").upper()
        if level not in LEVELS:
            raise LogError(f"{where}: unknown log level {match.group('level')!r}")
        service = match.group("service").strip()
        if not service:
            raise LogError(f"{where}: missing service")
        try:
            stamp = datetime.strptime(match.group("ts"), "%Y-%m-%d %H:%M:%S")
        except ValueError as exc:
            raise LogError(f"{where}: invalid timestamp") from exc
        return LogRecord(stamp, level, service, match.group("msg"), source)

    generic = GENERIC_RE.match(stripped)
    if generic:
        level = generic.group("level")
        if level.upper() not in LEVELS:
            raise LogError(f"{where}: unknown log level {level!r}")
        raise LogError(f"{where}: unrecognized line format: {stripped[:48]!r}")
    raise LogError(f"{where}: missing timestamp: {stripped[:48]!r}")


def parse_file(path: str | Path, strict: bool = True) -> tuple[list[LogRecord], int]:
    """Parse a log file -> (records, skipped).

    Blank lines are always ignored. In strict mode the first malformed line
    raises; otherwise it is skipped and counted.
    """
    source = Path(path)
    if not source.is_file():
        raise LogError(f"file not found: {source}")
    try:
        raw = source.read_text(encoding="utf-8")
    except OSError as exc:
        raise LogError(f"could not read {source.name}: {exc}") from exc

    records: list[LogRecord] = []
    skipped = 0
    for line_no, line in enumerate(raw.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(parse_line(line, source=source.name, line_no=line_no))
        except LogError:
            if strict:
                raise
            skipped += 1
    return records, skipped


def parse_many(paths: list[Path], strict: bool = True) -> tuple[list[LogRecord], int]:
    """Parse several files in order; totals (records, skipped)."""
    records: list[LogRecord] = []
    skipped = 0
    for path in paths:
        chunk, bad = parse_file(path, strict=strict)
        records.extend(chunk)
        skipped += bad
    return records, skipped


# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #
@dataclass
class ServiceSummary:
    """Per-service counters and error rate."""

    service: str
    total: int = 0
    errors: int = 0
    level_counts: dict[str, int] = field(default_factory=dict)

    @property
    def error_rate(self) -> float:
        return self.errors / self.total if self.total else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "service": self.service,
            "total": self.total,
            "errors": self.errors,
            "error_rate": round(self.error_rate, 4),
            "levels": dict(sorted(self.level_counts.items())),
        }


def error_rate(records: list[LogRecord]) -> float:
    """Fraction of ERROR/CRITICAL records (0.0 for an empty input)."""
    if not records:
        return 0.0
    errors = sum(1 for r in records if r.is_error)
    return errors / len(records)


def summarize(records: list[LogRecord]) -> dict[str, ServiceSummary]:
    """Aggregate records into per-service summaries (keyed by service name)."""
    summaries: dict[str, ServiceSummary] = {}
    for record in records:
        summary = summaries.setdefault(record.service,
                                       ServiceSummary(service=record.service))
        summary.total += 1
        summary.level_counts[record.level] = \
            summary.level_counts.get(record.level, 0) + 1
        if record.is_error:
            summary.errors += 1
    return dict(sorted(summaries.items()))


def threshold_alerts(summaries: dict[str, ServiceSummary],
                     threshold: float = 0.2,
                     min_samples: int = 1) -> list[ServiceSummary]:
    """Services whose error rate is >= threshold with enough samples."""
    if not 0.0 <= threshold <= 1.0:
        raise LogError(f"threshold must be in 0..1, got {threshold}")
    if min_samples < 1:
        raise LogError(f"min_samples must be >= 1, got {min_samples}")
    hits = [s for s in summaries.values()
            if s.total >= min_samples and s.error_rate >= threshold]
    hits.sort(key=lambda s: (-s.error_rate, s.service))
    return hits


def top_offenders(summaries: dict[str, ServiceSummary],
                  n: int = 5) -> list[ServiceSummary]:
    """Top-n services by error count (ties broken by name ascending)."""
    if n < 1:
        raise LogError(f"n must be >= 1, got {n}")
    ordered = sorted(summaries.values(),
                     key=lambda s: (-s.errors, s.service))
    return ordered[:n]


def rate_by_minute(records: list[LogRecord]) -> dict[str, float]:
    """Error rate per minute bucket, keyed 'YYYY-MM-DD HH:MM'."""
    totals: Counter[str] = Counter()
    errors: Counter[str] = Counter()
    for record in records:
        totals[record.minute] += 1
        if record.is_error:
            errors[record.minute] += 1
    return {minute: errors[minute] / count
            for minute, count in sorted(totals.items())}


# --------------------------------------------------------------------------- #
# Report rendering
# --------------------------------------------------------------------------- #
def render_report(records: list[LogRecord],
                  summaries: dict[str, ServiceSummary],
                  alerts: list[ServiceSummary],
                  top: list[ServiceSummary],
                  threshold: float,
                  min_samples: int,
                  skipped: int = 0) -> str:
    """Human-readable report used by the CLI and the demo."""
    level_totals: Counter[str] = Counter(r.level for r in records)
    overall = error_rate(records)
    lines = [
        "LOG MONITOR REPORT",
        "=" * 68,
        f"Records      : {len(records)} parsed, {skipped} skipped",
        f"Services     : {len(summaries)}",
        "Levels       : " + " | ".join(
            f"{lvl} {level_totals.get(lvl, 0)}" for lvl in LEVELS),
        f"Overall rate : {overall:.3f} "
        f"({sum(1 for r in records if r.is_error)} errors)",
        "",
        "Per-service summary:",
        f"  {'service':<18} {'total':>5} {'errors':>6} {'rate':>6}  levels",
    ]
    for summary in summaries.values():
        levels = " ".join(f"{k} {v}" for k, v in
                          sorted(summary.level_counts.items()))
        lines.append(f"  {summary.service:<18} {summary.total:>5} "
                     f"{summary.errors:>6} {summary.error_rate:>6.3f}  {levels}")

    lines += ["",
              f"Threshold alerts (rate >= {threshold:.2f}, "
              f"samples >= {min_samples}):"]
    if alerts:
        for summary in alerts:
            lines.append(f"  ! {summary.service:<18} "
                         f"{summary.error_rate:.3f} "
                         f"({summary.errors}/{summary.total})")
    else:
        lines.append("  (none)")

    lines += ["", "Top offenders (by error count):"]
    for index, summary in enumerate(top, start=1):
        lines.append(f"  {index}. {summary.service:<18} "
                     f"{summary.errors} errors "
                     f"({summary.total} records, rate {summary.error_rate:.3f})")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Bundled data + offline demo
# --------------------------------------------------------------------------- #
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
BUNDLED_LOGS = (DATA_DIR / "app.log", DATA_DIR / "legacy.log")

# Expected values for the bundled sample (asserted by the demo).
EXPECTED_RECORDS = 80
EXPECTED_ERRORS = 17
EXPECTED_SERVICES = {
    "api-gateway", "auth", "billing", "cache", "payment-adapter", "worker",
}
EXPECTED_ALERTS = {"billing", "payment-adapter"}
DEMO_THRESHOLD = 0.30
DEMO_MIN_SAMPLES = 8


def load_bundled(logs: tuple[Path, ...] | None = None) -> tuple[list[LogRecord], int]:
    """Parse the bundled demo logs (strict); raise if any are missing."""
    paths = list(logs or BUNDLED_LOGS)
    missing = [p for p in paths if not p.is_file()]
    if missing:
        raise LogError(f"bundled sample not found: {missing[0]}")
    return parse_many(paths, strict=True)


def run_demo(logs: tuple[Path, ...] | None = None) -> int:
    """Parse the bundled logs, aggregate, alert, and self-check - offline."""
    print("=" * 68)
    print(" LOG MONITOR - offline demo")
    print(" Bundled log files; stdlib parsing; no network, no daemons.")
    print("=" * 68)

    records, skipped = load_bundled(logs)
    print(f"\nParsed {len(records)} records from "
          f"{len(logs or BUNDLED_LOGS)} bundled log file(s)")

    summaries = summarize(records)
    alerts = threshold_alerts(summaries, DEMO_THRESHOLD, DEMO_MIN_SAMPLES)
    top = top_offenders(summaries, 3)
    minute_rates = rate_by_minute(records)
    print()
    print(render_report(records, summaries, alerts, top,
                        DEMO_THRESHOLD, DEMO_MIN_SAMPLES, skipped))

    # --- cross-checks the demo asserts ----------------------------------- #
    assert skipped == 0, "bundled logs must parse cleanly"
    assert len(records) == EXPECTED_RECORDS, "unexpected record count"
    errors = sum(1 for r in records if r.is_error)
    assert errors == EXPECTED_ERRORS, "unexpected error count"
    assert set(summaries) == EXPECTED_SERVICES, "unexpected service set"
    assert sum(s.total for s in summaries.values()) == len(records), \
        "per-service totals must sum to all records"
    assert abs(error_rate(records) - EXPECTED_ERRORS / EXPECTED_RECORDS) < 1e-9
    assert {s.service for s in alerts} == EXPECTED_ALERTS, \
        "alert set mismatch at the demo threshold"
    assert all(a.error_rate >= DEMO_THRESHOLD for a in alerts)
    assert top[0].service == "billing" and top[0].errors == 7, \
        "billing must be the top offender with 7 errors"
    assert [s.service for s in top] == ["billing", "payment-adapter", "auth"], \
        "top offenders ordering mismatch"
    assert minute_rates and all(0.0 <= r <= 1.0 for r in minute_rates.values())

    # deterministic re-parse: identical summaries
    again, skipped2 = load_bundled(logs)
    assert skipped2 == 0
    assert summarize(again) == summaries, "re-parse not deterministic"
    assert [(r.timestamp, r.level, r.service) for r in again] == \
           [(r.timestamp, r.level, r.service) for r in records], \
        "record order changed between parses"

    alert_names = ", ".join(s.service for s in alerts)
    print(f"\nMinute buckets: {len(minute_rates)}, "
          f"overall error rate {error_rate(records):.3f}")
    print(f"Cross-checks OK: {len(records)} records, {errors} errors, "
          f"{len(alerts)} alert(s) [{alert_names}], top offender "
          f"{top[0].service} ({top[0].errors} errors), deterministic re-parse")
    print("Demo completed successfully.")
    return 0
