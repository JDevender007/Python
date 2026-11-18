"""Tests for the Cloud Config Manager project."""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

from config_manager import (  # noqa: E402
    DATA_DIR,
    LEGACY_DRIFT,
    LEGACY_MERGE,
    LEGACY_REDACT,
    MAX_REPLICAS,
    MAX_SERVICES,
    MAX_SIZE_GB,
    Change,
    ConfigError,
    audit,
    build_plan,
    count_leaves,
    deep_merge,
    diff,
    is_secret_key,
    leaks,
    load_config,
    mask,
    measure,
    names_of,
    read_configs,
    render_plan,
    report,
    run_demo,
    same,
    service_names,
    shallow_merge,
    summarize,
    validate_config,
    validate_or_raise,
)
from main import main  # noqa: E402


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
def valid() -> dict:
    return {
        "project": "shop-api",
        "region": "us-east-1",
        "services": [
            {
                "name": "web",
                "image": "nginx:1.25",
                "replicas": 2,
                "env": {"LOG_LEVEL": "info"},
            }
        ],
    }


def write(tmp_path: Path, name: str, body: str) -> Path:
    target = tmp_path / name
    target.write_text(body, encoding="utf-8")
    return target


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def test_load_config_reads_the_bundled_desired_document():
    config = load_config(DATA_DIR / "desired.json")
    assert config["project"] == "shop-api"
    assert config["region"] == "us-east-1"
    assert len(config["services"]) == 2


def test_load_config_reads_the_bundled_override_document():
    config = load_config(DATA_DIR / "override.json")
    assert config == {
        "region": "us-west-2",
        "budget": 500,
        "services": [{"name": "api", "replicas": 5}],
        "tags": {"env": "staging"},
    }


def test_load_config_reads_the_bundled_observed_document():
    config = load_config(DATA_DIR / "observed.json")
    assert [item["name"] for item in config["services"]] == ["web", "api", "worker"]


def test_load_config_accepts_a_string_path(tmp_path):
    target = write(tmp_path, "one.json", json.dumps(valid()))
    assert load_config(str(target))["project"] == "shop-api"


def test_load_config_accepts_a_path_object(tmp_path):
    target = write(tmp_path, "one.json", json.dumps(valid()))
    assert load_config(target)["region"] == "us-east-1"


def test_load_config_raises_when_the_file_is_missing(tmp_path):
    with pytest.raises(ConfigError, match="config not found: absent.json"):
        load_config(tmp_path / "absent.json")


def test_load_config_names_the_file_when_the_json_is_broken(tmp_path):
    target = write(tmp_path, "broken.json", '{"project": "shop-api",}')
    with pytest.raises(ConfigError, match="broken.json is not valid JSON: line 1"):
        load_config(target)


def test_load_config_refuses_a_non_ascii_document(tmp_path):
    target = tmp_path / "emoji.json"
    target.write_bytes(b'{"project": "sh\xc3\xb6p"}')
    with pytest.raises(ConfigError, match="emoji.json is not ASCII text"):
        load_config(target)


def test_load_config_refuses_a_list_root(tmp_path):
    target = write(tmp_path, "list.json", "[]")
    with pytest.raises(ConfigError, match="a config root must be a mapping"):
        load_config(target)


def test_load_config_refuses_a_scalar_root(tmp_path):
    target = write(tmp_path, "scalar.json", "42")
    with pytest.raises(ConfigError, match="a config root must be a mapping"):
        load_config(target)


def test_load_config_refuses_a_null_root(tmp_path):
    target = write(tmp_path, "null.json", "null")
    with pytest.raises(ConfigError, match="a config root must be a mapping"):
        load_config(target)


def test_read_configs_defaults_to_the_bundled_trio():
    desired, override, observed = read_configs()
    assert desired["project"] == "shop-api"
    assert override["region"] == "us-west-2"
    assert [item["name"] for item in observed["services"]] == ["web", "api", "worker"]


def test_read_configs_returns_three_documents_in_a_fixed_order():
    bundle = read_configs()
    assert len(bundle) == 3
    assert all(isinstance(document, dict) for document in bundle)
    assert bundle[0]["services"][0]["name"] == "web"


def test_read_configs_honours_explicit_paths(tmp_path):
    desired = write(tmp_path, "d.json", json.dumps(valid()))
    override = write(tmp_path, "o.json", '{"region": "eu-west-1"}')
    observed = write(tmp_path, "s.json", json.dumps(valid()))
    first, second, third = read_configs(desired, override, observed)
    assert first["region"] == "us-east-1"
    assert second["region"] == "eu-west-1"
    assert third["region"] == "us-east-1"


