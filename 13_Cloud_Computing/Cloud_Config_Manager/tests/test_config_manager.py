"""Tests for the Cloud Config Manager project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from config_manager import (  # noqa: E402
    Change,
    ConfigError,
    build_plan,
    deep_merge,
    diff,
    is_secret_path,
    load_config,
    mask_value,
    render_plan,
    run_demo,
    save_config,
    summarize,
    validate_config,
    validate_or_raise,
)
from main import main  # noqa: E402


def _valid_config() -> dict:
    return {
        "project": "shop-api",
        "region": "us-east-1",
        "services": [
            {"name": "web", "image": "nginx:1.25", "replicas": 2,
             "env": {"LOG_LEVEL": "info"}},
        ],
        "storage": {"bucket": "shop-api-assets", "size_gb": 500},
        "budget": 400,
        "tags": {"team": "platform"},
    }


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def test_load_yaml(tmp_path):
    path = tmp_path / "cfg.yaml"
    path.write_text(yaml.safe_dump(_valid_config()), encoding="utf-8")
    assert load_config(path)["project"] == "shop-api"


def test_load_json(tmp_path):
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps(_valid_config()), encoding="utf-8")
    assert load_config(path)["budget"] == 400


def test_load_missing(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.yaml")


def test_load_invalid_yaml(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("key: [unclosed", encoding="utf-8")
    with pytest.raises(ConfigError, match="could not parse"):
        load_config(path)


def test_load_empty(tmp_path):
    path = tmp_path / "empty.yaml"
    path.write_text("", encoding="utf-8")
    with pytest.raises(ConfigError, match="empty"):
        load_config(path)


def test_load_non_mapping(tmp_path):
    path = tmp_path / "list.yaml"
    path.write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="mapping"):
        load_config(path)


def test_save_and_reload_roundtrip(tmp_path):
    target = save_config(_valid_config(), tmp_path / "out.yaml")
    assert load_config(target) == _valid_config()
    json_target = save_config(_valid_config(), tmp_path / "out.json")
    assert load_config(json_target) == _valid_config()


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def test_valid_config_passes():
    assert validate_config(_valid_config()) == []


def test_unknown_top_key():
    config = _valid_config()
    config["rebotes"] = 3
    errors = validate_config(config)
    assert any("unknown top-level key" in e for e in errors)


def test_project_required_and_slug():
    config = _valid_config()
    del config["project"]
    assert any("$.project" in e for e in validate_config(config))
    config["project"] = "Shop API"
    assert any("slug" in e for e in validate_config(config))


def test_region_pattern():
    config = _valid_config()
    config["region"] = "east"
    errors = validate_config(config)
    assert any("$.region" in e and "us-east-1" in e for e in errors)


def test_services_required_non_empty():
    config = _valid_config()
    config["services"] = []
    assert any("$.services" in e for e in validate_config(config))
    config["services"] = "web"
    assert any("$.services" in e for e in validate_config(config))


def test_service_name_and_duplicate():
    config = _valid_config()
    config["services"].append(dict(config["services"][0]))  # duplicate 'web'
    errors = validate_config(config)
    assert any("duplicate service" in e for e in errors)

    config["services"][0]["name"] = "Web!"
    assert any("$.services[0].name" in e for e in validate_config(config))


def test_service_image_required():
    config = _valid_config()
    del config["services"][0]["image"]
    assert any("image" in e for e in validate_config(config))
    config["services"][0]["image"] = "nginx"
    assert any("repo:tag" in e for e in validate_config(config))


def test_service_replicas_range():
    config = _valid_config()
    config["services"][0]["replicas"] = 0
    assert any("replicas" in e for e in validate_config(config))
    config["services"][0]["replicas"] = 999
    assert any("replicas" in e for e in validate_config(config))
    config["services"][0]["replicas"] = True
    assert any("replicas" in e for e in validate_config(config))


def test_service_env_rules():
    config = _valid_config()
    config["services"][0]["env"] = ["A=B"]
    assert any("env" in e for e in validate_config(config))

    config["services"][0]["env"] = {"PORT": 8080.5}
    assert any("PORT" in e for e in validate_config(config))

    config["services"][0]["env"] = {"PORT": 8080, "DEBUG": True, "NAME": "x"}
    assert validate_config(config) == []


def test_service_unknown_key():
    config = _valid_config()
    config["services"][0]["cpu"] = 500
    assert any("unknown service key" in e for e in validate_config(config))


def test_storage_rules():
    config = _valid_config()
    config["storage"] = {"bucket": "BAD NAME", "size_gb": 0}
    errors = validate_config(config)
    assert any("bucket" in e for e in errors)
    assert any("size_gb" in e for e in errors)

    config["storage"] = {"bucket": "ok-bucket", "size_gb": 10, "acl": "public"}
    assert any("unknown storage key" in e for e in validate_config(config))


def test_budget_and_tags_rules():
    config = _valid_config()
    config["budget"] = -1
    assert any("$.budget" in e for e in validate_config(config))
    config["budget"] = "plenty"
    assert any("$.budget" in e for e in validate_config(config))
    config["budget"] = None  # optional -> allowed
    assert validate_config(config) == []

    config["tags"] = {"team": 5}
    assert any("$.tags" in e for e in validate_config(config))


def test_validate_or_raise_lists_all():
    config = {"project": "Bad Name", "region": "east", "services": []}
    with pytest.raises(ConfigError) as excinfo:
        validate_or_raise(config)
    message = str(excinfo)
    assert "3 problem(s)" in message
    assert "$.project" in message and "$.region" in message and "$.services" in message


# --------------------------------------------------------------------------- #
# Deep merge
# --------------------------------------------------------------------------- #
def test_deep_merge_nested():
    base = {"a": {"x": 1, "y": 2}, "b": 1}
    overlay = {"a": {"y": 3, "z": 4}, "c": 5}
    assert deep_merge(base, overlay) == {
        "a": {"x": 1, "y": 3, "z": 4}, "b": 1, "c": 5
    }


def test_deep_merge_replaces_lists_and_scalars():
    base = {"services": [1, 2, 3], "region": "us-east-1"}
    overlay = {"services": [9], "region": "eu-west-1"}
    assert deep_merge(base, overlay) == {"services": [9], "region": "eu-west-1"}


def test_deep_merge_does_not_mutate():
    base = {"a": {"x": 1}}
    overlay = {"a": {"y": 2}}
    deep_merge(base, overlay)
    assert base == {"a": {"x": 1}}
    assert overlay == {"a": {"y": 2}}


def test_deep_merge_empty_overlay():
    base = _valid_config()
    assert deep_merge(base, {}) == base


# --------------------------------------------------------------------------- #
# Diff
# --------------------------------------------------------------------------- #
def test_diff_identical_is_empty():
    config = _valid_config()
    assert diff(config, config) == []


def test_diff_scalar_change():
    # before = observed (current), after = desired (target)
    changes = diff({"a": 1}, {"a": 2})
    assert len(changes) == 1
    assert changes[0].kind == "change"
    assert changes[0].path == "$.a"
    assert changes[0].before == 2 and changes[0].after == 1


def test_diff_add_and_remove():
    changes = diff({"new": "x"}, {"old": "y"})
    kinds = {c.path: c.kind for c in changes}
    assert kinds == {"$.new": "add", "$.old": "remove"}


def test_diff_nested_path():
    changes = diff({"a": {"b": {"c": 1}}}, {"a": {"b": {"c": 2}}})
    assert changes[0].path == "$.a.b.c"


def test_diff_list_by_name():
    desired = {"services": [
        {"name": "web", "replicas": 3},
        {"name": "cache", "replicas": 1},
    ]}
    observed = {"services": [
        {"name": "web", "replicas": 2},
        {"name": "legacy", "replicas": 1},
    ]}
    changes = diff(desired, observed)
    paths = {(c.path, c.kind) for c in changes}
    assert ("$.services[web].replicas", "change") in paths
    assert ("$.services[cache]", "add") in paths
    assert ("$.services[legacy]", "remove") in paths
    assert len(changes) == 3


def test_diff_positional_list_fallback():
    changes = diff({"xs": [1, 2]}, {"xs": [1, 9, 8]})
    kinds = {(c.path, c.kind) for c in changes}
    # positional: index1 changes; observed extras at index2 removed
    assert ("$.xs[1]", "change") in kinds
    assert ("$.xs[2]", "remove") in kinds

    changes = diff({"xs": [1, 5, 6]}, {"xs": [1]})
    kinds = {(c.path, c.kind) for c in changes}
    assert ("$.xs[1]", "add") in kinds
    assert ("$.xs[2]", "add") in kinds


def test_diff_shape_change():
    changes = diff({"a": {"x": 1}}, {"a": "text"})
    assert changes[0].kind == "change"
    assert changes[0].path == "$.a"


# --------------------------------------------------------------------------- #
# Secret masking
# --------------------------------------------------------------------------- #
def test_is_secret_path():
    assert is_secret_path("$.services[api].env.DB_PASSWORD")
    assert is_secret_path("$.api_token")
    assert is_secret_path("$.x.secret")
    assert not is_secret_path("$.region")


def test_mask_value_scalar_and_nested():
    assert mask_value("hunter2", "$.password") == "***"
    added = mask_value({"DB_PASSWORD": "x", "LOG": "info"}, "$.env")
    assert added == {"DB_PASSWORD": "***", "LOG": "info"}
    assert mask_value([{"token": "t"}], "$.items") == [{"token": "***"}]


def test_diff_masks_secret_change():
    changes = diff({"env": {"DB_PASSWORD": "new"}}, {"env": {"DB_PASSWORD": "old"}})
    assert changes[0].before == "***" and changes[0].after == "***"


def test_render_masks_secret_line():
    changes = [Change("$.env.DB_PASSWORD", "change", "***", "***")]
    text = render_plan(changes)
    assert "*** (secret value changed)" in text
    assert "hunter2" not in text


# --------------------------------------------------------------------------- #
# Plan and rendering
# --------------------------------------------------------------------------- #
def test_build_plan_validates_desired():
    with pytest.raises(ConfigError, match="invalid config"):
        build_plan({"project": "x"}, {})


def test_summarize_counts():
    changes = [
        Change("$.a", "add"), Change("$.b", "change"),
        Change("$.c", "remove"), Change("$.d", "add"),
    ]
    assert summarize(changes) == {"add": 2, "remove": 1, "change": 1}


def test_render_no_drift():
    assert "No drift" in render_plan([])


def test_render_plan_sections():
    changes = build_plan(_valid_config(), {"project": "shop-api"})
    text = render_plan(changes)
    assert "Change plan" in text
    assert "to add" in text and "to remove" in text
    assert "$.region" in text


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(tmp_path, capsys):
    assert run_demo(workdir=tmp_path) == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "validate base config -> OK" in out
    assert "deliberately broken config" in out
    assert "drift plan" in out
    assert "self-diff is empty -> True" in out
    assert (tmp_path / "desired.yaml").is_file()


def test_run_demo_is_idempotent(tmp_path, capsys):
    assert run_demo(workdir=tmp_path) == 0
    assert run_demo(workdir=tmp_path) == 0
    out = capsys.readouterr().out
    assert out.count("Demo completed successfully.") == 2


def test_demo_masks_secret_in_plan(tmp_path, capsys):
    assert run_demo(workdir=tmp_path) == 0
    out = capsys.readouterr().out
    assert "DB_PASSWORD" in out
    assert "super-secret-demo" not in out
    assert "rotated-old-value" not in out


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(capsys):
    assert main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_validate_valid(tmp_path, capsys):
    path = save_config(_valid_config(), tmp_path / "ok.yaml")
    assert main(["--validate", str(path)]) == 0
    assert "VALID" in capsys.readouterr().out


def test_cli_validate_invalid(tmp_path, capsys):
    path = save_config({"project": "x"}, tmp_path / "bad.yaml")
    assert main(["--validate", str(path)]) == 2
    err = capsys.readouterr().err
    assert "INVALID" in err and "$.region" in err


def test_cli_validate_missing(tmp_path, capsys):
    assert main(["--validate", str(tmp_path / "nope.yaml")]) == 2
    assert "not found" in capsys.readouterr().err


def _plan_files(tmp_path: Path, drift: bool = True) -> tuple[Path, Path]:
    desired = _valid_config()
    observed = _valid_config()
    if drift:
        observed["region"] = "eu-west-1"
        observed["services"][0]["replicas"] = 5
    return (
        save_config(desired, tmp_path / "desired.yaml"),
        save_config(observed, tmp_path / "observed.yaml"),
    )


def test_cli_plan_clean(tmp_path, capsys):
    desired, observed = _plan_files(tmp_path, drift=False)
    assert main(["--plan", "--desired", str(desired), "--observed", str(observed)]) == 0
    assert "No drift" in capsys.readouterr().out


def test_cli_plan_check_detects_drift(tmp_path, capsys):
    desired, observed = _plan_files(tmp_path, drift=True)
    code = main(["--plan", "--desired", str(desired),
                 "--observed", str(observed), "--check"])
    assert code == 1
    out = capsys.readouterr().out
    assert "$.region" in out and "$.services[web].replicas" in out


def test_cli_plan_without_check_exits_zero(tmp_path, capsys):
    desired, observed = _plan_files(tmp_path, drift=True)
    code = main(["--plan", "--desired", str(desired), "--observed", str(observed)])
    assert code == 0


def test_cli_plan_requires_files(capsys):
    assert main(["--plan"]) == 2
    assert "--desired" in capsys.readouterr().err


def test_cli_plan_invalid_desired(tmp_path, capsys):
    bad = save_config({"project": "x"}, tmp_path / "bad.yaml")
    observed = save_config(_valid_config(), tmp_path / "obs.yaml")
    assert main(["--plan", "--desired", str(bad), "--observed", str(observed)]) == 2
    assert "invalid config" in capsys.readouterr().err


def test_cli_plan_json(tmp_path, capsys):
    desired, observed = _plan_files(tmp_path, drift=True)
    assert main(["--plan", "--desired", str(desired),
                 "--observed", str(observed), "--json"]) == 0
    out = capsys.readouterr().out
    payload = json.loads(out[out.index("{"):out.rindex("}") + 1])
    assert payload["drift"] is True
    assert payload["summary"]["change"] >= 2


def test_cli_merge_to_file(tmp_path, capsys):
    base = save_config(_valid_config(), tmp_path / "base.yaml")
    overlay = save_config({"region": "eu-west-1", "budget": 900},
                          tmp_path / "overlay.yaml")
    out_file = tmp_path / "merged.yaml"
    assert main(["--merge", "--base", str(base), "--overlay", str(overlay),
                 "--out", str(out_file)]) == 0
    merged = load_config(out_file)
    assert merged["region"] == "eu-west-1" and merged["budget"] == 900
    assert validate_config(merged) == []


def test_cli_merge_prints(tmp_path, capsys):
    base = save_config(_valid_config(), tmp_path / "base.yaml")
    overlay = save_config({"budget": 500}, tmp_path / "overlay.yaml")
    assert main(["--merge", "--base", str(base), "--overlay", str(overlay),
                 "--json"]) == 0
    out = capsys.readouterr().out
    payload = json.loads(out[out.index("{"):out.rindex("}") + 1])
    assert payload["budget"] == 500


def test_cli_merge_missing_args(tmp_path, capsys):
    base = save_config(_valid_config(), tmp_path / "base.yaml")
    assert main(["--merge", "--base", str(base)]) == 2
    assert "--overlay" in capsys.readouterr().err


def test_cli_merge_invalid_result(tmp_path, capsys):
    base = save_config(_valid_config(), tmp_path / "base.yaml")
    overlay = save_config({"region": "nope"}, tmp_path / "overlay.yaml")
    assert main(["--merge", "--base", str(base), "--overlay", str(overlay)]) == 2
    assert "invalid" in capsys.readouterr().err
