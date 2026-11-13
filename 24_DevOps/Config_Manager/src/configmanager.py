"""Config Manager: layered YAML/JSON configuration with schema validation.

Layers merge in a fixed order - **defaults -> file -> environment** - later
layers win, and every final key remembers *which* layer set it (provenance).
A declarative schema validates each key: type (str/int/number/bool) with
coercion, required flags, min/max bounds, and choice lists. Local files only
- no network, no remote config services, no secrets fetched at runtime.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
VALID_TYPES = ("str", "int", "number", "bool")
LAYER_ORDER = ("defaults", "file", "env")   # later wins
DEFAULT_ENV_PREFIX = "APP_"
TRUE_STRINGS = frozenset({"true", "1", "yes", "on"})
FALSE_STRINGS = frozenset({"false", "0", "no", "off"})


class ConfigError(RuntimeError):
    """Raised for missing files, bad schema, and validation failures."""


# --------------------------------------------------------------------------- #
# Loading and flattening
# --------------------------------------------------------------------------- #
def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML mapping from disk."""
    source = Path(path)
    if not source.is_file():
        raise ConfigError(f"file not found: {source}")
    try:
        data = yaml.safe_load(source.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {source.name}: {exc}") from exc
    return _as_mapping(data, source.name)


def load_json(path: str | Path) -> dict[str, Any]:
    """Load a JSON mapping from disk."""
    source = Path(path)
    if not source.is_file():
        raise ConfigError(f"file not found: {source}")
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"invalid JSON in {source.name}: {exc}") from exc
    return _as_mapping(data, source.name)


def load_layer(path: str | Path) -> dict[str, Any]:
    """Load a config file, dispatching on the extension (.yaml/.yml/.json)."""
    suffix = Path(path).suffix.lower()
    if suffix == ".json":
        return load_json(path)
    if suffix in (".yaml", ".yml"):
        return load_yaml(path)
    raise ConfigError(f"unsupported config format {suffix!r} "
                      f"(expected .yaml/.yml/.json)")


def _as_mapping(data: Any, name: str) -> dict[str, Any]:
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(f"{name}: top level must be a mapping, "
                          f"got {type(data).__name__}")
    return data


