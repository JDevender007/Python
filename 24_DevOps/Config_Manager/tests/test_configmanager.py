"""Tests for the Config Manager project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from configmanager import (  # noqa: E402
    DEFAULTS_YAML,
    ENV_JSON,
    EXPECTED_KEYS,
    EXPECTED_LAYER_SPLIT,
    SCHEMA_YAML,
    SETTINGS_YAML,
    ConfigError,
    FieldSpec,
    env_key_to_config,
    env_layer,
    flatten,
    load_config,
    load_json,
    load_layer,
    load_schema,
    load_yaml,
    merge_layers,
    render_report,
    run_demo,
    unflatten,
    validate,
)
from main import build_parser, main  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

SCHEMA = {
    "name": FieldSpec("name", "str"),
    "port": FieldSpec("port", "int", min=1, max=65535),
    "ratio": FieldSpec("ratio", "number", min=0.0, max=1.0),
    "debug": FieldSpec("debug", "bool"),
    "level": FieldSpec("level", "str", choices=("INFO", "ERROR")),
    "optional": FieldSpec("optional", "str", required=False),
}

GOOD = {"name": "svc", "port": 8080, "ratio": 0.5, "debug": True,
        "level": "INFO"}


def _write(tmp_path: Path, text: str, name: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# Loading and flattening
# --------------------------------------------------------------------------- #
def test_bundled_files_exist():
    for path in (DEFAULTS_YAML, SETTINGS_YAML, SCHEMA_YAML, ENV_JSON):
        assert path.is_file(), path
    assert DEFAULTS_YAML.parent == DATA_DIR


def test_load_yaml_nested(tmp_path):
    path = _write(tmp_path, "db:\n  host: localhost\n", "c.yaml")
    assert load_yaml(path) == {"db": {"host": "localhost"}}


def test_load_yaml_missing(tmp_path):
    with pytest.raises(ConfigError, match="file not found"):
        load_yaml(tmp_path / "nope.yaml")


def test_load_yaml_invalid(tmp_path):
    path = _write(tmp_path, "a: [1, 2\n", "bad.yaml")
    with pytest.raises(ConfigError, match="invalid YAML"):
        load_yaml(path)


def test_load_yaml_non_mapping(tmp_path):
    path = _write(tmp_path, "- just\n- a list\n", "list.yaml")
    with pytest.raises(ConfigError, match="top level must be a mapping"):
        load_yaml(path)


def test_load_yaml_empty_returns_dict(tmp_path):
    path = _write(tmp_path, "", "empty.yaml")
    assert load_yaml(path) == {}


def test_load_json_ok(tmp_path):
    path = _write(tmp_path, '{"a": 1}', "c.json")
    assert load_json(path) == {"a": 1}


def test_load_json_invalid(tmp_path):
    path = _write(tmp_path, "{oops", "bad.json")
    with pytest.raises(ConfigError, match="invalid JSON"):
        load_json(path)


def test_load_layer_dispatch(tmp_path):
    y = _write(tmp_path, "k: 1", "c.yaml")
    j = _write(tmp_path, '{"k": 2}', "c.json")
    assert load_layer(y) == {"k": 1}
    assert load_layer(j) == {"k": 2}


def test_load_layer_rejects_unknown_extension(tmp_path):
    path = _write(tmp_path, "k: 1", "c.toml")
    with pytest.raises(ConfigError, match="unsupported config format"):
        load_layer(path)


def test_flatten_nested():
    flat = flatten({"a": 1, "db": {"host": "x", "pool": {"size": 5}}})
    assert flat == {"a": 1, "db.host": "x", "db.pool.size": 5}


def test_unflatten_roundtrip():
    flat = {"a": 1, "db.host": "x", "db.pool.size": 5}
    assert flatten(unflatten(flat)) == flat


def test_unflatten_single_key():
    assert unflatten({"db.host": "x"}) == {"db": {"host": "x"}}


# --------------------------------------------------------------------------- #
# Schema
# --------------------------------------------------------------------------- #
def test_load_bundled_schema():
    schema = load_schema(SCHEMA_YAML)
    assert len(schema) == EXPECTED_KEYS
    assert schema["port"].type == "int"
    assert schema["port"].max == 65535
    assert schema["log_level"].choices == ("DEBUG", "INFO", "WARNING",
                                           "ERROR", "CRITICAL")
    assert schema["optional" if "optional" in schema else "app_name"].required


def test_schema_validation_errors(tmp_path):
    bad_type = _write(tmp_path, "k:\n  type: float\n", "s1.yaml")
    with pytest.raises(ConfigError, match="type must be one of"):
        load_schema(bad_type)
    non_map = _write(tmp_path, "k: 3\n", "s2.yaml")
    with pytest.raises(ConfigError, match="must be a mapping"):
        load_schema(non_map)
    unknown = _write(tmp_path, "k:\n  type: str\n  default: x\n", "s3.yaml")
    with pytest.raises(ConfigError, match="unknown field"):
        load_schema(unknown)
    choices = _write(tmp_path, "k:\n  type: str\n  choices: nope\n", "s4.yaml")
    with pytest.raises(ConfigError, match="choices must be a list"):
        load_schema(choices)
    with pytest.raises(ConfigError, match="file not found"):
        load_schema(tmp_path / "nope.yaml")


# --------------------------------------------------------------------------- #
# Validation and coercion
# --------------------------------------------------------------------------- #
def test_validate_good_values():
    assert validate(GOOD, SCHEMA) == GOOD


def test_validate_coerces_numeric_strings():
    out = validate(dict(GOOD, port="9090", ratio="0.25"), SCHEMA)
    assert out["port"] == 9090 and isinstance(out["port"], int)
    assert out["ratio"] == 0.25 and isinstance(out["ratio"], float)


def test_validate_coerces_bool_strings():
    assert validate(dict(GOOD, debug="true"), SCHEMA)["debug"] is True
    assert validate(dict(GOOD, debug="FALSE"), SCHEMA)["debug"] is False
    assert validate(dict(GOOD, debug="yes"), SCHEMA)["debug"] is True
    assert validate(dict(GOOD, debug="0"), SCHEMA)["debug"] is False


def test_validate_rejects_unknown_key_first():
    # unknown key is reported before any value problem
    with pytest.raises(ConfigError, match=r"unknown key\(s\): mystery"):
        validate(dict(GOOD, mystery=1, port="NaN"), SCHEMA)


def test_validate_rejects_missing_required():
    with pytest.raises(ConfigError, match=r"missing required key\(s\): name"):
        validate({k: v for k, v in GOOD.items() if k != "name"}, SCHEMA)


def test_validate_optional_key_may_be_absent():
    out = validate(GOOD, SCHEMA)
    assert "optional" not in out


def test_validate_type_and_coercion_errors():
    with pytest.raises(ConfigError, match="cannot coerce 'abc' to int"):
        validate(dict(GOOD, port="abc"), SCHEMA)
    with pytest.raises(ConfigError, match="cannot coerce '80.5' to int"):
        validate(dict(GOOD, port="80.5"), SCHEMA)
    with pytest.raises(ConfigError, match="key name: expected str, got int"):
        validate(dict(GOOD, name=42), SCHEMA)
    with pytest.raises(ConfigError, match="got bool"):
        validate(dict(GOOD, port=True), SCHEMA)
    with pytest.raises(ConfigError, match="cannot coerce 'maybe' to bool"):
        validate(dict(GOOD, debug="maybe"), SCHEMA)
    with pytest.raises(ConfigError, match="cannot coerce 'wide' to number"):
        validate(dict(GOOD, ratio="wide"), SCHEMA)


def test_validate_bounds():
    with pytest.raises(ConfigError, match="below minimum 1"):
        validate(dict(GOOD, port=0), SCHEMA)
    with pytest.raises(ConfigError, match="above maximum 65535"):
        validate(dict(GOOD, port=70000), SCHEMA)


def test_validate_choices():
    with pytest.raises(ConfigError, match="'NOISE' not in choices"):
        validate(dict(GOOD, level="NOISE"), SCHEMA)


# --------------------------------------------------------------------------- #
# Environment layer
# --------------------------------------------------------------------------- #
def test_env_key_rules():
    assert env_key_to_config("APP_PORT") == "port"
    assert env_key_to_config("APP_DB__HOST") == "db.host"
    assert env_key_to_config("PATH") is None
    with pytest.raises(ConfigError, match="prefix must be non-empty"):
        env_key_to_config("APP_PORT", prefix="")
    with pytest.raises(ConfigError, match="empty key after the prefix"):
        env_key_to_config("APP_")


def test_env_layer_selects_prefixed():
    layer = env_layer({"APP_PORT": "9090", "APP_DB__HOST": "10.0.0.5",
                       "HOME": "/root"})
    assert layer == {"port": "9090", "db.host": "10.0.0.5"}


def test_env_layer_custom_prefix():
    layer = env_layer({"MYAPP_PORT": "1"}, prefix="MYAPP_")
    assert layer == {"port": "1"}


# --------------------------------------------------------------------------- #
# Layered merge + provenance
# --------------------------------------------------------------------------- #
def test_merge_layers_last_wins():
    merged, provenance = merge_layers([
        ("defaults", {"a": 1, "b": 2}),
        ("file:x.yaml", {"b": 3}),
        ("env", {"a": 4}),
    ])
    assert merged == {"a": 4, "b": 3}
    assert provenance == {"a": "env", "b": "file:x.yaml"}


def test_load_config_full_layering():
    environ = load_json(ENV_JSON)
    result = load_config(DEFAULTS_YAML, SCHEMA_YAML,
                         file_path=SETTINGS_YAML, environ=environ)
    assert len(result.values) == EXPECTED_KEYS
    assert result.values["port"] == 9090          # env wins
    assert result.values["log_level"] == "WARNING"  # file wins
    assert result.values["app_name"] == "devops-demo"  # default
    assert result.layer_counts() == EXPECTED_LAYER_SPLIT
    assert result.provenance["port"] == "env:APP_PORT"
    assert result.provenance["retries"] == "file:settings.yaml"
    assert result.provenance["db.port"] == "defaults"


def test_load_config_without_file_layer():
    result = load_config(DEFAULTS_YAML, SCHEMA_YAML, file_path=None)
    assert result.values["port"] == 8080
    assert result.provenance["port"] == "defaults"


def test_load_config_without_env_layer():
    result = load_config(DEFAULTS_YAML, SCHEMA_YAML,
                         file_path=SETTINGS_YAML, environ=None)
    assert result.values["port"] == 8000
    assert result.provenance["port"] == "file:settings.yaml"


def test_load_config_missing_defaults(tmp_path):
    with pytest.raises(ConfigError, match="file not found"):
        load_config(tmp_path / "nope.yaml", SCHEMA_YAML)


def test_load_config_missing_schema(tmp_path):
    with pytest.raises(ConfigError, match="file not found"):
        load_config(DEFAULTS_YAML, tmp_path / "nope.yaml")


def test_load_config_bad_file_layer(tmp_path):
    bad = _write(tmp_path, "port: not-a-number\n", "bad.yaml")
    with pytest.raises(ConfigError, match="cannot coerce"):
        load_config(DEFAULTS_YAML, SCHEMA_YAML, file_path=bad)


def test_load_config_unknown_key_in_file(tmp_path):
    bad = _write(tmp_path, "surprise: 1\n", "extra.yaml")
    with pytest.raises(ConfigError, match="unknown key"):
        load_config(DEFAULTS_YAML, SCHEMA_YAML, file_path=bad)


def test_result_to_dict_and_unflatten():
    result = load_config(DEFAULTS_YAML, SCHEMA_YAML, file_path=SETTINGS_YAML)
    payload = result.to_dict()
    json.dumps(payload)
    assert set(payload) == {"values", "provenance", "layer_counts"}
    nested = result.unflatten()
    assert nested["db"]["host"] == "127.0.0.1"


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def test_render_report_sections():
    result = load_config(DEFAULTS_YAML, SCHEMA_YAML,
                         file_path=SETTINGS_YAML, environ=load_json(ENV_JSON))
    text = render_report(result)
    assert "CONFIG PROVENANCE REPORT" in text
    assert "defaults -> file -> env" in text
    assert "Split        : defaults 3, file 3, env 3" in text
    assert "env:APP_PORT" in text
    assert "file:settings.yaml" in text


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK:" in out
    assert "Demo completed successfully." in out
    assert "CONFIG PROVENANCE REPORT" in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    assert run_demo() == 0
    assert capsys.readouterr().out.count("Demo completed successfully.") == 2


def test_run_demo_missing_defaults(tmp_path):
    with pytest.raises(ConfigError, match="bundled sample not found"):
        run_demo(defaults=tmp_path / "nope.yaml")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(capsys):
    assert main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Cross-checks OK:" in out


def test_cli_file_layering(capsys):
    assert main(["--file", str(SETTINGS_YAML)]) == 0
    out = capsys.readouterr().out
    assert "CONFIG PROVENANCE REPORT" in out and "Done." in out


def test_cli_file_with_env_file(capsys):
    code = main(["--file", str(SETTINGS_YAML),
                 "--env-file", str(ENV_JSON), "--quiet"])
    assert code == 0


def test_cli_json_output(tmp_path, capsys):
    out_json = tmp_path / "cfg.json"
    code = main(["--file", str(SETTINGS_YAML), "--json", str(out_json),
                 "--quiet"])
    assert code == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["values"]["log_level"] == "WARNING"
    assert payload["provenance"]["log_level"] == "file:settings.yaml"
    assert payload["layer_counts"]["defaults"] == 4


def test_cli_missing_file(tmp_path, capsys):
    assert main(["--file", str(tmp_path / "nope.yaml")]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_invalid_config(tmp_path, capsys):
    bad = _write(tmp_path, "port: 70000\n", "bad.yaml")
    assert main(["--file", str(bad)]) == 2
    assert "above maximum" in capsys.readouterr().err


def test_cli_bad_env_file(tmp_path, capsys):
    bad = _write(tmp_path, '{"APP_PORT": 9090}', "env.json")
    assert main(["--file", str(SETTINGS_YAML), "--env-file", str(bad)]) == 2
    assert "must be strings" in capsys.readouterr().err


def test_cli_requires_action(capsys):
    with pytest.raises(SystemExit):
        main([])


def test_cli_rejects_empty_env_prefix(capsys):
    with pytest.raises(SystemExit):
        main(["--demo", "--env-prefix", ""])


def test_cli_quiet_suppresses_report(capsys):
    assert main(["--file", str(SETTINGS_YAML), "--quiet"]) == 0
    assert "CONFIG PROVENANCE REPORT" not in capsys.readouterr().out


def test_build_parser_defaults():
    args = build_parser().parse_args(["--demo"])
    assert args.env_prefix == "APP_"
    assert args.defaults == DEFAULTS_YAML
    assert args.schema == SCHEMA_YAML
    assert not args.quiet


def test_bundled_yaml_roundtrip():
    # bundled files parse to plain dicts and re-serialise cleanly
    defaults = load_yaml(DEFAULTS_YAML)
    assert isinstance(defaults["db"], dict)
    yaml.safe_dump(defaults)
    env = json.loads(ENV_JSON.read_text(encoding="utf-8"))
    assert set(env) == {"APP_PORT", "APP_DEBUG", "APP_DB__HOST"}


def test_cli_demo_quiet_prints_nothing(capsys):
    assert main(["--demo", "--quiet"]) == 0
    assert capsys.readouterr().out == ""