def test_read_configs_keeps_missing_file_errors(tmp_path):
    with pytest.raises(ConfigError, match="config not found"):
        read_configs(tmp_path / "nope.json", None, None)


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def test_a_minimal_config_is_valid():
    assert validate_config(valid()) == []


def test_the_bundled_desired_config_is_valid():
    assert validate_config(load_config(DATA_DIR / "desired.json")) == []


def test_the_bundled_observed_config_is_valid():
    assert validate_config(load_config(DATA_DIR / "observed.json")) == []


def test_the_override_alone_is_not_a_valid_config():
    problems = validate_config(load_config(DATA_DIR / "override.json"))
    assert any("$.services" in item for item in problems)
    assert any("$.project" in item for item in problems)


def test_a_non_mapping_config_is_reported_not_raised():
    assert validate_config([]) == ["$: a config is a mapping"]


def test_an_unknown_top_level_key_is_reported():
    config = valid()
    config["extra"] = 1
    assert "$.extra: unknown top-level key" in validate_config(config)


def test_a_non_slug_project_is_reported():
    config = valid()
    config["project"] = "Shop API"
    assert any("$.project" in item for item in validate_config(config))


def test_a_missing_project_is_reported():
    config = valid()
    del config["project"]
    assert any("$.project" in item for item in validate_config(config))


def test_a_non_slug_region_is_reported():
    config = valid()
    config["region"] = "east"
    assert any("$.region" in item for item in validate_config(config))


def test_a_region_with_a_digit_suffix_is_accepted():
    config = valid()
    config["region"] = "ap-southeast-2"
    assert validate_config(config) == []


def test_an_empty_service_list_is_reported():
    config = valid()
    config["services"] = []
    assert any("$.services: a non-empty array" in item for item in validate_config(config))


def test_a_non_list_services_key_is_reported():
    config = valid()
    config["services"] = {"name": "web"}
    assert any("$.services: a non-empty array" in item for item in validate_config(config))


def test_too_many_services_is_reported():
    config = valid()
    config["services"] = [
        {"name": f"svc-{index}", "image": "nginx:1", "replicas": 1}
        for index in range(MAX_SERVICES + 1)
    ]
    assert any(f"at most {MAX_SERVICES} services" in item for item in validate_config(config))


def test_the_service_cap_itself_is_allowed():
    config = valid()
    config["services"] = [
        {"name": f"svc-{index}", "image": "nginx:1", "replicas": 1}
        for index in range(MAX_SERVICES)
    ]
    assert validate_config(config) == []


def test_a_non_object_service_is_reported_with_an_index():
    config = valid()
    config["services"] = ["web"]
    assert any("$.services[0]: a service is an object" in item for item in validate_config(config))


def test_a_duplicate_service_name_is_reported():
    config = valid()
    config["services"].append(dict(config["services"][0]))
    assert any("duplicate service 'web'" in item for item in validate_config(config))


def test_a_bad_service_name_is_reported():
    config = valid()
    config["services"][0]["name"] = "Web_1"
    assert any("$.services[0].name" in item for item in validate_config(config))


def test_an_image_without_a_tag_is_reported():
    config = valid()
    config["services"][0]["image"] = "nginx"
    assert any("$.services[0].image" in item for item in validate_config(config))


def test_a_zero_replica_count_is_reported():
    config = valid()
    config["services"][0]["replicas"] = 0
    assert any("$.services[0].replicas" in item for item in validate_config(config))


def test_a_boolean_replica_count_is_refused():
    config = valid()
    config["services"][0]["replicas"] = True
    assert any("$.services[0].replicas" in item for item in validate_config(config))


def test_the_replica_cap_is_inclusive():
    config = valid()
    config["services"][0]["replicas"] = MAX_REPLICAS
    assert validate_config(config) == []


def test_a_replica_count_above_the_cap_is_reported():
    config = valid()
    config["services"][0]["replicas"] = MAX_REPLICAS + 1
    assert any("$.services[0].replicas" in item for item in validate_config(config))


def test_a_non_mapping_env_is_reported():
    config = valid()
    config["services"][0]["env"] = ["LOG_LEVEL=info"]
    assert any("env: a mapping is required" in item for item in validate_config(config))


def test_a_non_scalar_env_value_is_reported():
    config = valid()
    config["services"][0]["env"]["NESTED"] = {"a": 1}
    assert any("env.NESTED: a scalar is required" in item for item in validate_config(config))


def test_an_env_without_a_mapping_is_accepted():
    config = valid()
    del config["services"][0]["env"]
    assert validate_config(config) == []


def test_a_valid_storage_block_is_accepted():
    config = valid()
    config["storage"] = {"bucket": "shop-assets", "size_gb": 10, "versioning": True}
    assert validate_config(config) == []


def test_a_non_mapping_storage_block_is_reported():
    config = valid()
    config["storage"] = "shop-assets"
    assert "$.storage: a mapping is required" in validate_config(config)


