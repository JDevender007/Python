"""Cloud configuration management: validation, overlays, and drift detection.

Configs are plain YAML/JSON documents. This module provides:

- schema validation with precise, path-based error messages
- deep-merge overlays (base + environment overrides)
- diffing a desired config against an observed state
- a change plan (add / remove / change) with secret masking

Everything is file-based and offline - no cloud APIs are contacted.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

LOG = logging.getLogger("cloud.config")

ALLOWED_TOP_KEYS = {"project", "region", "services", "storage", "budget", "tags"}
SECRET_KEY_HINTS = ("password", "secret", "token", "api_key", "apikey", "credential")
REGION_RE = re.compile(r"^[a-z]{2}-[a-z0-9-]+-\d+$")
SERVICE_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{0,30}$")
BUCKET_RE = re.compile(r"^[a-z0-9][a-z0-9.\-]{1,61}[a-z0-9]$")

MAX_REPLICAS = 100
MAX_SIZE_GB = 65_536


class ConfigError(RuntimeError):
    """Raised for load failures and schema violations."""


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def load_config(path: str | Path) -> dict[str, Any]:
    """Load a YAML or JSON config file (by extension) into a dict."""
    source = Path(path)
    if not source.is_file():
        raise ConfigError(f"config not found: {source}")
    text = source.read_text(encoding="utf-8")
    try:
        if source.suffix.lower() == ".json":
            data = json.loads(text)
        else:
            data = yaml.safe_load(text)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ConfigError(f"could not parse {source.name}: {exc}") from exc
    if data is None:
        raise ConfigError(f"config is empty: {source.name}")
    if not isinstance(data, dict):
        raise ConfigError(f"config root must be a mapping: {source.name}")
    return data


def save_config(config: dict[str, Any], path: str | Path) -> Path:
    """Write a config as YAML (or JSON when the name ends with .json)."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.suffix.lower() == ".json":
        target.write_text(json.dumps(config, indent=2), encoding="utf-8")
    else:
        target.write_text(
            yaml.safe_dump(config, sort_keys=False), encoding="utf-8"
        )
    return target


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_config(config: dict[str, Any]) -> list[str]:
    """Return a list of schema problems (empty list means valid)."""
    errors: list[str] = []

    for key in config:
        if key not in ALLOWED_TOP_KEYS:
            errors.append(f"$.{key}: unknown top-level key "
                          f"(allowed: {', '.join(sorted(ALLOWED_TOP_KEYS))})")

    project = config.get("project")
    if not isinstance(project, str) or not project.strip():
        errors.append("$.project: required non-empty string")
    elif not SERVICE_NAME_RE.match(project):
        errors.append("$.project: must be a lowercase slug (a-z, 0-9, dash)")

    region = config.get("region")
    if not isinstance(region, str):
        errors.append("$.region: required string")
    elif not REGION_RE.match(region):
        errors.append("$.region: must look like 'us-east-1'")

    services = config.get("services")
    if not isinstance(services, list) or not services:
        errors.append("$.services: required non-empty array")
    else:
        seen: set[str] = set()
        for i, service in enumerate(services):
            where = f"$.services[{i}]"
            if not isinstance(service, dict):
                errors.append(f"{where}: must be an object")
                continue
            name = service.get("name")
            if not isinstance(name, str) or not SERVICE_NAME_RE.match(name or ""):
                errors.append(f"{where}.name: required lowercase slug")
            elif name in seen:
                errors.append(f"{where}.name: duplicate service {name!r}")
            else:
                seen.add(name)

            image = service.get("image")
            if not isinstance(image, str) or ":" not in image:
                errors.append(f"{where}.image: required 'repo:tag' string")

            replicas = service.get("replicas")
            if not _is_int(replicas) or not 1 <= replicas <= MAX_REPLICAS:
                errors.append(f"{where}.replicas: integer 1..{MAX_REPLICAS} required")

            env = service.get("env", {})
            if not isinstance(env, dict):
                errors.append(f"{where}.env: must be a mapping")
            else:
                for env_key, env_val in env.items():
                    if not isinstance(env_key, str):
                        errors.append(f"{where}.env: keys must be strings")
                    elif not isinstance(env_val, (str, int, bool)) or isinstance(
                        env_val, float
                    ):
                        errors.append(
                            f"{where}.env.{env_key}: must be a string, int, or bool"
                        )

            extra = set(service) - {"name", "image", "replicas", "env"}
            for key in sorted(extra):
                errors.append(f"{where}.{key}: unknown service key")

    storage = config.get("storage")
    if storage is not None:
        if not isinstance(storage, dict):
            errors.append("$.storage: must be an object")
        else:
            bucket = storage.get("bucket")
            if not isinstance(bucket, str) or not BUCKET_RE.match(bucket):
                errors.append("$.storage.bucket: invalid bucket name")
            size = storage.get("size_gb")
            if not _is_int(size) or not 1 <= size <= MAX_SIZE_GB:
                errors.append(f"$.storage.size_gb: integer 1..{MAX_SIZE_GB} required")
            for key in set(storage) - {"bucket", "size_gb"}:
                errors.append(f"$.storage.{key}: unknown storage key")

    budget = config.get("budget")
    if budget is not None and (not _is_number(budget) or budget < 0):
        errors.append("$.budget: non-negative number required")

    tags = config.get("tags")
    if tags is not None:
        if not isinstance(tags, dict):
            errors.append("$.tags: must be a mapping")
        else:
            for tag_key, tag_val in tags.items():
                if not isinstance(tag_key, str) or not isinstance(tag_val, str):
                    errors.append("$.tags: keys and values must be strings")

    return errors


