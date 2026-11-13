"""Tests for the Device Registry project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from main import main  # noqa: E402
from registry import (  # noqa: E402
    KINDS,
    MIN_SEED_DEVICES,
    SEED_FILE,
    STATUSES,
    RegistryError,
    add_device,
    connect,
    device_events,
    device_events_count,
    get_device,
    list_devices,
    load_seed,
    registry_stats,
    remove_device,
    render_report,
    run_demo,
    seed_registry,
    to_dict,
    update_status,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SEED = PROJECT_ROOT / "data" / "devices.json"


@pytest.fixture()
def db():
    connection = connect()
    yield connection
    connection.close()


@pytest.fixture()
def seeded(db):
    seed_registry(db, SEED)
    return db


def sample(**overrides) -> dict:
    values = {"device_id": "test-device", "name": "Test Device",
              "kind": "sensor", "room": "lab", "firmware": "1.0.0"}
    values.update(overrides)
    return values


# --------------------------------------------------------------------------- #
# Connection
# --------------------------------------------------------------------------- #
def test_connect_creates_schema(db):
    tables = {row[0] for row in db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"devices", "device_events"} <= tables


def test_connect_creates_parent_directories(tmp_path):
    path = tmp_path / "nested" / "dir" / "registry.db"
    connection = connect(path)
    assert path.is_file()
    connection.close()


def test_connect_file_persists_devices(tmp_path):
    path = tmp_path / "registry.db"
    first = connect(path)
    add_device(first, **sample())
    first.close()
    second = connect(path)
    assert get_device(second, "test-device")["name"] == "Test Device"
    second.close()


# --------------------------------------------------------------------------- #
# Adding devices
# --------------------------------------------------------------------------- #
def test_add_device_returns_the_row(db):
    device = add_device(db, **sample())
    assert device["id"] == "test-device"
    assert device["kind"] == "sensor"
    assert device["status"] == "offline"
    assert device["created_at"].endswith("Z")


def test_add_device_accepts_every_kind(db):
    for index, kind in enumerate(KINDS):
        device = add_device(db, **sample(device_id=f"dev-{index}", kind=kind))
        assert device["kind"] == kind


def test_add_device_trims_whitespace(db):
    device = add_device(db, **sample(name="  Padded Name  "))
    assert device["name"] == "Padded Name"


def test_add_device_rejects_duplicate_id(db):
    add_device(db, **sample())
    with pytest.raises(RegistryError, match="already exists"):
        add_device(db, **sample(name="Other"))


@pytest.mark.parametrize("device_id", ["Bad Id", "1leading", "x", "-dash",
                                       "UPPER", "a" * 40])
def test_add_device_rejects_bad_ids(db, device_id):
    with pytest.raises(RegistryError, match="invalid device id"):
        add_device(db, **sample(device_id=device_id))


@pytest.mark.parametrize("name", ["", "   ", None])
def test_add_device_rejects_bad_names(db, name):
    with pytest.raises(RegistryError, match="name must be a non-empty string"):
        add_device(db, **sample(name=name))


def test_add_device_rejects_unknown_kind(db):
    with pytest.raises(RegistryError, match="invalid kind"):
        add_device(db, **sample(kind="toaster"))


def test_add_device_rejects_empty_room(db):
    with pytest.raises(RegistryError, match="room must be a non-empty string"):
        add_device(db, **sample(room="  "))


@pytest.mark.parametrize("firmware", ["1.0", "v1.0.0", "1.0.0.0", ""])
def test_add_device_rejects_bad_firmware(db, firmware):
    with pytest.raises(RegistryError, match="firmware"):
        add_device(db, **sample(firmware=firmware))


def test_add_device_rejects_unknown_status(db):
    with pytest.raises(RegistryError, match="invalid status"):
        add_device(db, **sample(status="sleeping"))


def test_add_device_accepts_explicit_status(db):
    device = add_device(db, **sample(status="online"))
    assert device["status"] == "online"


# --------------------------------------------------------------------------- #
# Reading devices
# --------------------------------------------------------------------------- #
def test_get_device_unknown(db):
    with pytest.raises(RegistryError, match="unknown device"):
        get_device(db, "ghost")


def test_get_device_rejects_bad_id(db):
    with pytest.raises(RegistryError, match="invalid device id"):
        get_device(db, "BAD ID")


def test_list_devices_is_sorted_by_id(seeded):
    ids = [device["id"] for device in list_devices(seeded)]
    assert ids == sorted(ids)


def test_list_devices_filters_by_kind(seeded):
    devices = list_devices(seeded, kind="sensor")
    assert devices and all(device["kind"] == "sensor" for device in devices)


def test_list_devices_filters_by_room(seeded):
    devices = list_devices(seeded, room="hallway")
    assert devices and all(device["room"] == "hallway" for device in devices)


def test_list_devices_filters_by_status(seeded):
    update_status(seeded, "gw-hall", "online")
    online = list_devices(seeded, status="online")
    assert [device["id"] for device in online] == ["gw-hall"]


def test_list_devices_combines_filters(seeded):
    devices = list_devices(seeded, kind="actuator", room="hallway")
    assert [device["id"] for device in devices] == ["lit-hall"]


def test_list_devices_rejects_bad_kind(seeded):
    with pytest.raises(RegistryError, match="invalid kind"):
        list_devices(seeded, kind="toaster")


def test_list_devices_rejects_bad_status(seeded):
    with pytest.raises(RegistryError, match="invalid status"):
        list_devices(seeded, status="sleeping")


def test_list_devices_empty_room(seeded):
    assert list_devices(seeded, room="nowhere") == []


# --------------------------------------------------------------------------- #
# Status changes
# --------------------------------------------------------------------------- #
def test_update_status_changes_and_logs(seeded):
    device = update_status(seeded, "gw-hall", "online")
    assert device["status"] == "online"
    history = device_events(seeded, "gw-hall")
    assert [row["status"] for row in history] == ["online"]


def test_update_status_same_status_logs_nothing(seeded):
    update_status(seeded, "gw-hall", "online")
    update_status(seeded, "gw-hall", "online")
    assert len(device_events(seeded, "gw-hall")) == 1


def test_update_status_rejects_bad_status(seeded):
    with pytest.raises(RegistryError, match="invalid status"):
        update_status(seeded, "gw-hall", "sleeping")


def test_update_status_unknown_device(seeded):
    with pytest.raises(RegistryError, match="unknown device"):
        update_status(seeded, "ghost", "online")


def test_device_events_history_order(seeded):
    for status in ("online", "error", "maintenance", "online"):
        update_status(seeded, "gw-hall", status)
    history = [row["status"] for row in device_events(seeded, "gw-hall")]
    assert history == ["online", "error", "maintenance", "online"]


def test_device_events_unknown_device(seeded):
    with pytest.raises(RegistryError, match="unknown device"):
        device_events(seeded, "ghost")


# --------------------------------------------------------------------------- #
# Removal
# --------------------------------------------------------------------------- #
def test_remove_device_returns_row(seeded):
    removed = remove_device(seeded, "plug-study")
    assert removed["id"] == "plug-study"
    with pytest.raises(RegistryError, match="unknown device"):
        get_device(seeded, "plug-study")


def test_remove_device_deletes_events(seeded):
    update_status(seeded, "plug-study", "online")
    assert device_events_count(seeded, "plug-study") == 1
    remove_device(seeded, "plug-study")
    assert device_events_count(seeded, "plug-study") == 0


def test_remove_device_unknown(seeded):
    with pytest.raises(RegistryError, match="unknown device"):
        remove_device(seeded, "ghost")


# --------------------------------------------------------------------------- #
# Seed data
# --------------------------------------------------------------------------- #
def test_load_seed_reads_the_bundled_file():
    rows = load_seed(SEED)
    assert len(rows) >= MIN_SEED_DEVICES
    assert all({"id", "name", "kind", "room", "firmware"} <= set(row)
               for row in rows)


def test_load_seed_missing_file(tmp_path):
    with pytest.raises(RegistryError, match="seed file not found"):
        load_seed(tmp_path / "ghost.json")


def test_load_seed_rejects_bad_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{oops", encoding="utf-8")
    with pytest.raises(RegistryError, match="not valid JSON"):
        load_seed(path)


def test_load_seed_requires_devices_key(tmp_path):
    path = tmp_path / "wrong.json"
    path.write_text(json.dumps({"rows": []}), encoding="utf-8")
    with pytest.raises(RegistryError, match="'devices' list"):
        load_seed(path)


def test_load_seed_rejects_short_list(tmp_path):
    path = tmp_path / "short.json"
    path.write_text(json.dumps({"devices": [
        {"id": "one", "name": "One", "kind": "sensor", "room": "r",
         "firmware": "1.0.0"}]}), encoding="utf-8")
    with pytest.raises(RegistryError, match="at least"):
        load_seed(path)


def test_load_seed_rejects_bad_entry(tmp_path):
    path = tmp_path / "bad_entry.json"
    path.write_text(json.dumps({"devices": ["nope"] * 4}), encoding="utf-8")
    with pytest.raises(RegistryError, match="not an object"):
        load_seed(path)


def test_load_seed_rejects_missing_field(tmp_path):
    row = {"id": "one", "name": "One", "kind": "sensor", "room": "r",
           "firmware": "1.0.0"}
    path = tmp_path / "missing.json"
    path.write_text(json.dumps({"devices": [row] * 4}), encoding="utf-8")
    with pytest.raises(RegistryError, match="duplicate seed device id"):
        load_seed(path)


def test_load_seed_rejects_duplicate_ids(tmp_path):
    row = {"id": "same", "name": "One", "kind": "sensor", "room": "r",
           "firmware": "1.0.0"}
    path = tmp_path / "dupe.json"
    path.write_text(json.dumps({"devices": [row] * 4}), encoding="utf-8")
    with pytest.raises(RegistryError, match="duplicate seed device id"):
        load_seed(path)


def test_seed_registry_adds_rows(db):
    assert seed_registry(db, SEED) == len(load_seed(SEED))
    assert len(list_devices(db)) == len(load_seed(SEED))


def test_seed_registry_is_idempotent(seeded):
    assert seed_registry(seeded, SEED) == 0
    assert len(list_devices(seeded)) == len(load_seed(SEED))


# --------------------------------------------------------------------------- #
# Statistics and reporting
# --------------------------------------------------------------------------- #
def test_registry_stats_counts(seeded):
    stats = registry_stats(seeded)
    assert stats["total"] == len(load_seed(SEED))
    assert sum(stats["by_kind"].values()) == stats["total"]
    assert sum(stats["by_status"].values()) == stats["total"]


def test_registry_stats_rooms(seeded):
    stats = registry_stats(seeded)
    assert stats["rooms"] == len({device["room"]
                                  for device in list_devices(seeded)})


def test_render_report_lists_every_device(seeded):
    report = render_report(seeded)
    assert "DEVICE REGISTRY" in report
    for device in list_devices(seeded):
        assert device["id"] in report


def test_to_dict_is_json_safe(seeded):
    payload = to_dict(seeded)
    json.dumps(payload)
    assert payload["stats"]["total"] == len(payload["devices"])


# --------------------------------------------------------------------------- #
# Demo and CLI
# --------------------------------------------------------------------------- #
def test_run_demo_prints_cross_checks(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out
    assert "Demo completed successfully." in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    first = capsys.readouterr().out
    assert run_demo() == 0
    assert capsys.readouterr().out == first


def test_cli_demo(capsys):
    assert main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_demo_quiet(capsys):
    assert main(["--demo", "--quiet"]) == 0
    assert capsys.readouterr().out == ""


def test_cli_requires_a_mode():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


def test_cli_requires_exactly_one_action(tmp_path, capsys):
    assert main(["--db", str(tmp_path / "r.db")]) == 2
    assert "choose exactly one" in capsys.readouterr().err


def test_cli_filters_require_list(tmp_path, capsys):
    assert main(["--db", str(tmp_path / "r.db"), "--stats",
                 "--kind", "sensor"]) == 2
    assert "require --list" in capsys.readouterr().err


def test_cli_seeds_and_lists(tmp_path, capsys):
    path = tmp_path / "r.db"
    assert main(["--db", str(path), "--seed"]) == 0
    capsys.readouterr()
    assert main(["--db", str(path), "--list"]) == 0
    out = capsys.readouterr().out
    assert "DEVICE REGISTRY" in out
    assert "gw-hall" in out


def test_cli_list_filters(tmp_path, capsys):
    path = tmp_path / "r.db"
    main(["--db", str(path), "--seed"])
    capsys.readouterr()
    assert main(["--db", str(path), "--list", "--kind", "camera"]) == 0
    out = capsys.readouterr().out
    assert "cam-front" in out
    assert "gw-hall" not in out


def test_cli_add_and_status(tmp_path, capsys):
    path = tmp_path / "r.db"
    assert main(["--db", str(path), "--add",
                 "fan-attic:Attic Fan:actuator:attic:1.0.0"]) == 0
    capsys.readouterr()
    assert main(["--db", str(path), "--status", "fan-attic:online"]) == 0
    assert "online" in capsys.readouterr().out
    assert main(["--db", str(path), "--history", "fan-attic"]) == 0
    assert "1 status change" in capsys.readouterr().out


def test_cli_rejects_bad_add_spec(tmp_path, capsys):
    assert main(["--db", str(tmp_path / "r.db"), "--add", "too:few"]) == 2
    assert "expected id:name:kind:room:firmware" in \
        capsys.readouterr().err


def test_cli_rejects_bad_status_value(tmp_path, capsys):
    path = tmp_path / "r.db"
    main(["--db", str(path), "--add", "dev-one:One:sensor:lab:1.0.0"])
    capsys.readouterr()
    assert main(["--db", str(path), "--status", "dev-one:sleeping"]) == 2
    assert "invalid status" in capsys.readouterr().err


def test_cli_remove_device(tmp_path, capsys):
    path = tmp_path / "r.db"
    main(["--db", str(path), "--add", "dev-one:One:sensor:lab:1.0.0"])
    capsys.readouterr()
    assert main(["--db", str(path), "--remove", "dev-one"]) == 0
    assert "Removed dev-one" in capsys.readouterr().out


def test_cli_unknown_device(tmp_path, capsys):
    assert main(["--db", str(tmp_path / "r.db"), "--history", "ghost"]) == 2
    assert "unknown device" in capsys.readouterr().err


def test_cli_stats_and_json(tmp_path, capsys):
    path = tmp_path / "r.db"
    main(["--db", str(path), "--seed"])
    capsys.readouterr()
    out = tmp_path / "run.json"
    assert main(["--db", str(path), "--stats", "--json", str(out),
                 "--quiet"]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["stats"]["total"] == len(load_seed(SEED))
    assert len(payload["devices"]) == payload["stats"]["total"]
    assert capsys.readouterr().out == ""


def test_bundled_seed_exists():
    assert SEED_FILE.is_file()
    assert SEED.is_file()
    assert set(KINDS) == {"gateway", "sensor", "actuator", "camera"}
    assert "online" in STATUSES
