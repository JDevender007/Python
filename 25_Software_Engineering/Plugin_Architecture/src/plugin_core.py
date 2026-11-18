"""Plugin architecture: discovery, registration, lifecycle, ordering, sandbox.

Discovery  - sorted *.py files in a plugins/ directory (deterministic)
Registration - each module contributes Plugin subclasses (by ``name``)
Lifecycle  - setup -> process -> teardown hooks per plugin, logged
Ordering   - dependency plan via Kahn's algorithm, deterministic ties
Sandbox    - import failures, init/setup/process/teardown exceptions, and
             missing dependencies never abort the pipeline: they are
             recorded and the remaining plugins still run

Bundled sample plugins live in ../plugins, the pipeline config in
../data/plugins.json. Fully offline - no network, no downloads.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Iterable, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLUGINS_DIR = PROJECT_ROOT / "plugins"
DEFAULT_CONFIG = PROJECT_ROOT / "data" / "plugins.json"

REQUIRED_INPUT_FIELDS = ("id", "text", "qty")
CONFIG_KEYS = ("input", "enable", "disable")


class PluginError(RuntimeError):
    """Raised for structural problems: bad config, missing dirs, cycles."""


# --------------------------------------------------------------------------- #
# The plugin contract
# --------------------------------------------------------------------------- #
class Plugin(ABC):
    """Base class every plugin subclass: identity, deps, lifecycle hooks."""

    name: ClassVar[str] = ""
    dependencies: ClassVar[tuple[str, ...]] = ()

    def setup(self, context: dict[str, Any]) -> None:
        """Prepare the plugin (open resources, seed context)."""

    @abstractmethod
    def process(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Transform the pipeline records; return the new record list."""

    def teardown(self, context: dict[str, Any]) -> None:
        """Release resources; runs whenever setup() succeeded."""


# --------------------------------------------------------------------------- #
# Discovery and registration (sandboxed loading)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class LoadFailure:
    path: Path
    message: str


@dataclass
class PluginRegistry:
    """What discovery produced: classes, their sources, and load failures."""

    directory: Path
    classes: dict[str, type[Plugin]] = field(default_factory=dict)
    sources: dict[str, Path] = field(default_factory=dict)
    failures: list[LoadFailure] = field(default_factory=list)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self.classes)

    @property
    def dependencies(self) -> dict[str, tuple[str, ...]]:
        return {name: cls.dependencies for name, cls in self.classes.items()}


def discover_plugins(directory: str | Path) -> list[Path]:
    """Sorted list of candidate plugin modules (skip underscore files)."""
    source = Path(directory)
    if not source.is_dir():
        raise PluginError(f"plugin directory not found: {source}")
    files = sorted(p for p in source.glob("*.py")
                   if not p.name.startswith("_"))
    if not files:
        raise PluginError(f"no plugin files found in {source}")
    return files


def _ensure_core_importable() -> None:
    """Let plugin files say `from plugin_core import Plugin`."""
    core_dir = str(Path(__file__).resolve().parent)
    if core_dir not in sys.path:
        sys.path.insert(0, core_dir)