def test_a_bad_bucket_name_is_reported():
    config = valid()
    config["storage"] = {"bucket": "Shop_Assets", "size_gb": 10}
    assert any("$.storage.bucket" in item for item in validate_config(config))


def test_a_zero_storage_size_is_reported():
    config = valid()
    config["storage"] = {"bucket": "shop-assets", "size_gb": 0}
    assert any("$.storage.size_gb" in item for item in validate_config(config))


def test_the_storage_cap_is_inclusive():
    config = valid()
    config["storage"] = {"bucket": "shop-assets", "size_gb": MAX_SIZE_GB}
    assert validate_config(config) == []


def test_a_storage_size_above_the_cap_is_reported():
    config = valid()
    config["storage"] = {"bucket": "shop-assets", "size_gb": MAX_SIZE_GB + 1}
    assert any("$.storage.size_gb" in item for item in validate_config(config))


def test_an_unknown_storage_key_is_reported():
    config = valid()
    config["storage"] = {"bucket": "shop-assets", "size_gb": 10, "class": "cold"}
    assert "$.storage.class: unknown storage key" in validate_config(config)


def test_a_negative_budget_is_reported():
    config = valid()
    config["budget"] = -1
    assert any("$.budget" in item for item in validate_config(config))


def test_a_boolean_budget_is_reported():
    config = valid()
    config["budget"] = False
    assert any("$.budget" in item for item in validate_config(config))


def test_a_zero_budget_is_accepted():
    config = valid()
    config["budget"] = 0
    assert validate_config(config) == []


def test_a_non_mapping_tags_block_is_reported():
    config = valid()
    config["tags"] = ["team"]
    assert "$.tags: a mapping is required" in validate_config(config)


def test_non_text_tag_values_are_reported():
    config = valid()
    config["tags"] = {"team": 3}
    assert any("$.tags: keys and values must be text" in item for item in validate_config(config))


def test_problems_accumulate_instead_of_stopping_at_the_first():
    problems = validate_config({"project": "X", "region": "east", "services": []})
    assert len(problems) >= 3
    assert all(isinstance(item, str) for item in problems)


def test_validate_or_raise_names_the_problem_count():
    config = {"project": "X", "region": "east", "services": []}
    with pytest.raises(ConfigError, match=r"invalid config \(3 problem"):
        validate_or_raise(config)


def test_validate_or_raise_returns_none_for_a_valid_config():
    assert validate_or_raise(valid()) is None


# --------------------------------------------------------------------------- #
# Leaf counting and names
# --------------------------------------------------------------------------- #
def test_count_leaves_counts_scalars():
    assert count_leaves({"a": 1, "b": "two"}) == 2


def test_count_leaves_walks_nested_mappings():
    assert count_leaves({"a": {"b": {"c": 1}}}) == 1


def test_count_leaves_walks_lists():
    assert count_leaves({"a": [1, 2, 3]}) == 3


def test_count_leaves_counts_an_empty_container_as_one_value():
    assert count_leaves({}) == 1
    assert count_leaves([]) == 1


def test_count_leaves_of_the_bundled_desired_config_is_18():
    assert count_leaves(load_config(DATA_DIR / "desired.json")) == 18


def test_count_leaves_of_the_bundled_observed_config_is_21():
    assert count_leaves(load_config(DATA_DIR / "observed.json")) == 21


def test_names_of_returns_the_names_in_order():
    assert names_of([{"name": "web"}, {"name": "api"}]) == ["web", "api"]


def test_names_of_refuses_a_list_without_names():
    assert names_of([{"name": "web"}, {"image": "nginx:1"}]) is None


def test_names_of_refuses_duplicate_names():
    assert names_of([{"name": "web"}, {"name": "web"}]) is None


def test_names_of_refuses_non_object_entries():
    assert names_of(["web"]) is None


def test_names_of_refuses_an_empty_name():
    assert names_of([{"name": ""}]) is None


def test_names_of_accepts_an_empty_list():
    assert names_of([]) == []


def test_service_names_reads_the_bundled_desired_config():
    assert service_names(load_config(DATA_DIR / "desired.json")) == ["web", "api"]


def test_service_names_is_empty_for_a_config_without_services():
    assert service_names({}) == []


def test_service_names_is_empty_for_an_unnamed_service_list():
    assert service_names({"services": [{"image": "nginx:1"}]}) == []


# --------------------------------------------------------------------------- #
# Merging
# --------------------------------------------------------------------------- #
def test_deep_merge_keeps_sibling_keys():
    merged = deep_merge({"a": 1, "b": 2}, {"b": 3})
    assert merged == {"a": 1, "b": 3}


