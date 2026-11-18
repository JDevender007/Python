"""A SQLite-backed IoT device registry - offline.

Devices live in a single SQLite table with a validated schema, and every
status transition is appended to an event table so a device's history is
auditable. All state is local: an in-memory database for the demo or a
file on disk for the CLI. No network, no broker, no API keys.

Public API
----------
connect              open a database and create the schema
add_device           insert a validated device
get_device           fetch one device or raise
list_devices         filter by kind / room / status
update_status        change status and append an event
remove_device        delete a device and its events
registry_stats       counts by kind, status and room
render_report        human-readable listing
run_demo             offline demo with self-checks
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SEED_FILE = DATA_DIR / "devices.json"

KINDS = ("gateway", "sensor", "actuator", "camera")
STATUSES = ("online", "offline", "error", "maintenance")
DEFAULT_STATUS = "offline"
ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,31}$")
FIRMWARE_RE = re.compile(r"^\d+\.\d+\.\d+$")
MIN_SEED_DEVICES = 4

SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    kind        TEXT NOT NULL CHECK (kind IN ('gateway','sensor','actuator','camera')),
    room        TEXT NOT NULL,
    firmware    TEXT NOT NULL,
    status      TEXT NOT NULL CHECK (status IN ('online','offline','error','maintenance')),
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE TABLE IF NOT EXISTS device_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id   TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    status      TEXT NOT NULL,
    changed_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
"""


class RegistryError(RuntimeError):
    """Raised for invalid devices, bad queries or corrupted seed data."""


# --------------------------------------------------------------------------- #
# Schema and connection
# --------------------------------------------------------------------------- #
def connect(path: Path | str | None = None) -> sqlite3.Connection:
    """Open a database (``None`` = in-memory) and ensure the schema exists."""
    if path is None:
        connection = sqlite3.connect(":memory:")
    else:
        target = Path(path)
        if target.parent and not target.parent.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(target))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA)
    return connection


# --------------------------------------------------------------------------- #
# Validation helpers
# --------------------------------------------------------------------------- #
def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RegistryError(f"{field} must be a non-empty string")
    return value.strip()


def _check_id(device_id: object) -> str:
    text = _text(device_id, "device id")
    if not ID_RE.match(text):
        raise RegistryError(
            f"invalid device id {text!r}: use 2-32 lowercase letters, digits "
            f"or hyphens, starting with a letter")
    return text


def _check_kind(kind: object) -> str:
    text = _text(kind, "kind")
    if text not in KINDS:
        raise RegistryError(f"invalid kind {text!r} "
                            f"(choose from {', '.join(KINDS)})")
    return text


def _check_status(status: object) -> str:
    text = _text(status, "status")
    if text not in STATUSES:
        raise RegistryError(f"invalid status {text!r} "
                            f"(choose from {', '.join(STATUSES)})")
    return text


def _check_firmware(firmware: object) -> str:
    text = _text(firmware, "firmware")
    if not FIRMWARE_RE.match(text):
        raise RegistryError(f"invalid firmware {text!r}: expected MAJOR."
                            f"MINOR.PATCH")
    return text


# --------------------------------------------------------------------------- #
# CRUD
# --------------------------------------------------------------------------- #
def add_device(connection: sqlite3.Connection, *, device_id: str, name: str,
               kind: str, room: str, firmware: str,
               status: str = DEFAULT_STATUS) -> dict:
    """Validate and insert one device, returning it as a dict."""
    row = {
        "id": _check_id(device_id),
        "name": _text(name, "name"),
        "kind": _check_kind(kind),
        "room": _text(room, "room"),
        "firmware": _check_firmware(firmware),
        "status": _check_status(status),
    }
    try:
        connection.execute(
            "INSERT INTO devices (id, name, kind, room, firmware, status) "
            "VALUES (:id, :name, :kind, :room, :firmware, :status)", row)
    except sqlite3.IntegrityError as exc:
        raise RegistryError(f"device id already exists: {row['id']}") from exc
    connection.commit()
    return get_device(connection, row["id"])


def get_device(connection: sqlite3.Connection, device_id: str) -> dict:
    text = _check_id(device_id)
    row = connection.execute("SELECT * FROM devices WHERE id = ?",
                             (text,)).fetchone()
    if row is None:
        raise RegistryError(f"unknown device: {text}")
    return dict(row)