def load_plugins(directory: str | Path) -> PluginRegistry:
    """Import every plugin file; per-file errors are recorded, not raised."""
    files = discover_plugins(directory)
    _ensure_core_importable()
    registry = PluginRegistry(directory=Path(directory))

    for index, path in enumerate(files):
        module_name = f"discovered_plugin_{index}_{path.stem}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec is None or spec.loader is None:
                raise PluginError(f"cannot load module from {path.name}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
        except Exception as exc:
            registry.failures.append(
                LoadFailure(path, f"import failed: {exc}"))
            sys.modules.pop(module_name, None)
            continue

        contributed = [
            obj for obj in vars(module).values()
            if isinstance(obj, type) and issubclass(obj, Plugin)
            and obj is not Plugin and obj.__module__ == module.__name__
        ]
        if not contributed:
            registry.failures.append(
                LoadFailure(path, "no Plugin subclass defined"))
            continue
        for cls in contributed:
            plugin_name = getattr(cls, "name", "") or ""
            if not plugin_name:
                registry.failures.append(LoadFailure(
                    path, f"class {cls.__name__} has no plugin name"))
                continue
            if plugin_name in registry.classes:
                registry.failures.append(LoadFailure(
                    path, f"duplicate plugin name {plugin_name!r}"))
                continue
            registry.classes[plugin_name] = cls
            registry.sources[plugin_name] = path
    return registry


# --------------------------------------------------------------------------- #
# Dependency planning (deterministic topological order)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ExecutionPlan:
    order: tuple[str, ...]
    skipped: dict[str, str]


def plan_execution(registry: Mapping[str, tuple[str, ...]],
                   enabled: Sequence[str]) -> ExecutionPlan:
    """Topologically order enabled plugins; sandbox missing dependencies."""
    enabled_list = list(dict.fromkeys(enabled))
    enabled_set = set(enabled_list)
    skipped: dict[str, str] = {}

    def propagate() -> bool:
        """Skip plugins whose dependency is missing/disabled/already skipped."""
        changed = False
        for name in enabled_list:
            if name in skipped:
                continue
            for dep in registry.get(name, ()):
                if dep not in registry:
                    skipped[name] = f"missing dependency {dep!r}"
                    changed = True
                    break
                if dep not in enabled_set:
                    skipped[name] = f"dependency {dep!r} is disabled"
                    changed = True
                    break
                if dep in skipped:
                    skipped[name] = f"depends on skipped plugin {dep!r}"
                    changed = True
                    break
        return changed

    while propagate():
        pass

    # Kahn's algorithm over the surviving plugins, deterministic tie-break.
    remaining = [n for n in enabled_list if n not in skipped]
    resolved: set[str] = set()
    order: list[str] = []
    progress = True
    while progress:
        progress = False
        for name in sorted(remaining):
            deps = [d for d in registry.get(name, ()) if d in enabled_set]
            if all(d in resolved for d in deps):
                order.append(name)
                resolved.add(name)
                remaining.remove(name)
                progress = True
                break       # restart the scan: new plugins may have opened up
    if remaining:
        raise PluginError(
            f"dependency cycle among: {', '.join(sorted(remaining))}")
    return ExecutionPlan(order=tuple(order), skipped=skipped)


# --------------------------------------------------------------------------- #
# Execution (sandboxed lifecycle)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class PluginFailure:
    plugin: str
    stage: str
    message: str


@dataclass
class ExecutionReport:
    order: tuple[str, ...]
    skipped: dict[str, str]
    failures: list[PluginFailure]
    hooks: list[str]
    data: list[dict[str, Any]]
    context: dict[str, Any]

    @property
    def failed_plugins(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(f.plugin for f in self.failures))

    def to_dict(self) -> dict[str, Any]:
        return {
            "order": list(self.order),
            "skipped": dict(self.skipped),
            "failures": [{"plugin": f.plugin, "stage": f.stage,
                          "message": f.message} for f in self.failures],
            "hooks": list(self.hooks),
            "records": len(self.data),
        }


def execute(registry: PluginRegistry, enabled: Sequence[str],
            data: Sequence[Mapping[str, Any]]) -> ExecutionReport:
    """Run the planned lifecycle; never let one plugin abort the rest."""
    plan = plan_execution(registry.dependencies, enabled)
    working = [dict(record) for record in data]
    context: dict[str, Any] = {"events": []}
    failures: list[PluginFailure] = []
    hooks: list[str] = []
    skipped = dict(plan.skipped)
    poisoned: set[str] = set()

    def fail(name: str, stage: str, exc: Exception) -> None:
        failures.append(PluginFailure(name, stage, str(exc)))

    for name in plan.order:
        blocked = next((d for d in registry.dependencies[name]
                        if d in poisoned), None)
        if blocked is not None:
            skipped[name] = f"dependency {blocked!r} failed at runtime"
            continue

        hooks.append(f"{name}.init")
        try:
            plugin = registry.classes[name]()
        except Exception as exc:
            fail(name, "init", exc)
            poisoned.add(name)
            continue

        hooks.append(f"{name}.setup")
        try:
            plugin.setup(context)
        except Exception as exc:
            fail(name, "setup", exc)
            poisoned.add(name)
            continue

        hooks.append(f"{name}.process")
        try:
            result = plugin.process(working)
            if not isinstance(result, list):
                raise PluginError("process() must return a list of records")
            working = result
        except Exception as exc:
            fail(name, "process", exc)
            poisoned.add(name)

        hooks.append(f"{name}.teardown")
        try:
            plugin.teardown(context)
        except Exception as exc:
            fail(name, "teardown", exc)

    return ExecutionReport(order=plan.order, skipped=skipped,
                           failures=failures, hooks=hooks, data=working,
                           context=context)


# --------------------------------------------------------------------------- #
# Configuration (bundled JSON)
# --------------------------------------------------------------------------- #
def _validate_input_record(record: Any, index: int) -> None:
    if not isinstance(record, dict):
        raise PluginError(f"input[{index}] must be a JSON object")
    missing = [f for f in REQUIRED_INPUT_FIELDS if f not in record]
    if missing:
        raise PluginError(
            f"input[{index}] missing field(s): {', '.join(missing)}")
    if not isinstance(record["id"], str) or not record["id"]:
        raise PluginError(f"input[{index}]: id must be a non-empty string")
    if not isinstance(record["text"], str):
        raise PluginError(f"input[{index}]: text must be a string")
    if isinstance(record["qty"], bool) or not isinstance(record["qty"], int):
        raise PluginError(f"input[{index}]: qty must be an integer")
    if record["qty"] < 1:
        raise PluginError(f"input[{index}]: qty must be >= 1")


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load and validate the pipeline config (fast, before any plugin work)."""
    source = Path(path) if path is not None else DEFAULT_CONFIG
    if not source.is_file():
        raise PluginError(f"file not found: {source}")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PluginError(f"could not parse {source.name}: {exc}") from exc
    if not isinstance(payload, dict):
        raise PluginError("config must be a JSON object")
    if "input" not in payload:
        raise PluginError("config missing required key: input")
    records = payload["input"]
    if not isinstance(records, list):
        raise PluginError("input must be a JSON array")
    if not records:
        raise PluginError("input contains no records")
    for index, record in enumerate(records):
        _validate_input_record(record, index)
    for key in ("enable", "disable"):
        if key in payload:
            value = payload[key]
            if not isinstance(value, list) or \
                    not all(isinstance(v, str) for v in value):
                raise PluginError(f"{key} must be a list of plugin names")
    enabled = payload.get("enable")
    disabled = payload.get("disable", [])
    if enabled is not None:
        both = sorted(set(enabled) & set(disabled))
        if both:
            raise PluginError(
                f"plugin(s) listed in both enable and disable: "
                f"{', '.join(both)}")
    return payload


def enabled_plugins(config: Mapping[str, Any],
                    available: Iterable[str]) -> list[str]:
    """Resolve enable/disable lists against discovered plugin names."""
    discovered = list(available)
    enabled = config.get("enable")
    if enabled is None:
        selected = [n for n in discovered
                    if n not in set(config.get("disable", []))]
    else:
        unknown = [n for n in enabled if n not in discovered]
        if unknown:
            raise PluginError(
                f"unknown plugin(s) in enable list: {', '.join(unknown)}")
        disabled = set(config.get("disable", []))
        selected = [n for n in enabled if n not in disabled]
    if not selected:
        raise PluginError("no plugins enabled after applying disable list")
    return selected


# --------------------------------------------------------------------------- #
# Convenience entry point (used by the demo and the CLI)
# --------------------------------------------------------------------------- #
def run_pipeline(config_path: str | Path | None = None,
                 plugins_dir: str | Path | None = None
                 ) -> tuple[dict[str, Any], ExecutionReport]:
    """Load config + plugins, then execute; returns (config, report)."""
    config = load_config(config_path)
    registry = load_plugins(plugins_dir or DEFAULT_PLUGINS_DIR)
    selection = enabled_plugins(config, registry.names)
    report = execute(registry, selection, config["input"])
    return config, report


def format_report(report: ExecutionReport, records: int) -> str:
    """Human-readable summary of a finished run (used by the CLI)."""
    lines = [f"Execution order : {' -> '.join(report.order) or '(none)'}"]
    for name, reason in report.skipped.items():
        lines.append(f"Skipped         : {name} ({reason})")
    for failure in report.failures:
        lines.append(f"Failure         : {failure.plugin} "
                     f"[{failure.stage}] {failure.message}")
    lines.append(f"Records         : {records} in -> {len(report.data)} out")
    if "stats" in report.context:
        stats = report.context["stats"]
        lines.append(f"Stats plugin    : count={stats['count']} "
                     f"total_qty={stats['total_qty']}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def run_demo() -> int:
    """Run the bundled pipeline with self-assertions; always returns 0."""
    print("=" * 68)
    print(" PLUGIN ARCHITECTURE")
    print(" Discovery, lifecycle, dependency order, sandboxed failures.")
    print(" Bundled plugins + config; fully offline.")
    print("=" * 68)

    config, report = run_pipeline()
    registry = load_plugins(DEFAULT_PLUGINS_DIR)

    print(f"\nDiscovered {len(registry.names)} plugins from "
          f"{DEFAULT_PLUGINS_DIR.name}/: {', '.join(registry.names)}")
    print(f"Config         : {DEFAULT_CONFIG.name} "
          f"({len(config['input'])} input records)")
    print(f"Execution order: {' -> '.join(report.order)}")
    for name, reason in report.skipped.items():
        print(f"Skipped        : {name} ({reason})")
    print(f"Lifecycle trace: {', '.join(report.hooks)}")
    for failure in report.failures:
        print(f"Sandboxed      : {failure.plugin} failed at "
              f"[{failure.stage}] -> {failure.message}")
    print("\nOutput records:")
    for record in report.data:
        print(f"  {record['id']}: {record['text']!r} qty={record['qty']} "
              f"echoed={record.get('echoed')}")

    # --- cross-checks the demo asserts ----------------------------------- #
    assert registry.failures == [], "bundled plugins must all load"
    assert set(registry.names) == {"echo", "upper", "stats", "faulty",
                                   "orphan"}
    order = list(report.order)
    assert "echo" in order and "upper" in order and "stats" in order
    assert order.index("echo") < order.index("upper"), \
        "dependency must run before its dependent"
    assert order.index("echo") < order.index("stats")
    assert set(order) == {"echo", "upper", "stats", "faulty"}, \
        "exactly the enabled, non-skipped plugins must run"

    assert "orphan" in report.skipped
    assert "missing dependency" in report.skipped["orphan"]

    assert len(report.failures) == 1, "exactly one sandboxed failure"
    only = report.failures[0]
    assert only.plugin == "faulty" and only.stage == "process"
    assert only.message == "simulated plugin failure"
    assert "faulty.setup" in report.hooks
    assert "faulty.teardown" in report.hooks, "teardown must still run"

    assert len(report.data) == len(config["input"])
    assert all(r["text"].isupper() for r in report.data), "upper not applied"
    assert all(r.get("echoed") is True for r in report.data)
    stats = report.context["stats"]
    assert stats["count"] == 4 and stats["total_qty"] == 17

    # input records were never mutated (execute works on copies)
    assert config["input"] == load_config()["input"], "input was mutated"

    # deterministic re-run: identical order, failures, and output
    _, again = run_pipeline()
    assert again.order == report.order, "plan order changed"
    assert again.failures == report.failures, "failures changed"
    assert again.data == report.data, "output records changed"
    assert again.hooks == report.hooks, "lifecycle trace changed"

    print(f"\nCross-checks OK: {len(report.order)} plugins run, "
          f"{len(report.skipped)} sandboxed skip, "
          f"{len(report.failures)} sandboxed failure survived, "
          f"{len(report.data)} records transformed, deterministic re-run")
    print("Demo completed successfully.")
    return 0