def test_deep_merge_recurses_into_mappings():
    merged = deep_merge({"tags": {"team": "platform", "env": "prod"}}, {"tags": {"env": "staging"}})
    assert merged == {"tags": {"team": "platform", "env": "staging"}}


def test_deep_merge_replaces_a_scalar_with_a_mapping():
    assert deep_merge({"a": 1}, {"a": {"b": 2}}) == {"a": {"b": 2}}


def test_deep_merge_replaces_a_mapping_with_a_scalar():
    assert deep_merge({"a": {"b": 2}}, {"a": 1}) == {"a": 1}


def test_deep_merge_replaces_an_unnamed_list():
    assert deep_merge({"ports": [1, 2]}, {"ports": [3]}) == {"ports": [3]}


def test_deep_merge_merges_named_entries_by_identity():
    base = {"services": [{"name": "web", "replicas": 2}, {"name": "api", "replicas": 3}]}
    overlay = {"services": [{"name": "api", "replicas": 5}]}
    assert deep_merge(base, overlay)["services"] == [
        {"name": "web", "replicas": 2},
        {"name": "api", "replicas": 5},
    ]


def test_deep_merge_keeps_named_entries_the_overlay_never_mentions():
    merged = deep_merge(
        {"services": [{"name": "web", "image": "nginx:1.25"}]},
        {"services": [{"name": "api", "image": "api:1"}]},
    )
    assert merged["services"] == [
        {"name": "web", "image": "nginx:1.25"},
        {"name": "api", "image": "api:1"},
    ]


def test_deep_merge_preserves_base_order_not_overlay_order():
    merged = deep_merge(
        {"services": [{"name": "web"}, {"name": "api"}]},
        {"services": [{"name": "api", "replicas": 5}, {"name": "web", "replicas": 9}]},
    )
    assert [item["name"] for item in merged["services"]] == ["web", "api"]


def test_deep_merge_does_not_zip_different_names_by_position():
    merged = deep_merge(
        {"services": [{"name": "web", "image": "nginx:1.25"}]},
        {"services": [{"name": "api", "image": "api:1"}]},
    )
    assert merged["services"][0] == {"name": "web", "image": "nginx:1.25"}


def test_deep_merge_survives_a_bundled_overlay():
    desired = load_config(DATA_DIR / "desired.json")
    override = load_config(DATA_DIR / "override.json")
    merged = deep_merge(desired, override)
    assert count_leaves(merged) == 18
    assert len(merged["services"]) == 2
    assert merged["services"][1]["replicas"] == 5
    assert merged["services"][1]["image"] == "ghcr.io/shop/api:1.4.2"
    assert merged["services"][1]["env"]["DB_PASSWORD"] == "demo-secret-token"


def test_deep_merge_is_structural_and_never_aliases_an_input():
    base = {"tags": {"team": "platform"}, "services": [{"name": "web"}]}
    merged = deep_merge(base, {"tags": {"env": "prod"}})
    merged["tags"]["team"] = "changed"
    merged["services"][0]["name"] = "changed"
    assert base == {"tags": {"team": "platform"}, "services": [{"name": "web"}]}


def test_deep_merge_leaves_the_override_untouched():
    override = {"tags": {"env": "staging"}}
    merged = deep_merge({"tags": {"team": "platform"}}, override)
    merged["tags"]["env"] = "prod"
    assert override == {"tags": {"env": "staging"}}


def test_deep_merge_refuses_a_non_mapping_base():
    with pytest.raises(ConfigError, match=r"\$: a merge needs two mappings"):
        deep_merge([], {})


def test_a_list_over_a_mapping_replaces_it_without_recursing():
    merged = deep_merge({"a": {"b": 1}}, {"a": [1, 2]})
    assert merged == {"a": [1, 2]}


def test_deep_merge_accepts_an_empty_overlay():
    assert deep_merge({"a": 1}, {}) == {"a": 1}


def test_shallow_merge_replaces_a_whole_list():
    base = {"services": [{"name": "web"}, {"name": "api"}]}
    overlay = {"services": [{"name": "api", "replicas": 5}]}
    merged = shallow_merge(base, overlay)
    assert len(merged["services"]) == 1


def test_shallow_merge_loses_the_tags_sibling():
    merged = shallow_merge({"tags": {"team": "platform", "env": "prod"}}, {"tags": {"env": "staging"}})
    assert merged["tags"] == {"env": "staging"}


def test_shallow_merge_of_the_bundle_keeps_only_9_leaves():
    desired = load_config(DATA_DIR / "desired.json")
    override = load_config(DATA_DIR / "override.json")
    assert count_leaves(shallow_merge(desired, override)) == 9


