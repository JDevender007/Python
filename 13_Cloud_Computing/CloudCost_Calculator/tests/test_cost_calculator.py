"""Tests for the Cloud Cost Calculator project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cost_calculator import (  # noqa: E402
    DEFAULT_HOURS,
    PROVIDERS,
    CostError,
    InstancePricing,
    calculate,
    demo_config,
    get_provider,
    load_config,
    plan_comparison,
    price_resource,
    render_report,
    run_demo,
    savings_tips,
    translate_config,
)
from main import main  # noqa: E402


# --------------------------------------------------------------------------- #
# Pricing model
# --------------------------------------------------------------------------- #
def test_instance_hourly_plans():
    shape = InstancePricing("x", 2, 4, 0.10, 0.06, 0.04)
    assert shape.hourly("ondemand") == 0.10
    assert shape.hourly("1yr") == 0.06
    assert shape.hourly("3yr") == 0.04
    with pytest.raises(CostError, match="unknown plan"):
        shape.hourly("5yr")


def test_get_provider():
    assert get_provider("aws").provider == "aws"
    assert get_provider("GCP").provider == "gcp"  # case-insensitive
    with pytest.raises(CostError, match="unknown provider"):
        get_provider("oracle-cloud")


def test_providers_have_consistent_shapes():
    for name, provider in PROVIDERS.items():
        assert provider.instances, name
        assert provider.databases, name
        assert provider.storage, name
        assert provider.bandwidth_out > 0
        for shape in list(provider.instances.values()) + list(provider.databases.values()):
            assert shape.reserved_3yr < shape.reserved_1yr < shape.on_demand


# --------------------------------------------------------------------------- #
# Resource pricing
# --------------------------------------------------------------------------- #
def test_price_compute():
    line = price_resource(
        {"type": "compute", "instance": "t3.medium", "count": 3},
        get_provider("aws"), DEFAULT_HOURS,
    )
    assert line.category == "compute"
    assert line.amount == pytest.approx(3 * 730 * 0.0416, rel=1e-9)
    assert line.plan == "ondemand"


def test_price_compute_custom_hours_and_plan():
    line = price_resource(
        {"type": "compute", "instance": "m5.large", "count": 2,
         "hours": 100, "plan": "3yr"},
        get_provider("aws"), DEFAULT_HOURS,
    )
    assert line.amount == pytest.approx(2 * 100 * 0.0380, rel=1e-9)
    assert line.plan == "3yr"


def test_price_storage():
    line = price_resource(
        {"type": "storage", "class": "gp3", "size_gb": 500},
        get_provider("aws"), DEFAULT_HOURS,
    )
    assert line.amount == pytest.approx(40.0, rel=1e-9)
    assert line.category == "storage"


def test_price_bandwidth():
    line = price_resource(
        {"type": "bandwidth", "gb_out": 2000},
        get_provider("aws"), DEFAULT_HOURS,
    )
    assert line.amount == pytest.approx(180.0, rel=1e-9)


def test_price_database():
    line = price_resource(
        {"type": "database", "instance": "db.m5.large", "count": 1, "plan": "1yr"},
        get_provider("aws"), DEFAULT_HOURS,
    )
    assert line.amount == pytest.approx(730 * 0.1105, rel=1e-9)
    assert line.category == "database"


def test_price_unknown_instance():
    with pytest.raises(CostError, match="unknown compute instance"):
        price_resource({"type": "compute", "instance": "zz.9xlarge"},
                       get_provider("aws"), DEFAULT_HOURS)


def test_price_unknown_storage_class():
    with pytest.raises(CostError, match="unknown storage class"):
        price_resource({"type": "storage", "class": "tape", "size_gb": 10},
                       get_provider("aws"), DEFAULT_HOURS)


def test_price_unknown_type():
    with pytest.raises(CostError, match="unknown resource type"):
        price_resource({"type": "quantum"}, get_provider("aws"), DEFAULT_HOURS)


def test_price_unknown_plan():
    with pytest.raises(CostError, match="unknown plan"):
        price_resource({"type": "compute", "instance": "t3.micro", "plan": "spot"},
                       get_provider("aws"), DEFAULT_HOURS)


def test_price_negative_size():
    with pytest.raises(CostError, match="non-negative"):
        price_resource({"type": "storage", "class": "gp3", "size_gb": -5},
                       get_provider("aws"), DEFAULT_HOURS)


def test_price_count_default_is_one():
    line = price_resource({"type": "compute", "instance": "t3.micro"},
                          get_provider("aws"), DEFAULT_HOURS)
    assert line.amount == pytest.approx(730 * 0.0104, rel=1e-9)


# --------------------------------------------------------------------------- #
# Config loading
# --------------------------------------------------------------------------- #
def test_load_config_ok(tmp_path):
    path = tmp_path / "infra.json"
    path.write_text(json.dumps({"resources": []}), encoding="utf-8")
    assert load_config(path) == {"resources": []}


def test_load_config_missing(tmp_path):
    with pytest.raises(CostError, match="not found"):
        load_config(tmp_path / "nope.json")


def test_load_config_invalid_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(CostError, match="valid JSON"):
        load_config(path)


def test_load_config_missing_resources(tmp_path):
    path = tmp_path / "cfg.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(CostError, match="object"):
        load_config(path)
    path.write_text('{"provider": "aws"}', encoding="utf-8")
    with pytest.raises(CostError, match="resources"):
        load_config(path)


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def test_calculate_totals():
    report = calculate(demo_config())
    assert report.provider == "aws"
    assert report.hours_per_month == DEFAULT_HOURS
    # 3*730*.0416 + 730*.096 + 730*.175 + 500*.08 + 2000*.023 + 2000*.09
    assert report.total == pytest.approx(554.93, abs=0.01)
    assert report.budget_ok is True
    categories = set(report.by_category)
    assert {"compute", "database", "storage", "bandwidth"} == categories
    assert sum(report.by_category.values()) == pytest.approx(report.total, abs=0.05)


def test_calculate_empty_resources():
    report = calculate({"resources": []})
    assert report.total == 0.0
    assert report.budget_ok is True
    assert render_report(report).startswith("Provider : aws")


def test_budget_over():
    config = demo_config()
    config["budget"] = 100
    report = calculate(config)
    assert report.budget_ok is False


def test_calculate_rejects_bad_hours():
    with pytest.raises(CostError, match="hours_per_month"):
        calculate({"resources": [], "hours_per_month": 0})
    with pytest.raises(CostError, match="hours_per_month"):
        calculate({"resources": [], "hours_per_month": 99999})


def test_calculate_rejects_bad_budget():
    with pytest.raises(CostError, match="budget"):
        calculate({"resources": [], "budget": "lots"})


def test_calculate_provider_override():
    config = translate_config(demo_config(), "gcp")
    report = calculate(config)
    assert report.provider == "gcp"
    assert report.total > 0


def test_report_to_dict():
    payload = calculate(demo_config()).to_dict()
    for key in ("provider", "hours_per_month", "items", "by_category",
                "total", "budget", "budget_ok"):
        assert key in payload
    assert payload["items"][0]["category"] == "compute"


# --------------------------------------------------------------------------- #
# Comparison and tips
# --------------------------------------------------------------------------- #
def test_plan_comparison_ordering():
    totals = plan_comparison(demo_config())
    assert totals["3yr"] < totals["1yr"] < totals["ondemand"]
    assert set(totals) == {"ondemand", "1yr", "3yr"}


def test_plan_comparison_does_not_mutate_config():
    config = demo_config()
    before = json.dumps(config, sort_keys=True)
    plan_comparison(config)
    assert json.dumps(config, sort_keys=True) == before


def test_savings_tips_mention_reservations():
    tips = savings_tips(calculate(demo_config()))
    text = " ".join(tips)
    assert "reservation" in text
    assert "t3.medium" in text
    assert "bandwidth" in text or "egress" in text
    assert any("Storage" in t for t in tips)


def test_savings_tips_empty_when_reserved():
    config = {
        "resources": [
            {"type": "compute", "instance": "t3.micro", "count": 1, "plan": "3yr"}
        ]
    }
    assert savings_tips(calculate(config)) == []


def test_translate_config_maps_shapes():
    translated = translate_config(demo_config(), "gcp")
    instances = [r.get("instance") for r in translated["resources"]
                 if r.get("type") == "compute"]
    assert instances == ["e2-medium", "e2-standard-2"]
    classes = [r.get("class") for r in translated["resources"]
               if r.get("type") == "storage"]
    assert classes == ["pd-ssd", "pd-standard"]


def test_translate_config_does_not_mutate():
    config = demo_config()
    translate_config(config, "gcp")
    assert config["provider"] == "aws"
    assert config["resources"][0]["instance"] == "t3.medium"


# --------------------------------------------------------------------------- #
# Rendering and demo
# --------------------------------------------------------------------------- #
def test_render_report_sections():
    text = render_report(calculate(demo_config()))
    assert "Provider : aws" in text
    assert "TOTAL" in text
    assert "By category:" in text
    assert "Budget" in text
    assert "OK" in text


def test_render_report_over_budget_flag():
    config = demo_config()
    config["budget"] = 1
    text = render_report(calculate(config))
    assert "OVER BUDGET" in text


def test_run_demo_direct(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Plan comparison" in out
    assert "Savings tips" in out
    assert "Same footprint on gcp" in out


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
    assert "Demo completed successfully." in out
    assert "TOTAL" in out


def _write_config(tmp_path: Path, budget: int | None = 400) -> Path:
    config = demo_config()
    if budget is None:
        config.pop("budget", None)
    else:
        config["budget"] = budget
    path = tmp_path / "infra.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def test_cli_config_within_budget(tmp_path, capsys):
    path = _write_config(tmp_path, budget=600)
    assert main(["--config", str(path)]) == 0
    out = capsys.readouterr().out
    assert "TOTAL" in out and "Savings tips" in out


def test_cli_config_over_budget(tmp_path, capsys):
    path = _write_config(tmp_path, budget=100)
    assert main(["--config", str(path)]) == 1
    assert "OVER BUDGET" in capsys.readouterr().out


def test_cli_budget_override(tmp_path, capsys):
    path = _write_config(tmp_path, budget=100)
    assert main(["--config", str(path), "--budget", "600"]) == 0
    assert "OK" in capsys.readouterr().out


def test_cli_missing_config(tmp_path, capsys):
    assert main(["--config", str(tmp_path / "nope.json")]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_bad_provider(tmp_path, capsys):
    path = _write_config(tmp_path)
    assert main(["--config", str(path), "--provider", "oracle"]) == 2
    assert "unknown provider" in capsys.readouterr().err


def test_cli_json_output(tmp_path, capsys):
    path = _write_config(tmp_path, budget=600)
    assert main(["--config", str(path), "--json", "--compare"]) == 0
    out = capsys.readouterr().out
    payload = json.loads(out[out.index("{"):out.rindex("}") + 1])
    assert payload["provider"] == "aws"
    assert payload["budget_ok"] is True
    assert set(payload["plan_comparison"]) == {"ondemand", "1yr", "3yr"}


def test_cli_compare_flag(tmp_path, capsys):
    path = _write_config(tmp_path, budget=600)
    assert main(["--config", str(path), "--compare", "--no-tips"]) == 0
    out = capsys.readouterr().out
    assert "Plan comparison" in out
    assert "Savings tips" not in out


def test_cli_negative_budget(tmp_path, capsys):
    path = _write_config(tmp_path)
    assert main(["--config", str(path), "--budget", "-5"]) == 2
    assert "non-negative" in capsys.readouterr().err