def validate_or_raise(config: dict[str, Any]) -> None:
    """Raise ConfigError listing every problem, or pass silently."""
    errors = validate_config(config)
    if errors:
        joined = "\n  - ".join(errors)
        raise ConfigError(f"invalid config ({len(errors)} problem(s)):\n  - {joined}")


# --------------------------------------------------------------------------- #
# Overlay / deep merge
# --------------------------------------------------------------------------- #
def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge `overlay` onto `base` (new dict, inputs untouched).

    Mappings merge key-by-key; lists and scalars are replaced wholesale.
    """
    merged: dict[str, Any] = {}
    for key, value in base.items():
        merged[key] = (
            dict(value) if isinstance(value, dict) else
            list(value) if isinstance(value, list) else
            value
        )
    for key, value in overlay.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = (
                dict(value) if isinstance(value, dict) else
                list(value) if isinstance(value, list) else
                value
            )
    return merged


# --------------------------------------------------------------------------- #
# Diffing and planning
# --------------------------------------------------------------------------- #
@dataclass
class Change:
    """One planned change between desired and observed state."""

    path: str
    kind: str          # add | remove | change
    before: Any = None
    after: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path, "kind": self.kind,
                "before": self.before, "after": self.after}


def is_secret_path(path: str) -> bool:
    """True when any path segment looks like a secret."""
    lowered = path.lower()
    return any(hint in lowered for hint in SECRET_KEY_HINTS)


def mask_value(value: Any, path: str) -> Any:
    """Mask secret-looking values, including nested keys in containers."""
    if is_secret_path(path):
        return "***"
    return _mask_nested(value)


def _mask_nested(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: ("***" if is_secret_path(str(key)) else _mask_nested(val))
            for key, val in value.items()
        }
    if isinstance(value, list):
        return [_mask_nested(item) for item in value]
    return value


def _key_of(item: Any) -> str | None:
    if isinstance(item, dict) and isinstance(item.get("name"), str):
        return item["name"]
    return None


def diff(desired: Any, observed: Any, path: str = "$") -> list[Change]:
    """Compare desired vs observed, producing a change list."""
    changes: list[Change] = []

    if isinstance(desired, dict) and isinstance(observed, dict):
        for key in desired:
            child = f"{path}.{key}"
            if key not in observed:
                changes.append(Change(child, "add", None,
                                      mask_value(desired[key], child)))
            else:
                changes.extend(diff(desired[key], observed[key], child))
        for key in observed:
            if key not in desired:
                child = f"{path}.{key}"
                changes.append(Change(child, "remove",
                                      mask_value(observed[key], child), None))
        return changes

    if isinstance(desired, list) and isinstance(observed, list):
        d_keys = [_key_of(x) for x in desired]
        o_keys = [_key_of(x) for x in observed]
        keyed = (
            all(k is not None for k in d_keys + o_keys)
            and len(set(d_keys)) == len(d_keys)
            and len(set(o_keys)) == len(o_keys)
        )
        if keyed:
            d_map = dict(zip(d_keys, desired))
            o_map = dict(zip(o_keys, observed))
            for key in d_keys:
                assert isinstance(key, str)
                child = f"{path}[{key}]"
                if key in o_map:
                    changes.extend(diff(d_map[key], o_map[key], child))
                else:
                    changes.append(Change(child, "add", None,
                                          mask_value(d_map[key], child)))
            for key in o_keys:
                if key not in d_map:
                    assert isinstance(key, str)
                    child = f"{path}[{key}]"
                    changes.append(Change(child, "remove",
                                          mask_value(o_map[key], child), None))
            return changes

        # positional fallback
        for i in range(min(len(desired), len(observed))):
            changes.extend(diff(desired[i], observed[i], f"{path}[{i}]"))
        for i in range(len(desired), len(observed)):  # observed has extras
            child = f"{path}[{i}]"
            changes.append(Change(child, "remove",
                                  mask_value(observed[i], child), None))
        for i in range(len(observed), len(desired)):  # desired has extras
            child = f"{path}[{i}]"
            changes.append(Change(child, "add", None,
                                  mask_value(desired[i], child)))
        return changes

    if desired != observed:
        changes.append(
            Change(path, "change", mask_value(observed, path),
                   mask_value(desired, path))
        )
    return changes


def summarize(changes: list[Change]) -> dict[str, int]:
    """Counts per change kind."""
    counts = {"add": 0, "remove": 0, "change": 0}
    for change in changes:
        counts[change.kind] = counts.get(change.kind, 0) + 1
    return counts


def build_plan(
    desired: dict[str, Any], observed: dict[str, Any]
) -> list[Change]:
    """Validate desired, diff against observed, and return the plan."""
    validate_or_raise(desired)
    return diff(desired, observed)


def render_plan(changes: list[Change]) -> str:
    """Human-readable plan used by the CLI and demo."""
    if not changes:
        return "No drift: observed state matches desired configuration."
    counts = summarize(changes)
    lines = [
        f"Change plan: {counts['add']} to add, {counts['change']} to update, "
        f"{counts['remove']} to remove",
        "",
    ]
    for change in changes:
        if change.kind == "add":
            lines.append(f"  + {change.path} = {change.after!r}")
        elif change.kind == "remove":
            lines.append(f"  - {change.path} (was {change.before!r})")
        elif is_secret_path(change.path):
            lines.append(f"  ~ {change.path}: *** (secret value changed)")
        else:
            lines.append(f"  ~ {change.path}: {change.before!r} -> {change.after!r}")
    lines.append("")
    lines.append("Secrets are masked (paths containing password/secret/token/...).")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
def _demo_desired() -> dict[str, Any]:
    return {
        "project": "shop-api",
        "region": "us-east-1",
        "services": [
            {"name": "web", "image": "nginx:1.25", "replicas": 2,
             "env": {"LOG_LEVEL": "info"}},
            {"name": "api", "image": "ghcr.io/shop/api:1.4.2", "replicas": 3,
             "env": {"LOG_LEVEL": "info", "DB_PASSWORD": "super-secret-demo"}},
        ],
        "storage": {"bucket": "shop-api-assets", "size_gb": 500},
        "budget": 400,
        "tags": {"team": "platform"},
    }


def _demo_override() -> dict[str, Any]:
    return {"region": "us-west-2", "budget": 500}


def _demo_observed() -> dict[str, Any]:
    return {
        "project": "shop-api",
        "region": "us-east-1",
        "services": [
            {"name": "web", "image": "nginx:1.24", "replicas": 2,
             "env": {"LOG_LEVEL": "info"}},
            {"name": "api", "image": "ghcr.io/shop/api:1.4.2", "replicas": 2,
             "env": {"LOG_LEVEL": "info", "DB_PASSWORD": "rotated-old-value"}},
            {"name": "worker", "image": "ghcr.io/shop/worker:0.9", "replicas": 1,
             "env": {}},
        ],
        "storage": {"bucket": "shop-api-assets", "size_gb": 500},
        "budget": 350,
    }


def run_demo(workdir: Path | None = None) -> int:
    """Validate, overlay, and diff the bundled sample configs - offline."""
    print("=" * 60)
    print(" CLOUD CONFIG MANAGER - offline demo")
    print(" File-based YAML configs; no cloud APIs are contacted.")
    print("=" * 60)

    directory = workdir or Path(__file__).resolve().parent.parent / "data"
    directory.mkdir(parents=True, exist_ok=True)

    desired = _demo_desired()
    override = _demo_override()
    observed = _demo_observed()

    desired_path = save_config(desired, directory / "desired.yaml")
    override_path = save_config(override, directory / "override.yaml")
    observed_path = save_config(observed, directory / "observed.yaml")
    print(f"\n[1] Wrote {desired_path.name}, {override_path.name}, {observed_path.name}")

    loaded = load_config(desired_path)
    errors = validate_config(loaded)
    print(f"[2] validate base config -> {'OK' if not errors else errors}")

    print("[3] deliberately broken config -> shows path-based errors:")
    broken = {"project": "Shop API", "region": "east", "services": []}
    for error in validate_config(broken)[:4]:
        print(f"      - {error}")

    merged = deep_merge(load_config(desired_path), load_config(override_path))
    print(f"[4] overlay applied -> region={merged['region']}, "
          f"budget={merged['budget']}")

    plan = build_plan(merged, load_config(observed_path))
    print("\n[5] drift plan (desired+overlay vs observed):")
    print(render_plan(plan))

    counts = summarize(plan)
    print(f"\n[6] summary: {counts['add']} add / {counts['change']} change / "
          f"{counts['remove']} remove")

    # a clean second pass: diffing desired against itself must be empty
    clean = diff(merged, merged)
    print(f"[7] self-diff is empty -> {clean == []}")

    print("\nDemo completed successfully.")
    return 0