def test_shallow_merge_of_the_bundle_keeps_one_service():
    desired = load_config(DATA_DIR / "desired.json")
    override = load_config(DATA_DIR / "override.json")
    merged = shallow_merge(desired, override)
    assert [item["name"] for item in merged["services"]] == ["api"]


def test_shallow_merge_refuses_a_non_mapping():
    with pytest.raises(ConfigError, match="a merge needs two mappings"):
        shallow_merge([], {})


def test_merge_lists_replaces_unnamed_lists():
    assert deep_merge({"a": [1]}, {"a": [2, 3]}) == {"a": [2, 3]}


def test_merge_lists_does_not_merge_named_with_unnamed():
    assert deep_merge({"a": [{"name": "web"}]}, {"a": [1, 2]}) == {"a": [1, 2]}


# --------------------------------------------------------------------------- #
# Redaction
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "key",
    ["DB_PASSWORD", "db_password", "API_TOKEN", "client_secret", "api_key", "AWS_CREDENTIAL"],
)
def test_secret_key_hints_are_recognised(key):
    assert is_secret_key(key) is True


@pytest.mark.parametrize("key", ["LOG_LEVEL", "replicas", "bucket", "team", "region"])
def test_plain_keys_are_not_secret(key):
    assert is_secret_key(key) is False


def test_mask_redacts_a_secret_named_key():
    assert mask({"DB_PASSWORD": "s3cret"}) == {"DB_PASSWORD": "***"}


def test_mask_walks_into_lists_of_named_objects():
    masked = mask({"services": [{"name": "api", "env": {"API_TOKEN": "abc"}}]})
    assert masked == {"services": [{"name": "api", "env": {"API_TOKEN": "***"}}]}


def test_mask_leaves_ordinary_values_alone():
    masked = mask({"region": "us-east-1", "replicas": 2})
    assert masked == {"region": "us-east-1", "replicas": 2}


def test_mask_redacts_a_scalar_whose_path_names_a_secret():
    assert mask("s3cret", "$.services[api].env.DB_PASSWORD") == "***"


def test_mask_keeps_a_top_level_secret_at_the_same_key():
    masked = mask({"client_secret": "abc", "team": "platform"})
    assert masked == {"client_secret": "***", "team": "platform"}


def test_mask_of_a_plain_scalar_is_the_scalar():
    assert mask("us-east-1") == "us-east-1"


def test_leaks_finds_a_surviving_secret():
    assert leaks("password=s3cret", ["s3cret"]) == ["s3cret"]


def test_leaks_returns_nothing_when_every_secret_is_masked():
    assert leaks("DB_PASSWORD: ***", ["s3cret", "other"]) == []


def test_leaks_ignores_empty_secret_strings():
    assert leaks("anything", ["", "s3cret"]) == []


def test_secret_values_are_collected_from_both_bundled_documents():
    measured = measure()
    assert measured["secrets"] == ["demo-secret-token", "rotated-old-value"]


def test_the_rendered_plan_contains_no_secret_value():
    measured = measure()
    assert measured["leaks"] == []
    assert "demo-secret-token" not in measured["rendered"]
    assert "rotated-old-value" not in measured["rendered"]


def test_the_rendered_plan_still_names_the_secret_key():
    assert "DB_PASSWORD" in measure()["rendered"]


# --------------------------------------------------------------------------- #
# Type-strict equality and drift
# --------------------------------------------------------------------------- #
def test_same_is_true_for_identical_scalars():
    assert same(2, 2) is True
    assert same("a", "a") is True


def test_same_refuses_true_against_one():
    assert same(True, 1) is False


def test_same_refuses_false_against_zero():
    assert same(False, 0) is False


def test_same_refuses_two_different_values():
    assert same(1, 2) is False


def test_diff_is_empty_for_identical_documents():
    assert diff({"a": 1}, {"a": 1}) == []


def test_diff_reports_one_change_for_a_scalar():
    changes = diff({"a": 1}, {"a": 2})
    assert changes == [Change("$.a", "change", 2, 1)]


def test_diff_reports_an_add_for_a_key_only_in_the_desired_document():
    changes = diff({"a": 1, "b": 2}, {"a": 1})
    assert changes == [Change("$.b", "add", None, 2)]


def test_diff_reports_a_remove_for_a_key_only_in_the_observed_document():
    changes = diff({"a": 1}, {"a": 1, "b": 2})
    assert changes == [Change("$.b", "remove", 2, None)]


def test_diff_walks_the_union_of_keys():
    changes = diff({"a": {"b": 1}}, {"a": {"c": 2}})
    assert [(item.path, item.kind) for item in changes] == [
        ("$.a.b", "add"),
        ("$.a.c", "remove"),
    ]


def test_diff_reports_a_type_difference_as_drift():
    assert diff({"versioning": False}, {"versioning": 0}) != []


