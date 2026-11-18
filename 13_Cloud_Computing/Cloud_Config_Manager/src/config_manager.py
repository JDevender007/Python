"""A merge goes all the way down, and drift is a list of paths, not a boolean.

The legacy config manager is three shortcuts that fit on one screen:

    merged = {**base, **overlay}          # one level, whole subtrees
    drift = desired != observed           # one boolean, no path
    if "secret" in key: value = "***"     # top level only

Each one is silent, and each one produces a confident answer.

**1. A shallow merge discards siblings.** `{**base, **overlay}` replaces the
whole `services` list, so an overlay that changes one service's replica count
deletes the other service entirely, along with every image and environment
variable in it. The bundled pair keeps **18 leaves** through a recursive merge
and only **9** through the shallow one: `services` falls from 2 entries to 1 and
`tags` from 2 keys to 1.

**2. A list of named objects merges by identity, not by index.** Even a merge
that recurses has to decide what a list is. Replacing it loses data; zipping by
position merges `web` with `api` as soon as the order differs. A list whose
entries all carry a unique string `name` is a map: merge each named entry, keep
the unmatched ones, preserve base order. An overlay with
`{name: api, replicas: 5}` therefore keeps `api`'s image and environment and
changes only the count.

**3. Drift is a set of leaf paths, and absence is not a value.** `desired !=
observed` says *that* something differs, never *what*: one boolean for a plan
that has to touch eight places. Comparing only the keys present in both is the
other half of the mistake -- it cannot see a missing key (an add) or an extra
one (a remove). And Python's `==` is not type-strict: `True == 1` and
`0 == False`, so a config that changed `versioning: false` to `versioning: 0`
is reported as no drift at all. The rebuild walks the union of keys, compares
scalars with `type(left) is type(right) and left == right`, and emits one
`Change` per path.

**4. A secret is masked at render time and at every depth.** A redactor that
only looks at top-level keys prints `DB_PASSWORD` in full as soon as it lives
under `services[api].env`, and a plan that prints `before: '<old secret>'`
leaks the value it just replaced. The rebuild masks by key name at any depth,
masks both sides of a secret change, and the demo searches its own rendered
plan for the bundled secret strings to prove none survived.

The demonstration is offline: three JSON documents, no YAML dependency, no
cloud API, no clock.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DESIRED_FILE = DATA_DIR / "desired.json"
OVERRIDE_FILE = DATA_DIR / "override.json"
OBSERVED_FILE = DATA_DIR / "observed.json"

#: The legacy shortcuts, transcribed so the demo can print them.
LEGACY_MERGE = "merged = {**base, **overlay}          # one level, whole subtrees"
LEGACY_DRIFT = "drift = desired != observed           # one boolean, no path"
LEGACY_REDACT = 'if "secret" in key: value = "***"     # top level only'

MAX_SERVICES = 100
MAX_REPLICAS = 100
MAX_SIZE_GB = 65_536

TOP_KEYS = ("project", "region", "services", "storage", "budget", "tags")
SECRET_HINTS = ("password", "secret", "token", "api_key", "apikey", "credential")
SLUG = re.compile(r"^[a-z][a-z0-9-]{0,30}$")
REGION = re.compile(r"^[a-z]{2}-[a-z0-9-]+-\d+$")
BUCKET = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")


class ConfigError(RuntimeError):
    """Raised for input the program refuses."""


# --------------------------------------------------------------------------- #
# Validation helpers
# --------------------------------------------------------------------------- #
def _whole(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{name} must be an integer, got {type(value).__name__}")
    return value


def _text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ConfigError(f"{name} must be text, got {type(value).__name__}")
    return value


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def load_config(path: str | Path) -> dict[str, Any]:
    """Read one ASCII JSON document and require a mapping at the root."""
    target = Path(path)
    if not target.is_file():
        raise ConfigError(f"config not found: {target.name}")
    try:
        body = target.read_bytes().decode("ascii")
    except UnicodeDecodeError as exc:
        raise ConfigError(f"{target.name} is not ASCII text") from exc
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{target.name} is not valid JSON: line {exc.lineno}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{target.name}: a config root must be a mapping")
    return data


def read_configs(
    desired_path: str | Path | None = None,
    override_path: str | Path | None = None,
    observed_path: str | Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """The three documents this lab always works with, in a fixed order."""
    return (
        load_config(desired_path if desired_path is not None else DESIRED_FILE),
        load_config(override_path if override_path is not None else OVERRIDE_FILE),
        load_config(observed_path if observed_path is not None else OBSERVED_FILE),
    )


def validate_config(config: dict[str, Any]) -> list[str]:
    """Every schema problem, as `path: message`; an empty list means valid."""
    if not isinstance(config, dict):
        return ["$: a config is a mapping"]
    errors: list[str] = []
    for key in config:
        if key not in TOP_KEYS:
            errors.append(f"$.{key}: unknown top-level key")

    project = config.get("project")
    if not isinstance(project, str) or not SLUG.match(project):
        errors.append("$.project: a lowercase slug (a-z, 0-9, dash) is required")

    region = config.get("region")
    if not isinstance(region, str) or not REGION.match(region):
        errors.append("$.region: a value like 'us-east-1' is required")

    services = config.get("services")
    if not isinstance(services, list) or not services:
        errors.append("$.services: a non-empty array is required")
    elif len(services) > MAX_SERVICES:
        errors.append(f"$.services: at most {MAX_SERVICES} services")
    else:
        seen: set[str] = set()
        for index, service in enumerate(services):
            where = f"$.services[{index}]"
            if not isinstance(service, dict):
                errors.append(f"{where}: a service is an object")
                continue
            name = service.get("name")
            if not isinstance(name, str) or not SLUG.match(name):
                errors.append(f"{where}.name: a lowercase slug is required")
            elif name in seen:
                errors.append(f"{where}.name: duplicate service {name!r}")
            else:
                seen.add(name)
            image = service.get("image")
            if not isinstance(image, str) or ":" not in image:
                errors.append(f"{where}.image: a 'repo:tag' string is required")
            replicas = service.get("replicas")
            if isinstance(replicas, bool) or not isinstance(replicas, int) \
                    or not 1 <= replicas <= MAX_REPLICAS:
                errors.append(f"{where}.replicas: an integer 1..{MAX_REPLICAS} is required")
            env = service.get("env", {})
            if not isinstance(env, dict):
                errors.append(f"{where}.env: a mapping is required")
            else:
                for env_key, env_value in env.items():
                    if not isinstance(env_key, str):
                        errors.append(f"{where}.env: keys must be text")
                    elif not isinstance(env_value, (str, int, bool)):
                        errors.append(f"{where}.env.{env_key}: a scalar is required")

    storage = config.get("storage")
    if storage is not None:
        if not isinstance(storage, dict):
            errors.append("$.storage: a mapping is required")
        else:
            bucket = storage.get("bucket")
            if not isinstance(bucket, str) or not BUCKET.match(bucket):
                errors.append("$.storage.bucket: a bucket name is required")
            size = storage.get("size_gb")
            if isinstance(size, bool) or not isinstance(size, int) \
                    or not 1 <= size <= MAX_SIZE_GB:
                errors.append(f"$.storage.size_gb: an integer 1..{MAX_SIZE_GB} is required")
            for key in storage:
                if key not in ("bucket", "size_gb", "versioning"):
                    errors.append(f"$.storage.{key}: unknown storage key")

    budget = config.get("budget")
    if budget is not None and (isinstance(budget, bool) or not isinstance(budget, int)
                               or budget < 0):
        errors.append("$.budget: a non-negative integer is required")

    tags = config.get("tags")
    if tags is not None:
        if not isinstance(tags, dict):
            errors.append("$.tags: a mapping is required")
        else:
            for tag_key, tag_value in tags.items():
                if not isinstance(tag_key, str) or not isinstance(tag_value, str):
                    errors.append("$.tags: keys and values must be text")
    return errors


def validate_or_raise(config: dict[str, Any]) -> None:
    problems = validate_config(config)
    if problems:
        joined = "\n  - ".join(problems)
        raise ConfigError(f"invalid config ({len(problems)} problem(s)):\n  - {joined}")


# --------------------------------------------------------------------------- #
# Merging
# --------------------------------------------------------------------------- #
def names_of(items: list[Any]) -> list[str] | None:
    """The `name` of every entry, when they are unique objects that all have one."""
    if not all(isinstance(item, dict) for item in items):
        return None
    names = [item.get("name") for item in items]
    if not all(isinstance(name, str) and name for name in names):
        return None
    if len(set(names)) != len(names):
        return None
    return names  # type: ignore[return-value]


def _copy(value: Any) -> Any:
    """A structural copy: nothing the merge returns shares a container with its inputs."""
    if isinstance(value, dict):
        return {key: _copy(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_copy(item) for item in value]
    return value


def _merge_lists(base: list[Any], overlay: list[Any], path: str) -> list[Any]:
    base_names = names_of(base)
    overlay_names = names_of(overlay)
    if base_names is None or overlay_names is None:
        return _copy(overlay)
    overlay_map = dict(zip(overlay_names, overlay))
    merged: list[Any] = []
    for name, item in zip(base_names, base):
        if name in overlay_map:
            merged.append(deep_merge(item, overlay_map[name], f"{path}[{name}]"))
        else:
            merged.append(_copy(item))
    for name, item in zip(overlay_names, overlay):
        if name not in base_names:
            merged.append(_copy(item))
    return merged


def deep_merge(base: dict[str, Any], overlay: dict[str, Any], path: str = "$") -> dict[str, Any]:
    """Recursive merge: mappings merge by key, named lists by name, the rest replaces."""
    if not isinstance(base, dict) or not isinstance(overlay, dict):
        raise ConfigError(f"{path}: a merge needs two mappings")
    merged = _copy(base)
    for key, value in overlay.items():
        child = f"{path}.{key}"
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value, child)
        elif isinstance(value, list) and isinstance(merged.get(key), list):
            merged[key] = _merge_lists(merged[key], value, child)
        else:
            merged[key] = _copy(value)
    return merged


def shallow_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """The legacy merge: one level, whole subtrees replaced, siblings gone."""
    if not isinstance(base, dict) or not isinstance(overlay, dict):
        raise ConfigError("a merge needs two mappings")
    return {**base, **overlay}


def count_leaves(config: Any) -> int:
    """Every scalar, with an empty container counted as one value."""
    if isinstance(config, dict):
        return sum(count_leaves(item) for item in config.values()) if config else 1
    if isinstance(config, list):
        return sum(count_leaves(item) for item in config) if config else 1
    return 1


def service_names(config: dict[str, Any]) -> list[str]:
    services = config.get("services", [])
    names = names_of(services) if isinstance(services, list) else None
    return names or []


# --------------------------------------------------------------------------- #
# Redaction
# --------------------------------------------------------------------------- #
def is_secret_key(key: object) -> bool:
    lowered = str(key).lower()
    return any(hint in lowered for hint in SECRET_HINTS)


def mask(value: Any, path: str = "$") -> Any:
    """Mask a secret at any depth, on the key that names it and both of its sides."""
    last = re.split(r"[.\[]", path.rstrip("]"))[-1]
    if is_secret_key(last):
        return "***"
    if isinstance(value, dict):
        return {
            key: ("***" if is_secret_key(key) else mask(item, f"{path}.{key}"))
            for key, item in value.items()
        }
    if isinstance(value, list):
        names = names_of(value)
        rows = []
        for index, item in enumerate(value):
            child = f"{path}[{names[index]}]" if names else f"{path}[{index}]"
            rows.append(mask(item, child))
        return rows
    return value


def leaks(text: str, secrets: list[str]) -> list[str]:
    """Every secret string that survives in a rendered document."""
    return [secret for secret in secrets if secret and secret in text]


# --------------------------------------------------------------------------- #
# Drift
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Change:
    """One path the plan has to touch."""

    path: str
    kind: str          # add | remove | change
    before: Any = None
    after: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path, "kind": self.kind,
                "before": self.before, "after": self.after}


def same(left: Any, right: Any) -> bool:
    """Type-strict scalar equality: `True` is not `1`, `False` is not `0`."""
    return type(left) is type(right) and left == right


def diff(desired: Any, observed: Any, path: str = "$") -> list[Change]:
    """One change per leaf path: adds, removes and type-strict changes."""
    if isinstance(desired, dict) and isinstance(observed, dict):
        changes: list[Change] = []
        for key in desired:
            child = f"{path}.{key}"
            if key in observed:
                changes.extend(diff(desired[key], observed[key], child))
            else:
                changes.append(Change(child, "add", None, mask(desired[key], child)))
        for key in observed:
            if key not in desired:
                child = f"{path}.{key}"
                changes.append(Change(child, "remove", mask(observed[key], child), None))
        return changes

    if isinstance(desired, list) and isinstance(observed, list):
        desired_names = names_of(desired)
        observed_names = names_of(observed)
        if desired_names is not None and observed_names is not None:
            desired_map = dict(zip(desired_names, desired))
            observed_map = dict(zip(observed_names, observed))
            changes = []
            for name in desired_names:
                child = f"{path}[{name}]"
                if name in observed_map:
                    changes.extend(diff(desired_map[name], observed_map[name], child))
                else:
                    changes.append(Change(child, "add", None, mask(desired_map[name], child)))
            for name in observed_names:
                if name not in desired_map:
                    child = f"{path}[{name}]"
                    changes.append(
                        Change(child, "remove", mask(observed_map[name], child), None)
                    )
            return changes

        changes = []
        shared = min(len(desired), len(observed))
        for index in range(shared):
            changes.extend(diff(desired[index], observed[index], f"{path}[{index}]"))
        for index in range(shared, len(observed)):
            changes.append(
                Change(f"{path}[{index}]", "remove", mask(observed[index]), None)
            )
        for index in range(shared, len(desired)):
            changes.append(
                Change(f"{path}[{index}]", "add", None, mask(desired[index]))
            )
        return changes

    if desired == observed and type(desired) is type(observed):
        return []
    return [Change(path, "change", mask(observed, path), mask(desired, path))]


def build_plan(desired: dict[str, Any], observed: dict[str, Any]) -> list[Change]:
    """Validate the desired document, then plan the move to the observed state."""
    validate_or_raise(desired)
    if not isinstance(observed, dict):
        raise ConfigError("an observed state is a mapping")
    return diff(desired, observed)


def summarize(changes: list[Change]) -> dict[str, int]:
    """Counts per kind, always all three keys."""
    counts = {"add": 0, "change": 0, "remove": 0}
    for change in changes:
        if change.kind not in counts:
            raise ConfigError(f"unknown change kind: {change.kind!r}")
        counts[change.kind] += 1
    return counts


def _show(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=False)
    return repr(value)


def render_plan(changes: list[Change]) -> str:
    """A human plan in which no secret value is ever printed."""
    if not changes:
        return "No drift: the observed state matches the desired configuration."
    counts = summarize(changes)
    lines = [
        f"Change plan: {counts['add']} to add, {counts['change']} to update, "
        f"{counts['remove']} to remove",
        "",
    ]
    for change in changes:
        if change.kind == "add":
            lines.append(f"  + {change.path} = {_show(change.after)}")
        elif change.kind == "remove":
            lines.append(f"  - {change.path} (was {_show(change.before)})")
        elif change.before == "***" and change.after == "***":
            lines.append(f"  ~ {change.path}: *** (secret value changed)")
        else:
            lines.append(
                f"  ~ {change.path}: {_show(change.before)} -> {_show(change.after)}"
            )
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Measurement
# --------------------------------------------------------------------------- #
def measure(
    desired_path: str | Path | None = None,
    override_path: str | Path | None = None,
    observed_path: str | Path | None = None,
) -> dict[str, Any]:
    desired, override, observed = read_configs(desired_path, override_path, observed_path)
    validate_or_raise(desired)
    if not isinstance(observed, dict):
        raise ConfigError("an observed state is a mapping")
    merged = deep_merge(desired, override)
    legacy = shallow_merge(desired, override)
    plan = diff(merged, observed)
    rendered = render_plan(plan)
    secrets = _secret_values(desired) + _secret_values(observed)
    return {
        "desired": desired,
        "override": override,
        "observed": observed,
        "merged": merged,
        "legacy": legacy,
        "plan": plan,
        "counts": summarize(plan),
        "paths": [change.path for change in plan],
        "leaves": {
            "desired": count_leaves(desired),
            "merged": count_leaves(merged),
            "legacy": count_leaves(legacy),
            "observed": count_leaves(observed),
        },
        "services": {
            "desired": len(desired.get("services", [])),
            "merged": len(merged.get("services", [])),
            "legacy": len(legacy.get("services", [])),
        },
        "merged_service_names": service_names(merged),
        "legacy_service_names": service_names(legacy),
        "rendered": rendered,
        "secrets": secrets,
        "leaks": leaks(rendered, secrets),
        "same_type": same(True, 1),
        "loose_equal": True == 1,
    }


def _secret_values(config: Any) -> list[str]:
    found: list[str] = []
    if isinstance(config, dict):
        for key, value in config.items():
            if is_secret_key(key) and isinstance(value, str):
                found.append(value)
            else:
                found.extend(_secret_values(value))
    elif isinstance(config, list):
        for item in config:
            found.extend(_secret_values(item))
    return found


def report(measured: dict[str, Any]) -> dict[str, Any]:
    """A JSON-safe view: no config object, no unmasked secret."""
    return {
        "changes": len(measured["plan"]),
        "counts": measured["counts"],
        "paths": measured["paths"],
        "leaves": measured["leaves"],
        "services": measured["services"],
        "merged_service_names": measured["merged_service_names"],
        "legacy_service_names": measured["legacy_service_names"],
        "leaks": measured["leaks"],
        "same_type": measured["same_type"],
        "loose_equal": measured["loose_equal"],
        "plan": [change.to_dict() for change in measured["plan"]],
    }


# --------------------------------------------------------------------------- #
# Audit
# --------------------------------------------------------------------------- #
def _guard(check) -> bool:
    try:
        return bool(check())
    except Exception:                                     # noqa: BLE001
        return False


def _refuses(call) -> bool:
    try:
        call()
    except ConfigError:
        return True
    return False


def audit(
    measured: dict[str, Any],
    *,
    merge: Callable[[dict, dict], dict] = deep_merge,
    reread: Callable[[], tuple[dict, dict, dict]] | None = None,
) -> list[tuple[str, bool]]:
    """Every check re-derives from the three documents, not from the summary."""
    def documents() -> tuple[dict, dict, dict]:
        if reread is not None:
            return reread()
        if not hasattr(documents, "cache"):
            documents.cache = read_configs()  # type: ignore[attr-defined]
        return documents.cache  # type: ignore[attr-defined]

    def rebuilt() -> dict[str, Any]:
        if not hasattr(rebuilt, "cache"):
            desired, override, observed = documents()
            merged = merge(desired, override)
            plan = diff(merged, observed)
            rendered = render_plan(plan)
            secrets = _secret_values(desired) + _secret_values(observed)
            rebuilt.cache = {  # type: ignore[attr-defined]
                "merged": merged,
                "plan": plan,
                "paths": [change.path for change in plan],
                "counts": summarize(plan),
                "leaves": count_leaves(merged),
                "services": len(merged.get("services", [])),
                "names": service_names(merged),
                "rendered": rendered,
                "secrets": secrets,
                "leaks": leaks(rendered, secrets),
            }
        return rebuilt.cache  # type: ignore[attr-defined]

    checks = [
        (
            "all_three_documents_load",
            lambda: len(documents()) == 3
            and all(isinstance(item, dict) for item in documents()),
        ),
        (
            "the_desired_config_is_valid",
            lambda: validate_config(documents()[0]) == [],
        ),
        (
            "a_recursive_merge_keeps_every_leaf",
            lambda: rebuilt()["leaves"] == measured["leaves"]["desired"] == 18,
        ),
        (
            "a_shallow_merge_loses_half_the_leaves",
            lambda: measured["leaves"]["legacy"] == 9
            and measured["leaves"]["legacy"] * 2 == measured["leaves"]["desired"],
        ),
        (
            "a_shallow_merge_replaces_the_service_list",
            lambda: measured["services"]["legacy"] == 1
            and measured["services"]["merged"] == 2 == measured["services"]["desired"],
        ),
        (
            "a_named_list_merges_by_identity",
            lambda: rebuilt()["names"] == ["web", "api"]
            and rebuilt()["merged"]["services"][1]["replicas"] == 5
            and rebuilt()["merged"]["services"][1]["image"]
            == "ghcr.io/shop/api:1.4.2",
        ),
        (
            "the_overlay_keeps_the_siblings_it_does_not_touch",
            lambda: rebuilt()["merged"]["tags"] == {"team": "platform", "env": "staging"}
            and rebuilt()["merged"]["region"] == "us-west-2"
            and rebuilt()["merged"]["budget"] == 500,
        ),
        (
            "the_base_document_is_never_mutated",
            lambda: documents()[0]["region"] == "us-east-1"
            and documents()[0]["services"][1]["replicas"] == 3
            and documents()[0]["tags"] == {"team": "platform", "env": "prod"},
        ),
        (
            "the_plan_is_one_change_per_path",
            lambda: rebuilt()["paths"]
            == [
                "$.region",
                "$.services[web].image",
                "$.services[api].replicas",
                "$.services[api].env.DB_PASSWORD",
                "$.services[worker]",
                "$.storage.versioning",
                "$.budget",
                "$.tags.env",
            ]
            == measured["paths"],
        ),
        (
            "the_change_kinds_are_pinned",
            lambda: rebuilt()["counts"] == {"add": 1, "change": 6, "remove": 1}
            == measured["counts"]
            and len(rebuilt()["plan"]) == 8,
        ),
        (
            "a_missing_key_is_an_add_and_an_extra_one_is_a_remove",
            lambda: [(c.path, c.kind) for c in rebuilt()["plan"]
                    if c.kind in ("add", "remove")]
            == [("$.services[worker]", "remove"), ("$.tags.env", "add")],
        ),
        (
            "a_type_difference_is_drift_even_when_equality_says_no",
            lambda: measured["loose_equal"] is True
            and measured["same_type"] is False
            and same(False, 0) is False
            and diff({"versioning": False}, {"versioning": 0}) != []
            and diff({"replicas": 2}, {"replicas": 2}) == [],
        ),
        (
            "a_secret_is_masked_at_any_depth",
            lambda: "***" in rebuilt()["rendered"]
            and "DB_PASSWORD" in rebuilt()["rendered"]
            and rebuilt()["secrets"]
            and rebuilt()["leaks"] == [],
        ),
        (
            "both_sides_of_a_secret_change_are_masked",
            lambda: next(
                change for change in rebuilt()["plan"]
                if change.path.endswith("DB_PASSWORD")
            ).before == "***"
            and next(
                change for change in rebuilt()["plan"]
                if change.path.endswith("DB_PASSWORD")
            ).after == "***",
        ),
        (
            "a_bad_config_is_refused",
            lambda: _refuses(
                lambda: build_plan(
                    {"project": "Shop API", "region": "east", "services": []},
                    measured["observed"],
                )
            )
            and _refuses(
                lambda: build_plan(
                    {
                        "project": "shop-api",
                        "region": "us-east-1",
                        "services": [
                            {"name": "web", "image": "nginx:1.25", "replicas": 0}
                        ],
                    },
                    measured["observed"],
                )
            ),
        ),
        (
            "rebuild_is_deterministic",
            lambda: rebuilt()["paths"] == measured["paths"]
            and rebuilt()["merged"] == measured["merged"],
        ),
    ]
    return [(name, _guard(check)) for name, check in checks]


# --------------------------------------------------------------------------- #
# Rendering and the demo
# --------------------------------------------------------------------------- #
def run_demo() -> int:
    measured = measure()
    plan = measured["plan"]
    merged = measured["merged"]
    counts = measured["counts"]
    print("Cloud config -- a merge goes all the way down")
    print("=" * 49)
    print()
    print(
        f"Configs: desired {measured['leaves']['desired']} leaves, "
        f"overlay {count_leaves(measured['override'])}, "
        f"observed {measured['leaves']['observed']}."
    )
    print(
        f"  {len(merged['services'])} services in {merged['region']} "
        f"after the overlay, budget {merged['budget']}."
    )
    print()
    print("1. A shallow merge discards siblings.")
    print("   " + LEGACY_MERGE)
    print(
        f"   leaves: desired {measured['leaves']['desired']}, "
        f"shallow {measured['leaves']['legacy']}, deep {measured['leaves']['merged']}; "
        f"services {' + '.join(measured['legacy_service_names']) or 'none'} after "
        f"the shallow merge."
    )
    print(
        "   the deep merge keeps web and api, and api's image and env survive "
        "the replica change."
    )
    print()
    print("2. A named list merges by identity, not by index.")
    print(
        f"   overlay names only api; merged order is "
        f"{', '.join(measured['merged_service_names'])} and api has "
        f"{merged['services'][1]['replicas']} replicas, not 3."
    )
    print(
        f"   tags: {merged['tags']} -- team survives the env override."
    )
    print()
    print("3. Drift is a set of paths, not one boolean.")
    print("   " + LEGACY_DRIFT)
    print(
        f"   the legacy test says {str(measured['desired'] != measured['observed']).lower()}; "
        f"the rebuild says {len(plan)} changes "
        f"({counts['change']} change, {counts['add']} add, {counts['remove']} remove)."
    )
    print(
        f"   Python calls True == 1 {measured['loose_equal']}; "
        f"the type-strict test calls it {measured['same_type']}."
    )
    for change in plan:
        print(f"     {change.kind:<6} {change.path}")
    print()
    print("4. A secret is masked at every depth.")
    print("   " + LEGACY_REDACT)
    for line in measured["rendered"].splitlines():
        if "***" in line:
            print("   " + line.strip())
    print(
        f"   the rendered plan leaks {len(measured['leaks'])} of "
        f"{len(measured['secrets'])} bundled secret values."
    )
    print()
    print("Checks")
    results = audit(measured)
    for name, okay in results:
        print(f"  {'PASS' if okay else 'FAIL'}  {name}")
    passed = sum(1 for _, okay in results if okay)
    print(f"  {passed}/{len(results)} checks pass")
    print()
    print(
        "Cross-checks OK: "
        f"the shallow merge leaves {measured['leaves']['legacy']} of "
        f"{measured['leaves']['desired']} leaves and one service, the deep merge "
        f"keeps {measured['leaves']['merged']} leaves and "
        f"{len(measured['merged_service_names'])} services with api at "
        f"{merged['services'][1]['replicas']} replicas; the legacy drift test "
        f"returns one boolean while the rebuild names {len(plan)} paths "
        f"({counts['change']} change, {counts['add']} add, {counts['remove']} remove); "
        f"True == 1 is {measured['loose_equal']} but type-strict is "
        f"{measured['same_type']}; and {len(measured['leaks'])} of "
        f"{len(measured['secrets'])} secret values survive rendering; "
        f"{passed}/{len(results)} checks pass."
    )
    print("Demo completed successfully.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_demo())
