"""Web server access-log analysis: loading, validation, and reporting — offline.

Reads a CSV of HTTP requests (timestamp, method, path, status, bytes,
duration, client, session), validates it, and produces a TrafficReport with
request totals, status-class breakdowns, error rates, top paths, hourly and
daily traffic profiles, slowest endpoints, and top clients. Local file
analysis only - no network, no APIs.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

LOG = logging.getLogger("traffic.analyzer")

REQUIRED_COLUMNS = ("timestamp", "method", "path", "status", "bytes",
                    "duration_ms", "client_ip", "session_id")
ALLOWED_METHODS = ("GET", "POST", "PUT", "DELETE", "HEAD", "PATCH", "OPTIONS")
STATUS_CLASSES = ("2xx", "3xx", "4xx", "5xx")


class TrafficError(RuntimeError):
    """Raised for missing files, bad schemas, and invalid log rows."""


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def format_bytes(count: float) -> str:
    """Human-readable byte size (B / KB / MB / GB)."""
    value = float(count)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} GB"  # pragma: no cover - unreachable


def load_traffic(path: str | Path, since: str | None = None,
                 until: str | None = None) -> pd.DataFrame:
    """Load an access-log CSV, validate it, and return a cleaned frame."""
    source = Path(path)
    if not source.is_file():
        raise TrafficError(f"file not found: {source}")
    try:
        frame = pd.read_csv(source)
    except Exception as exc:
        raise TrafficError(f"could not parse {source.name}: {exc}") from exc

    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise TrafficError(
            f"missing column(s): {', '.join(missing)} "
            f"(required: {', '.join(REQUIRED_COLUMNS)})"
        )
    if frame.empty:
        raise TrafficError(f"no rows in {source.name}")

    frame = frame.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    if frame["timestamp"].isna().any():
        raise TrafficError("unparseable timestamp value(s)")

    frame["method"] = frame["method"].astype(str).str.strip().str.upper()
    bad_methods = sorted(set(frame["method"]) - set(ALLOWED_METHODS))
    if bad_methods:
        raise TrafficError(
            f"unknown method(s): {', '.join(bad_methods)} "
            f"(allowed: {', '.join(ALLOWED_METHODS)})"
        )

    frame["path"] = frame["path"].astype(str).str.strip()
    if frame["path"].eq("").any() or frame["path"].str.lower().eq("nan").any():
        raise TrafficError("empty path value(s)")
    if not frame["path"].str.startswith("/").all():
        raise TrafficError("every path must start with '/'")

    frame["status"] = pd.to_numeric(frame["status"], errors="coerce")
    if frame["status"].isna().any():
        raise TrafficError("column 'status' contains non-numeric values")
    if not frame["status"].between(100, 599).all() or (frame["status"] % 1 != 0).any():
        raise TrafficError("status must be whole numbers in 100..599")
    frame["status"] = frame["status"].astype(int)

    for column in ("bytes", "duration_ms"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if frame[column].isna().any():
            raise TrafficError(f"column {column!r} contains non-numeric values")
        if (frame[column] < 0).any():
            raise TrafficError(f"column {column!r} must be non-negative")

    for column in ("client_ip", "session_id"):
        values = frame[column].astype(str).str.strip()
        if values.eq("").any() or values.str.lower().eq("nan").any():
            raise TrafficError(f"empty {column!r} value(s)")
        frame[column] = values

    # optional inclusive date window (YYYY-MM-DD)
    since_ts = _parse_day(since, "--since") if since is not None else None
    until_ts = _parse_day(until, "--until") if until is not None else None
    if since_ts is not None and until_ts is not None and since_ts > until_ts:
        raise TrafficError("--since must be on or before --until")
    if since_ts is not None:
        frame = frame[frame["timestamp"] >= since_ts]
    if until_ts is not None:
        frame = frame[frame["timestamp"] < until_ts + pd.Timedelta(1, unit="D")]
    if frame.empty:
        raise TrafficError("no requests in the requested date range")

    frame = frame.sort_values("timestamp").reset_index(drop=True)
    LOG.info("loaded %d requests from %s", len(frame), source.name)
    return frame


_DAY_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _parse_day(value: str, flag: str) -> pd.Timestamp:
    """Parse a strict YYYY-MM-DD date (no lenient dateutil guessing)."""
    text = str(value).strip()
    if not _DAY_RE.fullmatch(text):
        raise TrafficError(f"{flag} must look like YYYY-MM-DD: {value!r}")
    try:
        parsed = pd.Timestamp(text)
    except Exception as exc:
        raise TrafficError(f"{flag} must look like YYYY-MM-DD: {value!r}") from exc
    if pd.isna(parsed):
        raise TrafficError(f"{flag} must look like YYYY-MM-DD: {value!r}")
    return parsed.normalize()


# --------------------------------------------------------------------------- #
# Report model
# --------------------------------------------------------------------------- #
@dataclass
class TrafficReport:
    """Aggregated view over a validated request DataFrame."""

    frame: pd.DataFrame
    requests: int = 0
    unique_ips: int = 0
    unique_sessions: int = 0
    bytes_total: int = 0
    avg_duration_ms: float = 0.0
    window_start: str = ""
    window_end: str = ""
    status_classes: dict[str, int] = field(default_factory=dict)
    error_rate_pct: float = 0.0
    top_paths: pd.DataFrame = field(default_factory=pd.DataFrame)
    slowest_paths: pd.DataFrame = field(default_factory=pd.DataFrame)
    top_ips: pd.DataFrame = field(default_factory=pd.DataFrame)
    hourly: pd.Series = field(default_factory=pd.Series)
    daily: pd.Series = field(default_factory=pd.Series)
    peak_hour: int = -1

    @property
    def bytes_human(self) -> str:
        return format_bytes(self.bytes_total)

    @property
    def requests_per_session(self) -> float:
        return round(self.requests / self.unique_sessions, 2) if self.unique_sessions else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "requests": self.requests,
            "unique_ips": self.unique_ips,
            "unique_sessions": self.unique_sessions,
            "requests_per_session": self.requests_per_session,
            "bytes_total": self.bytes_total,
            "bytes_human": self.bytes_human,
            "avg_duration_ms": round(self.avg_duration_ms, 1),
            "window": [self.window_start, self.window_end],
            "status_classes": dict(self.status_classes),
            "error_rate_pct": round(self.error_rate_pct, 2),
            "peak_hour": self.peak_hour,
            "top_paths": [
                {"path": str(idx), "hits": int(row["hits"]),
                 "share_pct": round(float(row["share_pct"]), 2),
                 "avg_ms": round(float(row["avg_ms"]), 1)}
                for idx, row in self.top_paths.iterrows()
            ],
            "slowest_paths": [
                {"path": str(idx), "avg_ms": round(float(row["avg_ms"]), 1),
                 "hits": int(row["hits"])}
                for idx, row in self.slowest_paths.iterrows()
            ],
            "hourly": {str(int(h)): int(v) for h, v in self.hourly.items()},
            "daily": {str(pd.Timestamp(d).date()): int(v) for d, v in self.daily.items()},
        }


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #
def status_class(code: int) -> str:
    return f"{int(code) // 100}xx"


def analyze(frame: pd.DataFrame, top: int = 5) -> TrafficReport:
    """Aggregate a validated frame into a TrafficReport."""
    if top < 1:
        raise TrafficError("top must be >= 1")

    report = TrafficReport(frame=frame)
    report.requests = len(frame)
    report.unique_ips = int(frame["client_ip"].nunique())
    report.unique_sessions = int(frame["session_id"].nunique())
    report.bytes_total = int(frame["bytes"].sum())
    report.avg_duration_ms = float(frame["duration_ms"].mean())
    report.window_start = str(frame["timestamp"].min())
    report.window_end = str(frame["timestamp"].max())

    classes = frame["status"].map(status_class).value_counts()
    report.status_classes = {name: int(classes.get(name, 0)) for name in STATUS_CLASSES}
    errors = report.status_classes.get("4xx", 0) + report.status_classes.get("5xx", 0)
    report.error_rate_pct = errors / report.requests * 100

    path_table = frame.groupby("path").agg(
        hits=("path", "count"),
        avg_ms=("duration_ms", "mean"),
        total_bytes=("bytes", "sum"),
    ).sort_values("hits", ascending=False)
    path_table["share_pct"] = path_table["hits"] / report.requests * 100
    path_table["avg_ms"] = path_table["avg_ms"].round(1)
    report.top_paths = path_table.head(top)
    report.slowest_paths = path_table.sort_values("avg_ms", ascending=False).head(top)

    ip_table = frame["client_ip"].value_counts().head(top).rename("requests")
    report.top_ips = ip_table.to_frame()

    hourly = frame["timestamp"].dt.hour.value_counts().sort_index()
    report.hourly = hourly.reindex(range(24), fill_value=0)
    report.peak_hour = int(report.hourly.idxmax()) if report.requests else -1

    daily = frame["timestamp"].dt.normalize().value_counts().sort_index()
    report.daily = daily

    LOG.info("analysed %d requests (%s errors)", report.requests,
             report.status_classes.get("4xx", 0) + report.status_classes.get("5xx", 0))
    return report


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def render_report(report: TrafficReport) -> str:
    """Human-readable traffic report used by the CLI and demo."""
    lines = [
        "WEB TRAFFIC ANALYSIS",
        "=" * 68,
        f"Window     : {report.window_start} .. {report.window_end}",
        f"Requests   : {report.requests:,}   "
        f"sessions {report.unique_sessions:,}   clients {report.unique_ips:,}",
        f"Per session: {report.requests_per_session}   "
        f"bandwidth {report.bytes_human}   "
        f"avg response {report.avg_duration_ms:.0f} ms",
        f"Errors     : {report.error_rate_pct:.1f}% "
        f"(4xx {report.status_classes.get('4xx', 0)}, "
        f"5xx {report.status_classes.get('5xx', 0)})",
        "",
        "Status classes:",
    ]
    for name in STATUS_CLASSES:
        count = report.status_classes.get(name, 0)
        share = count / report.requests * 100
        bar = "#" * max(1, round(share / 2)) if count else ""
        lines.append(f"  {name}  {count:>5} ({share:5.1f}%)  {bar}")

    lines += ["", f"Top {len(report.top_paths)} paths by hits:"]
    for path, row in report.top_paths.iterrows():
        lines.append(f"  {str(path):<32}{int(row['hits']):>6} hits "
                     f"({row['share_pct']:4.1f}%)  {row['avg_ms']:>6.1f} ms")

    lines += ["", f"Slowest paths (avg response):"]
    for path, row in report.slowest_paths.iterrows():
        lines.append(f"  {str(path):<32}{row['avg_ms']:>7.1f} ms  "
                     f"({int(row['hits'])} hits)")

    lines += ["", f"Hourly profile (peak {report.peak_hour:02d}:00):"]
    peak = max(1, int(report.hourly.max()))
    for hour, count in report.hourly.items():
        bar = "#" * max(1, round(int(count) / peak * 30)) if count else ""
        lines.append(f"  {hour:02d}:00  {int(count):>5}  {bar}")

    lines += ["", "Busiest days:"]
    for day, count in report.daily.sort_values(ascending=False).head(5).items():
        lines.append(f"  {pd.Timestamp(day).date()}  {int(count):>5} requests")

    lines += ["", "Top clients by requests:"]
    for ip, row in report.top_ips.iterrows():
        lines.append(f"  {str(ip):<18}{int(row['requests']):>6} requests")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
DEMO_CSV = Path(__file__).resolve().parent.parent / "data" / "traffic_sample.csv"


def run_demo(csv_path: Path | None = None) -> int:
    """Analyse the bundled sample access log — fully offline."""
    print("=" * 68)
    print(" WEB TRAFFIC ANALYZER - offline demo")
    print(" Bundled sample access log; no network, no servers.")
    print("=" * 68)

    source = csv_path or DEMO_CSV
    if not source.is_file():
        raise TrafficError(f"bundled sample not found: {source}")

    frame = load_traffic(source)
    print(f"\nLoaded {len(frame):,} requests from {source.name}")

    report = analyze(frame, top=5)
    print()
    print(render_report(report))

    # --- cross-checks the demo asserts ---------------------------------- #
    assert sum(report.status_classes.values()) == report.requests, \
        "status classes must partition all requests"
    errors = report.status_classes["4xx"] + report.status_classes["5xx"]
    assert abs(report.error_rate_pct - errors / report.requests * 100) < 1e-9, \
        "error rate mismatch"
    assert int(report.hourly.sum()) == report.requests, "hourly profile must sum to n"
    assert int(report.daily.sum()) == report.requests, "daily profile must sum to n"
    assert report.bytes_total == int(frame["bytes"].sum()), "bandwidth mismatch"
    top_path = report.top_paths.index[0]
    manual = int((frame["path"] == top_path).sum())
    assert int(report.top_paths.iloc[0]["hits"]) == manual, "top path count mismatch"
    print(f"\nCross-checks OK: statuses partition {report.requests:,} requests, "
          f"profiles sum to n (error rate {report.error_rate_pct:.1f}%)")

    # date-window filtering proves the --since/--until path
    day_one = load_traffic(source, since="2025-06-01", until="2025-06-01")
    assert len(day_one) < len(frame), "single-day window should be smaller"
    assert (day_one["timestamp"].dt.date == pd.Timestamp("2025-06-01").date()).all()
    print(f"Filtered to 2025-06-01: {len(day_one)} requests, "
          f"{day_one['session_id'].nunique()} sessions")

    print("\nDemo completed successfully.")
    return 0