def test_diff_keeps_a_named_list_aligned_by_name():
    changes = diff(
        {"services": [{"name": "web", "image": "nginx:1.25"}]},
        {"services": [{"name": "web", "image": "nginx:1.24"}]},
    )
    assert changes == [Change("$.services[web].image", "change", "nginx:1.24", "nginx:1.25")]


def test_diff_reports_a_missing_named_entry_as_an_add():
    changes = diff(
        {"services": [{"name": "web"}, {"name": "api"}]},
        {"services": [{"name": "web"}]},
    )
    assert changes == [Change("$.services[api]", "add", None, {"name": "api"})]


def test_diff_reports_an_extra_named_entry_as_a_remove():
    changes = diff(
        {"services": [{"name": "web"}]},
        {"services": [{"name": "web"}, {"name": "worker", "replicas": 1}]},
    )
    assert changes == [
        Change("$.services[worker]", "remove", {"name": "worker", "replicas": 1}, None)
    ]


def test_diff_compares_unnamed_lists_by_index():
    changes = diff({"ports": [80, 443]}, {"ports": [80]})
    assert changes == [Change("$.ports[1]", "add", None, 443)]


def test_diff_reports_a_removed_unnamed_list_item():
    changes = diff({"ports": [80]}, {"ports": [80, 443]})
    assert changes == [Change("$.ports[1]", "remove", 443, None)]


def test_diff_never_puts_a_secret_in_a_change():
    changes = diff({"env": {"DB_PASSWORD": "new"}}, {"env": {"DB_PASSWORD": "old"}})
    assert changes[0].before == "***"
    assert changes[0].after == "***"


def test_the_bundled_plan_names_eight_paths_in_order():
    measured = measure()
    assert measured["paths"] == [
        "$.region",
        "$.services[web].image",
        "$.services[api].replicas",
        "$.services[api].env.DB_PASSWORD",
        "$.services[worker]",
        "$.storage.versioning",
        "$.budget",
        "$.tags.env",
    ]


def test_the_bundled_plan_has_six_changes_one_add_and_one_remove():
    assert measure()["counts"] == {"add": 1, "change": 6, "remove": 1}


def test_build_plan_validates_the_desired_document_first():
    with pytest.raises(ConfigError, match="invalid config"):
        build_plan({"project": "Shop API"}, {})


def test_build_plan_refuses_a_non_mapping_observed_state():
    with pytest.raises(ConfigError, match="an observed state is a mapping"):
        build_plan(valid(), [])


def test_build_plan_of_the_bundle_matches_measure():
    desired = load_config(DATA_DIR / "desired.json")
    override = load_config(DATA_DIR / "override.json")
    observed = load_config(DATA_DIR / "observed.json")
    plan = build_plan(deep_merge(desired, override), observed)
    assert [item.to_dict()["path"] for item in plan] == measure()["paths"]


def test_summarize_counts_every_kind_even_at_zero():
    assert summarize([]) == {"add": 0, "change": 0, "remove": 0}


def test_summarize_counts_the_bundled_plan():
    assert summarize(measure()["plan"]) == {"add": 1, "change": 6, "remove": 1}


def test_summarize_refuses_an_unknown_kind():
    with pytest.raises(ConfigError, match="unknown change kind"):
        summarize([Change("$.a", "rename", 1, 2)])


def test_a_change_reports_itself_as_a_dict():
    assert Change("$.a", "change", 1, 2).to_dict() == {
        "path": "$.a",
        "kind": "change",
        "before": 1,
        "after": 2,
    }


def test_a_change_is_frozen():
    change = Change("$.a", "change", 1, 2)
    with pytest.raises(Exception):
        change.kind = "add"  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def test_render_plan_says_there_is_no_drift_for_an_empty_plan():
    assert render_plan([]) == "No drift: the observed state matches the desired configuration."


def test_render_plan_counts_the_three_kinds_in_its_header():
    header = render_plan(measure()["plan"]).splitlines()[0]
    assert header == "Change plan: 1 to add, 6 to update, 1 to remove"


def test_render_plan_marks_an_add_with_a_plus():
    rendered = render_plan([Change("$.tags.env", "add", None, "staging")])
    assert "  + $.tags.env = 'staging'" in rendered


def test_render_plan_marks_a_remove_with_a_minus():
    rendered = render_plan([Change("$.services[worker]", "remove", {"name": "worker"}, None)])
    assert '  - $.services[worker] (was {"name": "worker"})' in rendered


def test_render_plan_renders_a_scalar_change():
    rendered = render_plan([Change("$.budget", "change", 400, 500)])
    assert "  ~ $.budget: 400 -> 500" in rendered


def test_render_plan_renders_a_secret_change_without_values():
    rendered = render_plan([Change("$.services[api].env.DB_PASSWORD", "change", "***", "***")])
    assert "  ~ $.services[api].env.DB_PASSWORD: *** (secret value changed)" in rendered
    assert "demo-secret-token" not in rendered


