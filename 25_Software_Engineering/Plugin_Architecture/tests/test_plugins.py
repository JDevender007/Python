"""Tests for the Plugin Architecture project."""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from plugin_core import (  # noqa: E402
    DEFAULT_CONFIG,
    DEFAULT_PLUGINS_DIR,
    PluginError,
    enabled_plugins,
    execute,
    format_report,
    discover_plugins,
    load_config,
    load_plugins,
    plan_execution,
    run_demo,
    run_pipeline,
)
from main import main  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _write_plugin(directory: Path, filename: str, body: str) -> Path:
    path = directory / filename
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


GOOD_PLUGIN = """
    from plugin_core import Plugin

    class {cls}(Plugin):
        name = "{name}"
        dependencies = {deps}

        def process(self, data):
            return data
"""


def _make_plugins(tmp_path: Path, specs: dict[str, tuple[str, tuple]]):
    """Write simple plugins: {file: (class, name, deps)} via specs dict."""
    for filename, (cls, name, deps) in specs.items():
        _write_plugin(tmp_path, filename, GOOD_PLUGIN.format(
            cls=cls, name=name, deps=repr(tuple(deps))))


def _config(tmp_path: Path, payload, name: str = "config.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


BASE_INPUT = [{"id": "R-1", "text": "alpha", "qty": 2}]


@pytest.fixture(scope="module")
def registry():
    return load_plugins(DEFAULT_PLUGINS_DIR)


@pytest.fixture(scope="module")
def config():
    return load_config()


# --------------------------------------------------------------------------- #
# Discovery and loading
# --------------------------------------------------------------------------- #
def test_discover_bundled_plugins():
    files = discover_plugins(DEFAULT_PLUGINS_DIR)
    assert len(files) == 5
    assert files == sorted(files)
    assert all(not p.name.startswith("_") for p in files)


def test_discover_missing_directory(tmp_path):
    with pytest.raises(PluginError, match="plugin directory not found"):
        discover_plugins(tmp_path / "nope")


def test_discover_empty_directory(tmp_path):
    (tmp_path / "_ignored.py").write_text("x = 1", encoding="utf-8")
    with pytest.raises(PluginError, match="no plugin files"):
        discover_plugins(tmp_path)


def test_load_bundled_registry(registry):
    assert set(registry.names) == {"echo", "upper", "stats", "faulty",
                                   "orphan"}
    assert registry.dependencies["upper"] == ("echo",)
    assert registry.failures == []
    assert registry.sources["echo"].parent == DEFAULT_PLUGINS_DIR


def test_import_error_is_sandboxed(tmp_path):
    _make_plugins(tmp_path, {"alpha.py": ("AlphaPlugin", "alpha", ())})
    _write_plugin(tmp_path, "broken.py", 'raise ImportError("boom")\n')
    registry = load_plugins(tmp_path)
    assert registry.names == ("alpha",)
    assert len(registry.failures) == 1
    assert "import failed" in registry.failures[0].message
    assert registry.failures[0].path.name == "broken.py"


def test_module_without_plugin_is_reported(tmp_path):
    (tmp_path / "plain.py").write_text("VALUE = 1\n", encoding="utf-8")
    registry = load_plugins(tmp_path)
    assert registry.names == ()
    assert registry.failures[0].message == "no Plugin subclass defined"


def test_duplicate_plugin_name_is_reported(tmp_path):
    _make_plugins(tmp_path, {"a.py": ("APlugin", "twin", ())})
    _make_plugins(tmp_path, {"b.py": ("BPlugin", "twin", ())})
    registry = load_plugins(tmp_path)
    assert registry.names == ("twin",)
    assert len(registry.failures) == 1
    assert "duplicate plugin name" in registry.failures[0].message


def test_missing_plugin_name_is_reported(tmp_path):
    _write_plugin(tmp_path, "noname.py", """
        from plugin_core import Plugin

        class NamelessPlugin(Plugin):
            name = ""

            def process(self, data):
                return data
    """)
    registry = load_plugins(tmp_path)
    assert registry.names == ()
    assert "has no plugin name" in registry.failures[0].message


# --------------------------------------------------------------------------- #
# Dependency planning
# --------------------------------------------------------------------------- #
def test_plan_topological_order():
    deps = {"echo": (), "stats": ("echo",), "upper": ("echo",)}
    plan = plan_execution(deps, ["upper", "stats", "echo"])
    assert plan.order == ("echo", "stats", "upper")
    assert plan.skipped == {}


def test_plan_excludes_disabled_plugins():
    deps = {"echo": (), "upper": ("echo",)}
    plan = plan_execution(deps, ["upper"])       # echo not enabled
    assert plan.order == ()
    assert "upper" in plan.skipped
    assert "disabled" in plan.skipped["upper"]


def test_plan_sandboxes_missing_dependency():
    deps = {"orphan": ("not_installed",), "echo": ()}
    plan = plan_execution(deps, ["orphan", "echo"])
    assert plan.order == ("echo",)
    assert "missing dependency" in plan.skipped["orphan"]


def test_plan_skips_dependents_of_skipped():
    deps = {"c": ("nope",), "b": ("c",), "a": ()}
    plan = plan_execution(deps, ["a", "b", "c"])
    assert plan.order == ("a",)
    assert "missing dependency" in plan.skipped["c"]
    assert "depends on skipped plugin 'c'" in plan.skipped["b"]


def test_plan_detects_cycles():
    deps = {"a": ("b",), "b": ("a",)}
    with pytest.raises(PluginError, match="dependency cycle among"):
        plan_execution(deps, ["a", "b"])


def test_plan_is_deterministic():
    deps = {"zeta": (), "alpha": (), "mid": ("alpha",)}
    orders = {plan_execution(deps, ["zeta", "mid", "alpha"]).order
              for _ in range(5)}
    assert orders == {("alpha", "mid", "zeta")}


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
def test_load_bundled_config(config):
    assert len(config["input"]) == 4
    assert set(config["enable"]) == {"echo", "upper", "stats", "faulty",
                                     "orphan"}
    assert DEFAULT_CONFIG.parent == PROJECT_ROOT / "data"


def test_config_missing_file(tmp_path):
    with pytest.raises(PluginError, match="file not found"):
        load_config(tmp_path / "nope.json")


def test_config_malformed_json(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{oops", encoding="utf-8")
    with pytest.raises(PluginError, match="could not parse"):
        load_config(path)


def test_config_shape_errors(tmp_path):
    with pytest.raises(PluginError, match="config must be a JSON object"):
        load_config(_config(tmp_path, [1, 2]))
    with pytest.raises(PluginError, match="missing required key: input"):
        load_config(_config(tmp_path, {"enable": ["echo"]}))


def test_config_input_errors(tmp_path):
    with pytest.raises(PluginError, match="input must be a JSON array"):
        load_config(_config(tmp_path, {"input": {"id": "R-1"}}))
    with pytest.raises(PluginError, match="input contains no records"):
        load_config(_config(tmp_path, {"input": []}))


def test_config_record_errors(tmp_path):
    with pytest.raises(PluginError, match=r"input\[0\] missing field"):
        load_config(_config(tmp_path, {"input": [{"id": "R-1"}]}))
    with pytest.raises(PluginError, match=r"input\[1\]: qty must be >= 1"):
        load_config(_config(tmp_path, {"input": [
            {"id": "R-1", "text": "a", "qty": 1},
            {"id": "R-2", "text": "b", "qty": 0}]}))


def test_config_enable_disable_errors(tmp_path):
    with pytest.raises(PluginError, match="enable must be a list"):
        load_config(_config(tmp_path, {"input": BASE_INPUT,
                                       "enable": "echo"}))
    with pytest.raises(PluginError, match="both enable and disable"):
        load_config(_config(tmp_path, {"input": BASE_INPUT,
                                       "enable": ["echo"],
                                       "disable": ["echo"]}))


# --------------------------------------------------------------------------- #
# enable/disable resolution
# --------------------------------------------------------------------------- #
def test_enabled_plugins_defaults_and_disable():
    config = {"input": BASE_INPUT, "disable": ["faulty"]}
    assert enabled_plugins(config, ["echo", "faulty"]) == ["echo"]


def test_enabled_plugins_unknown_name():
    with pytest.raises(PluginError, match="unknown plugin\\(s\\) in enable"):
        enabled_plugins({"input": BASE_INPUT, "enable": ["ghost"]},
                        ["echo"])
    with pytest.raises(PluginError, match="no plugins enabled"):
        enabled_plugins({"input": BASE_INPUT, "disable": ["echo"]},
                        ["echo"])


# --------------------------------------------------------------------------- #
# Execution (sandboxed lifecycle)
# --------------------------------------------------------------------------- #
def test_execute_bundled_pipeline(registry, config):
    selection = enabled_plugins(config, registry.names)
    report = execute(registry, selection, config["input"])
    assert report.order[0] == "echo"
    assert report.order.index("echo") < report.order.index("upper")
    assert len(report.data) == 4
    assert all(r["text"].isupper() and r["echoed"] for r in report.data)
    assert report.context["stats"]["total_qty"] == 17


def test_execute_sandboxes_process_failure(registry, config):
    selection = enabled_plugins(config, registry.names)
    report = execute(registry, selection, config["input"])
    assert set(report.order) == {"echo", "faulty", "stats", "upper"}
    assert report.failed_plugins == ("faulty",)
    failure = report.failures[0]
    assert failure.stage == "process"
    assert failure.message == "simulated plugin failure"
    assert "faulty.teardown" in report.hooks


def test_execute_never_mutates_input(registry, config):
    selection = enabled_plugins(config, registry.names)
    snapshot = json.dumps(config["input"])
    execute(registry, selection, config["input"])
    assert json.dumps(config["input"]) == snapshot


def test_execute_skips_dependents_of_failed_plugin(tmp_path):
    _make_plugins(tmp_path, {"a.py": ("APlugin", "a", ())})
    _write_plugin(tmp_path, "b.py", """
        from plugin_core import Plugin

        class BPlugin(Plugin):
            name = "b"
            dependencies = ("a",)

            def process(self, data):
                raise RuntimeError("b exploded")
    """)
    _make_plugins(tmp_path, {"c.py": ("CPlugin", "c", ("b",))})
    registry = load_plugins(tmp_path)
    report = execute(registry, ["a", "b", "c"], BASE_INPUT)
    assert report.order == ("a", "b", "c")
    assert report.failed_plugins == ("b",)
    assert "c" in report.skipped
    assert "failed at runtime" in report.skipped["c"]


def test_execute_sandboxes_setup_failure(tmp_path):
    _write_plugin(tmp_path, "angry.py", """
        from plugin_core import Plugin

        class AngryPlugin(Plugin):
            name = "angry"

            def setup(self, context):
                raise RuntimeError("setup boom")

            def process(self, data):
                return data

            def teardown(self, context):
                context.setdefault("events", []).append("late")
    """)
    _make_plugins(tmp_path, {"calm.py": ("CalmPlugin", "calm", ())})
    registry = load_plugins(tmp_path)
    report = execute(registry, ["angry", "calm"], BASE_INPUT)
    assert report.failed_plugins == ("angry",)
    assert report.failures[0].stage == "setup"
    assert "angry.teardown" not in report.hooks     # setup never succeeded
    assert report.data == [dict(BASE_INPUT[0])]     # calm still ran


def test_execute_sandboxes_abstract_init(tmp_path):
    _write_plugin(tmp_path, "half.py", """
        from plugin_core import Plugin

        class HalfPlugin(Plugin):
            name = "half"
    """)
    registry = load_plugins(tmp_path)
    report = execute(registry, ["half"], BASE_INPUT)
    assert report.failures[0].stage == "init"
    assert report.data == list(BASE_INPUT)


def test_execute_rejects_non_list_result(tmp_path):
    _write_plugin(tmp_path, "weird.py", """
        from plugin_core import Plugin

        class WeirdPlugin(Plugin):
            name = "weird"

            def process(self, data):
                return {"not": "a list"}
    """)
    registry = load_plugins(tmp_path)
    report = execute(registry, ["weird"], BASE_INPUT)
    assert report.failures[0].stage == "process"
    assert "must return a list" in report.failures[0].message


# --------------------------------------------------------------------------- #
# Pipeline, formatting, demo
# --------------------------------------------------------------------------- #
def test_run_pipeline_returns_config_and_report():
    config, report = run_pipeline()
    assert len(config["input"]) == 4
    assert report.order[0] == "echo"
    assert "orphan" in report.skipped


def test_format_report_lines():
    config, report = run_pipeline()
    text = format_report(report, len(config["input"]))
    assert "Execution order" in text
    assert "Skipped         : orphan" in text
    assert "Failure         : faulty" in text
    assert "Records         : 4 in -> 4 out" in text
    assert "Stats plugin    : count=4" in text


def test_run_demo_direct(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Cross-checks OK" in out
    assert "Sandboxed" in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    assert run_demo() == 0
    assert capsys.readouterr().out.count("Demo completed successfully.") == 2


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(capsys):
    assert main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out
    assert "Demo completed successfully." in out


def test_cli_config_path(capsys):
    assert main(["--config", str(DEFAULT_CONFIG)]) == 0
    out = capsys.readouterr().out
    assert "Execution order" in out and "Done." in out


def test_cli_config_missing_file(capsys):
    assert main(["--config", "nope.json"]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_config_invalid_content(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"input": []}), encoding="utf-8")
    assert main(["--config", str(bad)]) == 2
    assert "input contains no records" in capsys.readouterr().err


def test_cli_config_unknown_plugin(tmp_path, capsys):
    path = _config(tmp_path, {"input": BASE_INPUT, "enable": ["ghost"]})
    assert main(["--config", str(path)]) == 2
    assert "unknown plugin" in capsys.readouterr().err


def test_cli_plugins_dir_missing(tmp_path, capsys):
    path = _config(tmp_path, {"input": BASE_INPUT})
    assert main(["--config", str(path),
                 "--plugins", str(tmp_path / "nope")]) == 2
    assert "plugin directory not found" in capsys.readouterr().err


def test_cli_custom_plugins_dir(tmp_path, capsys):
    _make_plugins(tmp_path, {"solo.py": ("SoloPlugin", "solo", ())})
    path = _config(tmp_path, {"input": BASE_INPUT})
    assert main(["--config", str(path), "--plugins", str(tmp_path),
                 "--quiet"]) == 0
    out = capsys.readouterr().out
    assert "Execution order : solo" in out


def test_cli_requires_action(capsys):
    with pytest.raises(SystemExit):
        main([])
    assert "--demo --config" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        main(["--plugins", "some/dir"])


def test_cli_mutually_exclusive_actions(capsys):
    with pytest.raises(SystemExit):
        main(["--demo", "--config", str(DEFAULT_CONFIG)])


def test_cli_demo_quiet_prints_nothing(capsys):
    assert main(["--demo", "--quiet"]) == 0
    assert capsys.readouterr().out == ""