def flatten(mapping: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Flatten nested mappings to dotted keys: {'db': {'host': 'x'}} ->
    {'db.host': 'x'}."""
    flat: dict[str, Any] = {}
    for key, value in mapping.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(flatten(value, prefix=f"{name}."))
        else:
            flat[name] = value
    return flat


def unflatten(flat: dict[str, Any]) -> dict[str, Any]:
    """Rebuild a nested mapping from dotted keys (inverse of flatten)."""
    tree: dict[str, Any] = {}
    for dotted, value in flat.items():
        parts = dotted.split(".")
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part, {})
            if not isinstance(node, dict):
                raise ConfigError(f"key conflict at {dotted!r}")
        node[parts[-1]] = value
    return tree


# --------------------------------------------------------------------------- #
# Schema
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class FieldSpec:
    """Schema entry for one configuration key."""

    key: str
    type: str
    required: bool = True
    min: float | None = None
    max: float | None = None
    choices: tuple[Any, ...] | None = None


def load_schema(path: str | Path) -> dict[str, FieldSpec]:
    """Load and validate a schema file (YAML or JSON)."""
    raw = load_layer(path)
    schema: dict[str, FieldSpec] = {}
    for key, spec in raw.items():
        if not isinstance(spec, dict):
            raise ConfigError(f"schema entry {key!r} must be a mapping")
        ftype = spec.get("type")
        if ftype not in VALID_TYPES:
            raise ConfigError(
                f"schema entry {key!r}: type must be one of "
                f"{', '.join(VALID_TYPES)}, got {ftype!r}")
        extra = set(spec) - {"type", "required", "min", "max", "choices"}
        if extra:
            raise ConfigError(f"schema entry {key!r}: unknown field(s): "
                              f"{', '.join(sorted(extra))}")
        choices = spec.get("choices")
        if choices is not None and not isinstance(choices, list):
            raise ConfigError(f"schema entry {key!r}: choices must be a list")
        schema[str(key)] = FieldSpec(
            key=str(key),
            type=ftype,
            required=bool(spec.get("required", True)),
            min=spec.get("min"),
            max=spec.get("max"),
            choices=tuple(choices) if choices is not None else None,
        )
    return schema


# --------------------------------------------------------------------------- #
# Coercion and validation
# --------------------------------------------------------------------------- #
def _coerce(key: str, value: Any, ftype: str) -> Any:
    """Coerce *value* to the schema type or raise ConfigError."""
    if ftype == "str":
        if isinstance(value, str):
            return value
        raise ConfigError(f"key {key}: expected str, "
                          f"got {type(value).__name__}")
    if ftype == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            low = value.strip().lower()
            if low in TRUE_STRINGS:
                return True
            if low in FALSE_STRINGS:
                return False
        raise ConfigError(f"key {key}: cannot coerce {value!r} to bool")
    if ftype == "int":
        if isinstance(value, bool):
            raise ConfigError(f"key {key}: expected int, got bool")
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value.strip())
            except ValueError:
                raise ConfigError(
                    f"key {key}: cannot coerce {value!r} to int") from None
        raise ConfigError(f"key {key}: expected int, "
                          f"got {type(value).__name__}")
    # ftype == "number"
    if isinstance(value, bool):
        raise ConfigError(f"key {key}: expected number, got bool")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            raise ConfigError(
                f"key {key}: cannot coerce {value!r} to number") from None
    raise ConfigError(f"key {key}: expected number, "
                      f"got {type(value).__name__}")


def validate(values: dict[str, Any],
             schema: dict[str, FieldSpec]) -> dict[str, Any]:
    """Validate flat values against the schema.

    Order (general -> specific): unknown keys, missing required keys,
    type coercion, then choices/bounds.
    """
    unknown = [k for k in values if k not in schema]
    if unknown:
        raise ConfigError(f"unknown key(s): {', '.join(sorted(unknown))}")

    missing = [spec.key for spec in schema.values()
               if spec.required and spec.key not in values]
    if missing:
        raise ConfigError(f"missing required key(s): "
                          f"{', '.join(sorted(missing))}")

    checked: dict[str, Any] = {}
    for spec in schema.values():
        if spec.key not in values:
            continue
        value = _coerce(spec.key, values[spec.key], spec.type)
        if spec.choices is not None and value not in spec.choices:
            raise ConfigError(
                f"key {spec.key}: {value!r} not in choices "
                f"{list(spec.choices)}")
        if spec.min is not None and value < spec.min:
            raise ConfigError(f"key {spec.key}: {value} is below "
                              f"minimum {spec.min}")
        if spec.max is not None and value > spec.max:
            raise ConfigError(f"key {spec.key}: {value} is above "
                              f"maximum {spec.max}")
        checked[spec.key] = value
    return checked


# --------------------------------------------------------------------------- #
# Environment layer
# --------------------------------------------------------------------------- #
def env_key_to_config(name: str, prefix: str = DEFAULT_ENV_PREFIX) -> str | None:
    """APP_DB__HOST -> db.host (returns None when the prefix doesn't match)."""
    if not prefix:
        raise ConfigError("env prefix must be non-empty")
    if not name.startswith(prefix):
        return None
    bare = name[len(prefix):]
    if not bare:
        raise ConfigError(f"env var {name!r} has an empty key after the prefix")
    return bare.lower().replace("__", ".")


def env_layer(environ: dict[str, str],
              prefix: str = DEFAULT_ENV_PREFIX) -> dict[str, str]:
    """Select prefixed environment variables as a config layer."""
    layer: dict[str, str] = {}
    for name, value in environ.items():
        key = env_key_to_config(name, prefix)
        if key is not None:
            layer[key] = value
    return layer


# --------------------------------------------------------------------------- #
# Layered merge with provenance
# --------------------------------------------------------------------------- #
@dataclass
class ConfigResult:
    """Final validated config plus per-key provenance."""

    values: dict[str, Any]
    provenance: dict[str, str]          # key -> "defaults" | "file:..." | "env:APP_X"
    layers: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def key_count(self) -> int:
        return len(self.values)

    def layer_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {layer: 0 for layer in LAYER_ORDER}
        for source in self.provenance.values():
            counts[source.split(":", 1)[0]] += 1
        return counts

    def unflatten(self) -> dict[str, Any]:
        return unflatten(self.values)

    def to_dict(self) -> dict[str, Any]:
        return {
            "values": self.values,
            "provenance": self.provenance,
            "layer_counts": self.layer_counts(),
        }


def merge_layers(layers: list[tuple[str, dict[str, Any]]]
                 ) -> tuple[dict[str, Any], dict[str, str]]:
    """Merge named flat layers in order; later layers win. Returns
    (merged values, provenance)."""
    merged: dict[str, Any] = {}
    provenance: dict[str, str] = {}
    for name, layer in layers:
        for key, value in layer.items():
            merged[key] = value
            provenance[key] = name
    return merged, provenance


def load_config(defaults_path: str | Path,
                schema_path: str | Path,
                file_path: str | Path | None = None,
                environ: dict[str, str] | None = None,
                env_prefix: str = DEFAULT_ENV_PREFIX) -> ConfigResult:
    """Build the layered config: defaults -> file -> env, then validate.

    The file layer is optional; the env layer comes from *environ* (pass a
    plain dict for deterministic/offline behaviour - nothing is read from
    the real process environment implicitly).
    """
    layer_list: list[tuple[str, dict[str, Any]]] = [
        ("defaults", flatten(load_layer(defaults_path))),
    ]
    if file_path is not None:
        layer_list.append((f"file:{Path(file_path).name}",
                           flatten(load_layer(file_path))))
    if environ:
        layer_list.append(("env", env_layer(environ, env_prefix)))

    merged, provenance = merge_layers(layer_list)
    # enrich env provenance with the originating variable name
    for key in list(provenance):
        if provenance[key] == "env":
            provenance[key] = ("env:"
                               f"{env_prefix}{key.upper().replace('.', '__')}")
    schema = load_schema(schema_path)
    values = validate(merged, schema)
    # keep provenance aligned with the validated key set only
    provenance = {k: provenance[k] for k in values}
    return ConfigResult(values=values, provenance=provenance,
                        layers=dict(layer_list))


# --------------------------------------------------------------------------- #
# Provenance report
# --------------------------------------------------------------------------- #
def render_report(result: ConfigResult) -> str:
    """Human-readable provenance report used by the CLI and the demo."""
    counts = result.layer_counts()
    lines = [
        "CONFIG PROVENANCE REPORT",
        "=" * 68,
        f"Keys         : {result.key_count} validated",
        f"Layers       : {' -> '.join(LAYER_ORDER)} (later wins)",
        f"Split        : defaults {counts['defaults']}, "
        f"file {counts['file']}, env {counts['env']}",
        "",
        f"  {'key':<18} {'value':<24} source",
        f"  {'-' * 18} {'-' * 24} {'-' * 20}",
    ]
    for key in sorted(result.values):
        value = result.values[key]
        lines.append(f"  {key:<18} {str(value):<24} "
                     f"{result.provenance[key]}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Bundled data + offline demo
# --------------------------------------------------------------------------- #
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULTS_YAML = DATA_DIR / "defaults.yaml"
SETTINGS_YAML = DATA_DIR / "settings.yaml"
SCHEMA_YAML = DATA_DIR / "schema.yaml"
ENV_JSON = DATA_DIR / "env.json"

EXPECTED_KEYS = 9
EXPECTED_LAYER_SPLIT = {"defaults": 3, "file": 3, "env": 3}


def run_demo(defaults: Path | None = None,
             schema: Path | None = None) -> int:
    """Layer the bundled configs, validate, and self-check - fully offline."""
    print("=" * 68)
    print(" CONFIG MANAGER - offline demo")
    print(" defaults.yaml -> settings.yaml -> env (APP_*); local files only.")
    print("=" * 68)

    for path in (defaults or DEFAULTS_YAML, SETTINGS_YAML, schema or SCHEMA_YAML):
        if not path.is_file():
            raise ConfigError(f"bundled sample not found: {path}")
    environ = load_json(ENV_JSON)
    print(f"\nLoaded: {Path(defaults or DEFAULTS_YAML).name} -> "
          f"{SETTINGS_YAML.name} -> env prefix {DEFAULT_ENV_PREFIX!r} "
          f"({len(environ)} vars)")

    result = load_config(defaults or DEFAULTS_YAML, schema or SCHEMA_YAML,
                         file_path=SETTINGS_YAML, environ=environ)
    print()
    print(render_report(result))

    # --- cross-checks the demo asserts ----------------------------------- #
    values = result.values
    assert len(values) == EXPECTED_KEYS, "unexpected key count"
    assert values["port"] == 9090 and isinstance(values["port"], int), \
        "env layer must win for port (int coerced from string)"
    assert values["debug"] is True, "'true' must coerce to boolean True"
    assert values["db.host"] == "10.0.0.5", "env APP_DB__HOST must win"
    assert values["log_level"] == "WARNING", "file layer must win for log_level"
    assert values["retries"] == 5 and isinstance(values["retries"], int)
    assert values["app_name"] == "devops-demo", "defaults layer for app_name"
    assert values["timeout_seconds"] == 5.0
    assert result.layer_counts() == EXPECTED_LAYER_SPLIT, \
        "layer split mismatch"
    assert result.provenance["port"] == "env:APP_PORT"
    assert result.provenance["log_level"] == "file:settings.yaml"
    assert result.provenance["app_name"] == "defaults"

    # round-trip: flatten(unflatten(values)) == values
    assert flatten(unflatten(values)) == values, "flatten round-trip failed"

    # deterministic re-run: identical values and provenance
    again = load_config(defaults or DEFAULTS_YAML, schema or SCHEMA_YAML,
                        file_path=SETTINGS_YAML, environ=environ)
    assert again.values == result.values, "not deterministic"
    assert again.provenance == result.provenance, "provenance not deterministic"

    # validation actually rejects bad input (three failure classes)
    bad_unknown = dict(values, mystery="?")
    try:
        validate(bad_unknown, load_schema(schema or SCHEMA_YAML))
        raise AssertionError("unknown key was not rejected")
    except ConfigError as exc:
        assert "unknown key" in str(exc)
    try:
        validate(dict(values, port="not-a-number"),
                 load_schema(schema or SCHEMA_YAML))
        raise AssertionError("bad port was not rejected")
    except ConfigError as exc:
        assert "cannot coerce" in str(exc)
    try:
        validate(dict(values, retries=99), load_schema(schema or SCHEMA_YAML))
        raise AssertionError("out-of-range retries was not rejected")
    except ConfigError as exc:
        assert "above maximum" in str(exc)

    counts = result.layer_counts()
    print(f"\nCross-checks OK: {len(values)} keys, layer split "
          f"defaults {counts['defaults']}/file "
          f"{counts['file']}/env {counts['env']}, "
          f"port={values['port']} from env, log_level={values['log_level']} "
          f"from file, coercion+bounds+unknown-key all rejected, "
          f"deterministic re-run")
    print("\nDemo completed successfully.")
    return 0