def test_render_plan_formats_a_mapping_change_with_json():
    rendered = render_plan([Change("$.a", "change", {"a": 1}, {"a": 2})])
    assert '{"a": 2}' in rendered


def test_render_plan_starts_with_a_blank_line_after_the_header():
    lines = render_plan(measure()["plan"]).splitlines()
    assert lines[1] == ""


# --------------------------------------------------------------------------- #
# Measurement and the JSON report
# --------------------------------------------------------------------------- #
def test_measure_returns_the_five_leaf_counts():
    assert measure()["leaves"] == {"desired": 18, "merged": 18, "legacy": 9, "observed": 21}


def test_measure_counts_services_for_every_view():
    assert measure()["services"] == {"desired": 2, "merged": 2, "legacy": 1}


def test_measure_keeps_the_service_order_through_the_merge():
    measured = measure()
    assert measured["merged_service_names"] == ["web", "api"]
    assert measured["legacy_service_names"] == ["api"]


def test_measure_names_every_leaf_of_the_plan():
    measured = measure()
    assert len(measured["paths"]) == len(measured["plan"]) == 8


def test_measure_proves_the_base_document_is_not_mutated():
    measured = measure()
    assert measured["desired"]["region"] == "us-east-1"
    assert measured["desired"]["services"][1]["replicas"] == 3
    assert measured["desired"]["tags"] == {"team": "platform", "env": "prod"}


def test_measure_pins_the_type_strict_demonstration():
    measured = measure()
    assert measured["loose_equal"] is True
    assert measured["same_type"] is False


def test_report_is_json_safe():
    body = json.loads(json.dumps(report(measure())))
    assert body["changes"] == 8
    assert body["counts"] == {"add": 1, "change": 6, "remove": 1}


def test_report_holds_no_config_object_and_no_secret():
    text = json.dumps(report(measure()))
    assert "demo-secret-token" not in text
    assert "rotated-old-value" not in text
    assert "merged" not in json.loads(text)


def test_report_keeps_the_plan_as_dicts():
    body = report(measure())
    assert isinstance(body["plan"][0], dict)
    assert body["plan"][0]["path"] == "$.region"


def test_measure_is_deterministic_across_calls():
    first = measure()
    second = measure()
    assert first["paths"] == second["paths"]
    assert first["merged"] == second["merged"]
    assert first["rendered"] == second["rendered"]


# --------------------------------------------------------------------------- #
# Audit and its negative controls
# --------------------------------------------------------------------------- #
def test_audit_reports_sixteen_checks_and_all_pass():
    results = audit(measure())
    assert len(results) == 16
    assert [name for name, okay in results if not okay] == []


def test_every_audit_check_has_a_name():
    assert all(isinstance(name, str) and name for name, _ in audit(measure()))


def test_a_shallow_merge_flips_the_leaf_check():
    results = dict(audit(measure(), merge=shallow_merge))
    assert results["a_recursive_merge_keeps_every_leaf"] is False
    assert results["a_named_list_merges_by_identity"] is False


def test_a_broken_reread_flips_the_path_check():
    desired, override, observed = read_configs()
    extra = {"tags": {"env": "staging", "tier": "gold"}}
    results = dict(audit(measure(), reread=lambda: (desired, extra, observed)))
    assert results["the_plan_is_one_change_per_path"] is False
    assert results["the_change_kinds_are_pinned"] is False


def test_an_unreadable_reread_fails_checks_instead_of_raising():
    def explode():
        raise RuntimeError("disk gone")

    results = dict(audit(measure(), reread=explode))
    assert results["all_three_documents_load"] is False
    assert any(value is False for value in results.values())


def test_a_tampered_leaf_count_flips_the_shallow_merge_check():
    measured = measure()
    measured["leaves"]["legacy"] = 18
    results = dict(audit(measured))
    assert results["a_shallow_merge_loses_half_the_leaves"] is False


def test_a_tampered_service_count_flips_the_service_check():
    measured = measure()
    measured["services"]["merged"] = 3
    results = dict(audit(measured))
    assert results["a_shallow_merge_replaces_the_service_list"] is False


def test_the_audit_rebuilds_the_plan_instead_of_trusting_the_summary():
    measured = measure()
    measured["rendered"] = "unmasked demo-secret-token"
    measured["secrets"] = []
    results = dict(audit(measured))
    assert results["a_secret_is_masked_at_any_depth"] is True


def test_a_secret_left_in_the_plan_flips_the_mask_check():
    desired = dict(read_configs()[0])
    polluted = dict(desired)
    polluted["tags"] = {"leak": "demo-secret-token"}
    results = dict(audit(measure(), reread=lambda: (polluted, {}, {})))
    assert results["a_secret_is_masked_at_any_depth"] is False


