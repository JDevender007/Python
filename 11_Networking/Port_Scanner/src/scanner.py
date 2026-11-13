"""Core scanning logic for the Port Scanner.

Only scans targets you own or have explicit permission to test.
"""

from __future__ import annotations

import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from typing import Any

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORTS = (21, 22, 25, 53, 80, 110, 143, 443, 3306, 5432, 8000, 8080)

# Well-known ports we can name without any external lookup.
SERVICE_NAMES: dict[int, str] = {
    21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp", 53: "dns",
    80: "http", 110: "pop3", 143: "imap", 443: "https", 445: "smb",
    3306: "mysql", 5432: "postgres", 6379: "redis", 8000: "http-alt",
    8080: "http-proxy", 8443: "https-alt", 27017: "mongodb",
}


@dataclass(frozen=True)
class ScanResult:
    """Outcome of a single port probe."""

    host: str
    port: int
    open: bool
    service: str
    latency_ms: float
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        """JSON-friendly representation."""
        return asdict(self)


def probe_port(host: str, port: int, timeout: float = 1.0) -> ScanResult:
    """Try a TCP connection to one port and describe the result."""
    service = SERVICE_NAMES.get(port, "unknown")
    start = socket.getdefaulttimeout()
    try:
        import time

        began = time.perf_counter()
        with socket.create_connection((host, port), timeout=timeout):
            elapsed = (time.perf_counter() - began) * 1000
        return ScanResult(host, port, True, service, round(elapsed, 2))
    except (ConnectionRefusedError, OSError) as exc:
        return ScanResult(host, port, False, service, 0.0, error=type(exc).__name__)
    finally:
        socket.setdefaulttimeout(start)


def parse_ports(spec: str) -> list[int]:
    """Parse a port specification such as '80,443' or '1-1024' or mixed."""
    ports: set[int] = set()
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            start_s, _, end_s = chunk.partition("-")
            start, end = int(start_s), int(end_s)
            if start > end:
                start, end = end, start
            if end - start > 10_000:
                raise ValueError("port range too large (max 10000 ports)")
            ports.update(range(start, end + 1))
        else:
            ports.add(int(chunk))
    for p in ports:
        if not 1 <= p <= 65535:
            raise ValueError(f"port out of range: {p}")
    return sorted(ports)


def scan(
    host: str = DEFAULT_HOST,
    ports: list[int] | None = None,
    *,
    timeout: float = 1.0,
    workers: int = 100,
) -> list[ScanResult]:
    """Scan a set of ports concurrently and return results ordered by port."""
    targets = ports if ports is not None else list(DEFAULT_PORTS)
    if not targets:
        return []
    if len(targets) > 10_000:
        raise ValueError("too many ports (max 10000)")

    results: list[ScanResult] = []
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(targets)))) as pool:
        futures = {pool.submit(probe_port, host, p, timeout): p for p in targets}
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda r: r.port)
    return results


def summarize(results: list[ScanResult]) -> dict[str, Any]:
    """Aggregate counts for reporting."""
    open_ports = [r for r in results if r.open]
    return {
        "host": results[0].host if results else "",
        "scanned": len(results),
        "open": len(open_ports),
        "closed": len(results) - len(open_ports),
        "open_ports": [r.port for r in open_ports],
    }