def list_devices(connection: sqlite3.Connection, kind: str | None = None,
                 room: str | None = None,
                 status: str | None = None) -> list[dict]:
    query = "SELECT * FROM devices"
    clauses: list[str] = []
    params: list[str] = []
    if kind is not None:
        clauses.append("kind = ?")
        params.append(_check_kind(kind))
    if status is not None:
        clauses.append("status = ?")
        params.append(_check_status(status))
    if room is not None:
        clauses.append("room = ?")
        params.append(_text(room, "room"))
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY id"
    return [dict(row) for row in connection.execute(query, params)]


def update_status(connection: sqlite3.Connection, device_id: str,
                  status: str) -> dict:
    """Set a new status and append a device event."""
    device = get_device(connection, device_id)
    target = _check_status(status)
    if device["status"] == target:
        return device
    connection.execute("UPDATE devices SET status = ? WHERE id = ?",
                       (target, device["id"]))
    connection.execute("INSERT INTO device_events (device_id, status) "
                       "VALUES (?, ?)", (device["id"], target))
    connection.commit()
    return get_device(connection, device["id"])


def remove_device(connection: sqlite3.Connection, device_id: str) -> dict:
    device = get_device(connection, device_id)
    connection.execute("DELETE FROM device_events WHERE device_id = ?",
                       (device["id"],))
    connection.execute("DELETE FROM devices WHERE id = ?", (device["id"],))
    connection.commit()
    return device


def device_events(connection: sqlite3.Connection,
                  device_id: str) -> list[dict]:
    device = get_device(connection, device_id)
    rows = connection.execute(
        "SELECT status, changed_at FROM device_events WHERE device_id = ? "
        "ORDER BY id", (device["id"],))
    return [dict(row) for row in rows]


# --------------------------------------------------------------------------- #
# Seed data
# --------------------------------------------------------------------------- #
def load_seed(path: Path | str | None = None) -> list[dict]:
    target = Path(path) if path is not None else SEED_FILE
    if not target.is_file():
        raise RegistryError(f"seed file not found: {target}")
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RegistryError(f"seed file is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict) or "devices" not in payload:
        raise RegistryError("seed file must contain a 'devices' list")
    rows = payload["devices"]
    if not isinstance(rows, list) or len(rows) < MIN_SEED_DEVICES:
        raise RegistryError(f"seed needs at least {MIN_SEED_DEVICES} devices")
    seen: set[str] = set()
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise RegistryError(f"seed device {index} is not an object")
        missing = {"id", "name", "kind", "room", "firmware"} - set(row)
        if missing:
            raise RegistryError(f"seed device {index} is missing "
                                f"{sorted(missing)}")
        _check_id(row["id"])
        _check_kind(row["kind"])
        _check_firmware(row["firmware"])
        if row["id"] in seen:
            raise RegistryError(f"duplicate seed device id: {row['id']}")
        seen.add(row["id"])
    return rows


def seed_registry(connection: sqlite3.Connection,
                  path: Path | str | None = None) -> int:
    rows = load_seed(path)
    added = 0
    for row in rows:
        try:
            connection.execute(
                "INSERT INTO devices (id, name, kind, room, firmware, status) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (row["id"], row["name"], row["kind"], row["room"],
                 row["firmware"], row.get("status", DEFAULT_STATUS)))
            added += 1
        except sqlite3.IntegrityError:
            continue
    connection.commit()
    return added


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def registry_stats(connection: sqlite3.Connection) -> dict:
    total = connection.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
    by_kind = {row[0]: row[1] for row in connection.execute(
        "SELECT kind, COUNT(*) FROM devices GROUP BY kind ORDER BY kind")}
    by_status = {row[0]: row[1] for row in connection.execute(
        "SELECT status, COUNT(*) FROM devices GROUP BY status ORDER BY status")}
    rooms = connection.execute(
        "SELECT COUNT(DISTINCT room) FROM devices").fetchone()[0]
    return {"total": int(total), "rooms": int(rooms), "by_kind": by_kind,
            "by_status": by_status}


def render_report(connection: sqlite3.Connection,
                  devices: list[dict] | None = None) -> str:
    devices = list_devices(connection) if devices is None else list(devices)
    stats = registry_stats(connection)
    lines = [
        "DEVICE REGISTRY",
        "=" * 78,
        f"Devices: {stats['total']}    Rooms: {stats['rooms']}",
        "",
        f"{'id':<14} {'kind':<10} {'status':<12} {'firmware':<9} room",
        "-" * 78,
    ]
    for device in devices:
        lines.append(f"{device['id']:<14} {device['kind']:<10} "
                     f"{device['status']:<12} {device['firmware']:<9} "
                     f"{device['room']}")
    lines += ["", "By kind: " + ", ".join(
        f"{kind}={count}" for kind, count in stats["by_kind"].items())]
    lines.append("By status: " + ", ".join(
        f"{status}={count}" for status, count in stats["by_status"].items()))
    return "\n".join(lines)