def test_the_bundled_audit_checks_the_pinned_paths():
    results = dict(audit(measure()))
    for name in (
        "the_plan_is_one_change_per_path",
        "a_missing_key_is_an_add_and_an_extra_one_is_a_remove",
        "a_type_difference_is_drift_even_when_equality_says_no",
        "both_sides_of_a_secret_change_are_masked",
        "a_bad_config_is_refused",
        "rebuild_is_deterministic",
    ):
        assert results[name] is True


# --------------------------------------------------------------------------- #
# The demo contract
# --------------------------------------------------------------------------- #
def test_run_demo_returns_zero_and_ends_with_the_two_contract_lines(capsys):
    assert run_demo() == 0
    lines = capsys.readouterr().out.rstrip("\n").splitlines()
    assert lines[-1] == "Demo completed successfully."
    assert lines[-2].startswith("Cross-checks OK: ")


def test_run_demo_is_byte_identical_across_runs(capsys):
    assert run_demo() == 0
    first = capsys.readouterr().out
    assert run_demo() == 0
    second = capsys.readouterr().out
    assert first == second


def test_run_demo_prints_the_three_legacy_shortcuts(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert LEGACY_MERGE in out
    assert LEGACY_DRIFT in out
    assert LEGACY_REDACT in out


def test_run_demo_prints_the_pinned_pairs(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "leaves: desired 18, shallow 9, deep 18" in out
    assert "8 changes (6 change, 1 add, 1 remove)" in out
    assert "16/16 checks pass" in out


def test_run_demo_reports_no_secret_leak(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "demo-secret-token" not in out
    assert "rotated-old-value" not in out


# --------------------------------------------------------------------------- #
# Command line
# --------------------------------------------------------------------------- #
def test_cli_demo_returns_zero():
    assert main(["--demo"]) == 0


def test_cli_demo_quiet_prints_nothing(capsys):
    assert main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_cli_demo_quiet_is_silent_even_when_the_bundle_is_broken():
    assert main(["--demo", "--quiet"]) == 0
    captured = io.StringIO()
    with redirect_stdout(captured), redirect_stderr(captured):
        assert main(["--demo", "--quiet"]) == 0
    assert captured.getvalue() == ""


def test_cli_audit_returns_zero_when_every_check_passes(capsys):
    assert main(["--audit"]) == 0
    assert "PASS  a_recursive_merge_keeps_every_leaf" in capsys.readouterr().out


def test_cli_writes_a_json_report(tmp_path):
    target = tmp_path / "nested" / "report.json"
    assert main(["--json", str(target)]) == 0
    body = json.loads(target.read_text(encoding="utf-8"))
    assert body["changes"] == 8


def test_cli_prints_the_plan_for_an_explicit_file(tmp_path):
    desired = tmp_path / "desired.json"
    desired.write_text(json.dumps(valid()), encoding="utf-8")
    (tmp_path / "override.json").write_text("{}", encoding="utf-8")
    (tmp_path / "observed.json").write_text(json.dumps(valid()), encoding="utf-8")
    assert main(["--file", str(desired)]) == 0


def test_cli_refuses_a_missing_file_with_exit_two(capsys, tmp_path):
    assert main(["--file", str(tmp_path / "absent.json")]) == 2
    assert "error: config not found" in capsys.readouterr().err


def test_cli_refuses_an_invalid_document_with_exit_two(tmp_path, capsys):
    bad = tmp_path / "desired.json"
    bad.write_text(json.dumps({"project": "X", "region": "east", "services": []}), encoding="utf-8")
    (tmp_path / "override.json").write_text("{}", encoding="utf-8")
    (tmp_path / "observed.json").write_text("{}", encoding="utf-8")
    assert main(["--file", str(bad)]) == 2
    assert "invalid config" in capsys.readouterr().err


def test_cli_accepts_explicit_override_and_observed(tmp_path):
    desired = tmp_path / "d.json"
    desired.write_text(json.dumps(valid()), encoding="utf-8")
    override = tmp_path / "o.json"
    override.write_text('{"budget": 100}', encoding="utf-8")
    observed = tmp_path / "s.json"
    observed.write_text(json.dumps(valid()), encoding="utf-8")
    assert (
        main(["--file", str(desired), "--override", str(override), "--observed", str(observed)])
        == 0
    )


def test_cli_quiet_without_demo_prints_nothing(capsys):
    assert main(["--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_the_three_bundled_seeds_are_ascii():
    for name in ("desired.json", "override.json", "observed.json"):
        raw = (DATA_DIR / name).read_bytes()
        assert all(byte < 128 for byte in raw), name
