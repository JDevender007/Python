"""Network and system metrics collection for the Network Monitor.

Uses psutil for interface, connection and bandwidth data. Every collector
degrades gracefully when psutil cannot read a particular counter.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

try:
    import psutil
except ImportError:  # pragma: no cover - psutil is expected in this environment
    psutil = None  # type: ignore[assignment]

LOG = logging.getLogger("netmon")

# Bytes we have already accounted for, per interface, for rate calculation.
_previous_counters: dict[str, Any] = {}
_previous_stamp: float | None = None


def require_psutil() -> None:
    """Raise a clear error when psutil is unavailable."""
    if psutil is None:
        raise RuntimeError(
            "psutil is required: pip install psutil"
        )


@dataclass
class InterfaceSample:
    """One interface counter snapshot."""

    name: str
    ip: str
    send_mbps: float = 0.0
    recv_mbps: float = 0.0
    total_sent_mb: float = 0.0
    total_recv_mb: float = 0.0
    errors_in: int = 0
    errors_out: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ip": self.ip,
            "send_mbps": round(self.send_mbps, 3),
            "recv_mbps": round(self.recv_mbps, 3),
            "total_sent_mb": round(self.total_sent_mb, 2),
            "total_recv_mb": round(self.total_recv_mb, 2),
            "errors_in": self.errors_in,
            "errors_out": self.errors_out,
        }


@dataclass
class MonitorSnapshot:
    """Everything measured in one polling cycle."""

    timestamp: float
    interfaces: list[InterfaceSample] = field(default_factory=list)
    connections: list[dict[str, Any]] = field(default_factory=list)
    top_talkers: list[dict[str, Any]] = field(default_factory=list)
    cpu_percent: float = 0.0
    memory_percent: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "cpu_percent": round(self.cpu_percent, 1),
            "memory_percent": round(self.memory_percent, 1),
            "interfaces": [i.to_dict() for i in self.interfaces],
            "connections": self.connections,
            "top_talkers": self.top_talkers,
        }


def interface_samples(interval: float = 0.0) -> list[InterfaceSample]:
    """Sample per-interface traffic and convert deltas into Mbps rates."""
    global _previous_counters, _previous_stamp

    require_psutil()
    counters = psutil.net_io_counters(pernic=True)
    addrs = psutil.net_if_addrs()
    now = time.time()

    samples: list[InterfaceSample] = []
    for name, counter in counters.items():
        ip = ""
        for entry in addrs.get(name, []):
            if getattr(entry, "family", None) is not None and entry.address and "." in entry.address:
                ip = entry.address
                break

        sample = InterfaceSample(
            name=name,
            ip=ip,
            total_sent_mb=counter.bytes_sent / 1_048_576,
            total_recv_mb=counter.bytes_recv / 1_048_576,
            errors_in=counter.errin,
            errors_out=counter.errout,
        )

        previous = _previous_counters.get(name)
        elapsed = None
        if previous is not None and _previous_stamp is not None:
            elapsed = now - _previous_stamp
        if previous is not None and elapsed and elapsed > 0:
            sample.send_mbps = (counter.bytes_sent - previous.bytes_sent) * 8 / elapsed / 1_000_000
            sample.recv_mbps = (counter.bytes_recv - previous.bytes_recv) * 8 / elapsed / 1_000_000
            # guard against counter resets (interface bounce)
            sample.send_mbps = max(0.0, sample.send_mbps)
            sample.recv_mbps = max(0.0, sample.recv_mbps)

        samples.append(sample)

    _previous_counters = counters
    _previous_stamp = now
    if interval:
        time.sleep(interval)
    return samples


def reset_counters() -> None:
    """Forget cached counters (used between tests and demos)."""
    global _previous_counters, _previous_stamp
    _previous_counters = {}
    _previous_stamp = None


def list_connections(limit: int = 50) -> list[dict[str, Any]]:
    """Return the current connection table, newest/largest first."""
    require_psutil()
    rows: list[dict[str, Any]] = []
    try:
        entries = psutil.net_connections(kind="inet")
    except (psutil.AccessDenied, OSError) as exc:
        LOG.warning("connection table unavailable: %s", exc)
        return rows

    for entry in entries:
        local = f"{entry.laddr.ip}:{entry.laddr.port}" if entry.laddr else "-"
        remote = f"{entry.raddr.ip}:{entry.raddr.port}" if entry.raddr else "-"
        rows.append({
            "local": local,
            "remote": remote,
            "status": entry.status or "-",
            "pid": entry.pid or 0,
        })
        if len(rows) >= limit:
            break
    return rows


def top_talkers(limit: int = 5) -> list[dict[str, Any]]:
    """Processes with the most accumulated network I/O."""
    require_psutil()
    rows: list[dict[str, Any]] = []
    for process in psutil.process_iter(["pid", "name", "io_counters"]):
        try:
            info = process.info
            io = info.get("io_counters")
            if io is None:
                continue
            total_mb = (io.read_bytes + io.write_bytes) / 1_048_576
            if total_mb <= 0:
                continue
            rows.append({
                "pid": info["pid"],
                "name": info["name"] or "?",
                "io_mb": round(total_mb, 2),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
            continue
    rows.sort(key=lambda r: r["io_mb"], reverse=True)
    return rows[:limit]


def take_snapshot(connection_limit: int = 50, talker_limit: int = 5) -> MonitorSnapshot:
    """Collect one full snapshot of host network state."""
    require_psutil()
    snapshot = MonitorSnapshot(
        timestamp=time.time(),
        interfaces=interface_samples(),
        connections=list_connections(connection_limit),
        top_talkers=top_talkers(talker_limit),
        cpu_percent=psutil.cpu_percent(interval=None),
        memory_percent=psutil.virtual_memory().percent,
    )
    return snapshot


def format_snapshot(snapshot: MonitorSnapshot) -> str:
    """Render a snapshot as a human-readable report."""
    lines: list[str] = []
    lines.append(f"CPU {snapshot.cpu_percent}%   Memory {snapshot.memory_percent}%")
    lines.append("")
    lines.append(f"{'INTERFACE':<22}{'IP':<16}{'DOWN Mbps':<12}{'UP Mbps':<12}{'Total MB'}")
    lines.append("-" * 74)
    for iface in snapshot.interfaces:
        lines.append(
            f"{iface.name:<22}{iface.ip:<16}"
            f"{iface.recv_mbps:<12.3f}{iface.send_mbps:<12.3f}"
            f"{iface.total_sent_mb + iface.total_recv_mb:<10.1f}"
        )

    lines.append("")
    lines.append(f"CONNECTIONS ({len(snapshot.connections)})")
    for row in snapshot.connections[:10]:
        lines.append(f"  {row['local']:<24}{row['remote']:<24}{row['status']}")

    lines.append("")
    lines.append("TOP TALKERS (cumulative I/O, MB)")
    for row in snapshot.top_talkers:
        lines.append(f"  {row['name']:<28}pid {row['pid']:<8}{row['io_mb']}")

    return "\n".join(lines)