def to_dict(connection: sqlite3.Connection) -> dict:
    return {"devices": list_devices(connection),
            "stats": registry_stats(connection)}


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
def run_demo(data_dir: Path | None = None) -> int:
    root = data_dir or DATA_DIR
    print("=" * 78)
    print(" DEVICE REGISTRY - offline demo")
    print(" SQLite schema, validated CRUD, status history, no network.")
    print("=" * 78)

    connection = connect()
    seeded = seed_registry(connection, root / "devices.json")
    devices = list_devices(connection)
    print(f"\nSeeded          : {seeded} devices into an in-memory database")
    assert seeded >= MIN_SEED_DEVICES
    assert len(devices) == seeded
    assert len({device["id"] for device in devices}) == seeded, \
        "duplicate ids in the registry"

    # every seeded row is schema-valid
    for device in devices:
        assert device["kind"] in KINDS, device
        assert device["status"] in STATUSES, device
        assert FIRMWARE_RE.match(device["firmware"]), device

    stats = registry_stats(connection)
    assert stats["total"] == seeded
    assert sum(stats["by_kind"].values()) == seeded
    assert sum(stats["by_status"].values()) == seeded
    assert set(stats["by_kind"]) <= set(KINDS)
    print(f"Kinds           : " + ", ".join(
        f"{kind}={count}" for kind, count in stats["by_kind"].items()))
    print(f"Rooms           : {stats['rooms']} distinct")

    # filtering must agree with an independent recount
    sensors = list_devices(connection, kind="sensor")
    recount = [device for device in devices if device["kind"] == "sensor"]
    assert [d["id"] for d in sensors] == [d["id"] for d in recount]
    print(f"Sensors         : {len(sensors)} "
          f"(matches an independent recount)")

    room = sensors[0]["room"]
    in_room = list_devices(connection, room=room)
    assert in_room and all(device["room"] == room for device in in_room)

    # validation is enforced at the boundary
    for bad in ({"device_id": "Bad Id", "name": "x", "kind": "sensor",
                 "room": "r", "firmware": "1.0.0"},
                {"device_id": "ok-id", "name": " ", "kind": "sensor",
                 "room": "r", "firmware": "1.0.0"},
                {"device_id": "ok-id", "name": "x", "kind": "toaster",
                 "room": "r", "firmware": "1.0.0"},
                {"device_id": "ok-id", "name": "x", "kind": "sensor",
                 "room": "r", "firmware": "1.0"}):
        try:
            add_device(connection, **bad)
        except RegistryError:
            pass
        else:
            raise RegistryError(f"validation accepted {bad}")
    try:
        add_device(connection, device_id=devices[0]["id"], name="Dup",
                   kind="sensor", room="r", firmware="1.0.0")
    except RegistryError as exc:
        assert "already exists" in str(exc)
    else:
        raise RegistryError("duplicate id was accepted")

    # status transitions are logged
    target = devices[0]["id"]
    before = get_device(connection, target)["status"]
    update_status(connection, target, "online")
    update_status(connection, target, "maintenance")
    history = device_events(connection, target)
    assert [event["status"] for event in history] == ["online", "maintenance"]
    assert get_device(connection, target)["status"] == "maintenance"
    print(f"Status history  : {target} {before} -> 2 logged transitions")

    # removal cascades to the event table
    removed = remove_device(connection, target)
    assert removed["id"] == target
    try:
        get_device(connection, target)
    except RegistryError as exc:
        assert "unknown device" in str(exc)
    else:
        raise RegistryError("removed device is still readable")
    assert device_events_count(connection, target) == 0
    assert registry_stats(connection)["total"] == seeded - 1

    print()
    print(render_report(connection))

    print(f"\nCross-checks OK: {seeded} seeded devices, schema-valid rows, "
          f"filters match recounts, invalid input rejected, "
          f"status history logged, delete cascades, no network")
    print("Demo completed successfully.")
    connection.close()
    return 0


def device_events_count(connection: sqlite3.Connection, device_id: str) -> int:
    """Event rows still referencing a device id (used by the demo/tests)."""
    return int(connection.execute(
        "SELECT COUNT(*) FROM device_events WHERE device_id = ?",
        (device_id,)).fetchone()[0])
