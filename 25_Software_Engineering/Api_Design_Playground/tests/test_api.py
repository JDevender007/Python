"""Tests for the API Design Playground project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from api import (  # noqa: E402
    CURRENT_VERSION,
    FILTER_OPS,
    SEED_TASKS,
    SUPPORTED_VERSIONS,
    ApiError,
    ConflictError,
    InMemoryRepository,
    NotFoundError,
    Query,
    Task,
    TaskQueryBuilder,
    ValidationError,
    VersionError,
    apply_query,
    load_tasks,
    parse_expression,
    respond,
    respond_many,
    run_demo,
)
from main import build_parser, build_query, main  # noqa: E402


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def task(task_id="T-1", title="Write docs", priority=3, done=False,
         tags=()) -> Task:
    return Task(id=task_id, title=title, priority=priority, done=done,
                tags=tags)


def seeded() -> list[Task]:
    return load_tasks()


# --------------------------------------------------------------------------- #
# Task validation
# --------------------------------------------------------------------------- #
def test_task_accepts_valid_record():
    item = task(tags=("api",))
    assert item.id == "T-1" and item.tags == ("api",)


def test_task_is_immutable():
    item = task()
    with pytest.raises(Exception):
        item.title = "changed"       # type: ignore[misc]


def test_task_is_hashable():
    assert len({task(), task()}) == 1


@pytest.mark.parametrize("bad_id", ["", None, 7])
def test_task_rejects_bad_id(bad_id):
    with pytest.raises(ValidationError, match="id must be a non-empty string"):
        Task(id=bad_id, title="x", priority=1)


@pytest.mark.parametrize("bad_title", ["", "   ", None, 5])
def test_task_rejects_bad_title(bad_title):
    with pytest.raises(ValidationError,
                       match="title must be a non-empty string"):
        Task(id="T-1", title=bad_title, priority=1)


@pytest.mark.parametrize("bad_priority", ["3", 3.0, None, True])
def test_task_rejects_non_integer_priority(bad_priority):
    with pytest.raises(ValidationError, match="priority must be an integer"):
        Task(id="T-1", title="x", priority=bad_priority)


@pytest.mark.parametrize("bad_priority", [0, 6, -1, 99])
def test_task_rejects_priority_out_of_range(bad_priority):
    with pytest.raises(ValidationError, match="priority must be 1..5"):
        Task(id="T-1", title="x", priority=bad_priority)


def test_task_rejects_non_bool_done():
    with pytest.raises(ValidationError, match="done must be a bool"):
        Task(id="T-1", title="x", priority=1, done="yes")


@pytest.mark.parametrize("bad_tags", [["api"], ("api", ""), (1,)])
def test_task_rejects_bad_tags(bad_tags):
    with pytest.raises(ValidationError, match="tags must be a tuple"):
        Task(id="T-1", title="x", priority=1, tags=bad_tags)


def test_task_defaults():
    item = task()
    assert item.done is False and item.tags == ()


# --------------------------------------------------------------------------- #
# Query validation
# --------------------------------------------------------------------------- #
def test_query_accepts_valid_shape():
    query = Query(filters=(("priority", "gte", 2),), order_by="priority",
                  descending=True, limit=3)
    assert query.limit == 3


def test_query_rejects_unknown_field():
    with pytest.raises(ValidationError, match="unknown field 'colour'"):
        Query(filters=(("colour", "eq", "red"),))


def test_query_rejects_unknown_operator():
    with pytest.raises(ValidationError, match="unsupported operator 'like'"):
        Query(filters=(("title", "like", "x"),))


@pytest.mark.parametrize("field_name", ["priority", "done"])
def test_query_contains_needs_a_text_field(field_name):
    with pytest.raises(ValidationError, match="needs a text field"):
        Query(filters=((field_name, "contains", "x"),))


def test_query_allows_contains_on_tags():
    assert Query(filters=(("tags", "contains", "api"),)).filters


def test_query_rejects_unknown_order_by():
    with pytest.raises(ValidationError, match="cannot order by 'colour'"):
        Query(order_by="colour")


@pytest.mark.parametrize("limit", [0, -1, True, 2.5])
def test_query_rejects_bad_limit(limit):
    with pytest.raises(ValidationError, match="limit must be an int >= 1"):
        Query(limit=limit)


def test_filter_ops_are_the_documented_set():
    assert FILTER_OPS == ("eq", "ne", "gt", "gte", "lt", "lte", "contains")


# --------------------------------------------------------------------------- #
# Fluent builder
# --------------------------------------------------------------------------- #
def test_builder_chains_by_returning_self():
    builder = TaskQueryBuilder()
    assert builder.where("priority", "gte", 3) is builder
    assert builder.order_by("title") is builder
    assert builder.limit(2) is builder
    assert builder.reset() is builder


def test_builder_snapshots_into_a_query():
    builder = TaskQueryBuilder().where("done", "eq", False).limit(2)
    query = builder.build()
    assert query.filters == (("done", "eq", False),)
    assert query.limit == 2 and query.order_by is None


def test_builder_validates_eagerly():
    with pytest.raises(ValidationError, match="unknown field"):
        TaskQueryBuilder().where("colour", "eq", "red")


def test_builder_rejects_bad_order_by_eagerly():
    with pytest.raises(ValidationError, match="cannot order by"):
        TaskQueryBuilder().order_by("colour")


def test_builder_built_query_is_a_snapshot():
    builder = TaskQueryBuilder().where("done", "eq", False)
    query = builder.build()
    builder.where("priority", "gte", 3)
    assert len(query.filters) == 1


def test_builder_reset_clears_everything():
    builder = (TaskQueryBuilder().where("done", "eq", True)
               .order_by("title", descending=True).limit(5).reset())
    assert builder.build() == Query()


def test_builder_keeps_filter_order():
    query = (TaskQueryBuilder().where("priority", "gte", 3)
             .where("done", "eq", False).build())
    assert [name for name, _op, _value in query.filters] == \
        ["priority", "done"]


# --------------------------------------------------------------------------- #
# Query evaluation
# --------------------------------------------------------------------------- #
def test_apply_query_without_filters_returns_everything():
    items = [task("T-1"), task("T-2")]
    assert apply_query(items, Query()) == items


@pytest.mark.parametrize("op, value, hits", [
    ("eq", 3, ["T-1"]),
    ("ne", 3, ["T-2", "T-3"]),
    ("gt", 2, ["T-1", "T-3"]),
    ("gte", 3, ["T-1", "T-3"]),
    ("lt", 3, ["T-2"]),
    ("lte", 2, ["T-2"]),
])
def test_apply_query_operators(op, value, hits):
    items = [task("T-1", priority=3), task("T-2", priority=1),
             task("T-3", priority=4)]
    query = Query(filters=(("priority", op, value),))
    assert [item.id for item in apply_query(items, query)] == hits


def test_apply_query_contains_is_a_substring_test():
    items = [task("T-1", title="Draft API contract"),
             task("T-2", title="Ship auth middleware")]
    query = Query(filters=(("title", "contains", "API"),))
    assert [item.id for item in apply_query(items, query)] == ["T-1"]


def test_apply_query_contains_matches_a_tag():
    items = [task("T-1", tags=("api",)), task("T-2", tags=("ops",))]
    query = Query(filters=(("tags", "contains", "api"),))
    assert [item.id for item in apply_query(items, query)] == ["T-1"]


def test_apply_query_filters_are_anded():
    items = [task("T-1", priority=5, done=False),
             task("T-2", priority=5, done=True),
             task("T-3", priority=1, done=False)]
    query = (TaskQueryBuilder().where("priority", "gte", 2)
             .where("done", "eq", False).build())
    assert [item.id for item in apply_query(items, query)] == ["T-1"]


def test_apply_query_orders_ascending():
    items = [task("T-1", priority=3), task("T-2", priority=1),
             task("T-3", priority=5)]
    query = Query(order_by="priority")
    assert [item.id for item in apply_query(items, query)] == \
        ["T-2", "T-1", "T-3"]


def test_apply_query_orders_descending():
    items = [task("T-1", priority=3), task("T-2", priority=1),
             task("T-3", priority=5)]
    query = Query(order_by="priority", descending=True)
    assert [item.id for item in apply_query(items, query)] == \
        ["T-3", "T-1", "T-2"]


def test_apply_query_sort_is_stable_for_ties():
    items = [task("T-1", priority=3), task("T-2", priority=3)]
    query = Query(order_by="priority")
    assert [item.id for item in apply_query(items, query)] == ["T-1", "T-2"]


def test_apply_query_truncates_after_ordering():
    items = [task("T-1", priority=1), task("T-2", priority=5)]
    query = Query(order_by="priority", descending=True, limit=1)
    assert [item.id for item in apply_query(items, query)] == ["T-2"]


def test_apply_query_does_not_mutate_the_input():
    items = [task("T-2", priority=1), task("T-1", priority=5)]
    before = list(items)
    apply_query(items, Query(order_by="priority", descending=True))
    assert items == before


# --------------------------------------------------------------------------- #
# Repository
# --------------------------------------------------------------------------- #
def test_repository_add_and_count():
    repo = InMemoryRepository([task("T-1")])
    assert repo.count() == 1
    repo.add(task("T-2"))
    assert repo.count() == 2


def test_repository_add_returns_the_task():
    repo = InMemoryRepository()
    item = task()
    assert repo.add(item) is item


def test_repository_rejects_a_duplicate_id():
    repo = InMemoryRepository([task("T-1")])
    with pytest.raises(ConflictError, match="already exists"):
        repo.add(task("T-1"))


def test_repository_get_and_remove():
    repo = InMemoryRepository([task("T-1")])
    assert repo.get("T-1").id == "T-1"
    assert repo.remove("T-1").id == "T-1"
    assert repo.count() == 0


def test_repository_get_missing_raises_not_found():
    with pytest.raises(NotFoundError, match="'T-9' not found"):
        InMemoryRepository().get("T-9")


def test_repository_remove_missing_raises_not_found():
    with pytest.raises(NotFoundError):
        InMemoryRepository().remove("T-9")


def test_repository_add_requires_a_task():
    with pytest.raises(ValidationError, match="expects a Task"):
        InMemoryRepository().add({"id": "T-1"})


def test_repository_update_returns_the_new_value():
    repo = InMemoryRepository([task("T-1", priority=1)])
    updated = repo.update("T-1", priority=5, done=True)
    assert updated.priority == 5 and updated.done is True
    assert repo.get("T-1") == updated


def test_repository_update_checks_existence_first():
    with pytest.raises(NotFoundError):
        InMemoryRepository().update("T-9", priority=2)


def test_repository_update_rejects_unknown_fields():
    repo = InMemoryRepository([task("T-1")])
    with pytest.raises(ValidationError, match="cannot update field"):
        repo.update("T-1", colour="red")


def test_repository_update_requires_a_change():
    repo = InMemoryRepository([task("T-1")])
    with pytest.raises(ValidationError, match="at least one change"):
        repo.update("T-1")


def test_repository_update_revalidates_values():
    repo = InMemoryRepository([task("T-1")])
    with pytest.raises(ValidationError, match="priority must be 1..5"):
        repo.update("T-1", priority=9)


def test_repository_update_keeps_the_old_value_on_failure():
    repo = InMemoryRepository([task("T-1", priority=2)])
    with pytest.raises(ValidationError):
        repo.update("T-1", priority=99)
    assert repo.get("T-1").priority == 2


def test_repository_query_accepts_a_builder():
    repo = InMemoryRepository(seeded())
    hits = repo.query(TaskQueryBuilder().where("priority", "gte", 3))
    assert [item.id for item in hits] == ["T-1", "T-2", "T-3", "T-5"]


def test_repository_query_accepts_a_query():
    repo = InMemoryRepository(seeded())
    hits = repo.query(Query(filters=(("done", "eq", True),)))
    assert [item.id for item in hits] == ["T-5"]


def test_repository_query_rejects_other_types():
    with pytest.raises(ValidationError, match="expects a Query"):
        InMemoryRepository().query("priority>=3")


def test_repository_list_is_a_copy():
    repo = InMemoryRepository([task("T-1")])
    repo.list().clear()
    assert repo.count() == 1


# --------------------------------------------------------------------------- #
# Error hierarchy
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("cls, code, status", [
    (ApiError, "api_error", 500),
    (ValidationError, "validation_error", 400),
    (NotFoundError, "not_found", 404),
    (ConflictError, "conflict", 409),
    (VersionError, "unsupported_version", 406),
])
def test_error_codes_and_statuses(cls, code, status):
    error = cls("boom")
    assert error.code == code and error.status == status
    assert error.to_dict() == {"error": code, "status": status,
                               "message": "boom"}


def test_errors_subclass_the_base():
    for cls in (ValidationError, NotFoundError, ConflictError, VersionError):
        assert issubclass(cls, ApiError)


def test_error_codes_are_distinct():
    classes = (ApiError, ValidationError, NotFoundError, ConflictError,
               VersionError)
    assert len({cls.code for cls in classes}) == len(classes)


def test_errors_are_catchable_as_api_errors():
    with pytest.raises(ApiError):
        raise ConflictError("clash")


# --------------------------------------------------------------------------- #
# Versioning
# --------------------------------------------------------------------------- #
def test_v1_payload_is_the_frozen_shape():
    assert set(respond(task(), "v1")) == {"id", "title", "priority", "done"}


def test_v2_is_a_strict_superset_of_v1():
    sample = task(tags=("api",), done=True)
    v1, v2 = respond(sample, "v1"), respond(sample, "v2")
    assert set(v1) < set(v2)
    assert all(v2[key] == value for key, value in v1.items())
    assert v2["tags"] == ["api"] and v2["status"] == "done"
    assert v2["schema"] == CURRENT_VERSION


def test_v2_status_is_open_for_unfinished_tasks():
    assert respond(task(done=False), "v2")["status"] == "open"


def test_respond_rejects_an_unknown_version():
    with pytest.raises(VersionError, match="unsupported api version 'v3'"):
        respond(task(), "v3")


def test_respond_names_the_supported_versions():
    with pytest.raises(VersionError, match="v1, v2"):
        respond(task(), "v9")


def test_respond_defaults_to_the_current_version():
    assert respond(task())["schema"] == CURRENT_VERSION
    assert SUPPORTED_VERSIONS == ("v1", "v2")


def test_respond_many_preserves_order():
    items = [task("T-1"), task("T-2")]
    assert [item["id"] for item in respond_many(items)] == ["T-1", "T-2"]


def test_respond_many_honours_the_version():
    assert all("schema" not in item
               for item in respond_many([task()], "v1"))


# --------------------------------------------------------------------------- #
# Expression parsing
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("text, expected", [
    ("priority>=3", ("priority", "gte", 3)),
    ("priority<=2", ("priority", "lte", 2)),
    ("priority>1", ("priority", "gt", 1)),
    ("priority<5", ("priority", "lt", 5)),
    ("priority==4", ("priority", "eq", 4)),
    ("priority!=4", ("priority", "ne", 4)),
    ("title~API", ("title", "contains", "API")),
])
def test_parse_expression_operators(text, expected):
    query = parse_expression(text)
    assert query.filters == (expected,)


def test_parse_expression_tolerates_spaces():
    assert parse_expression("  priority >= 3  ").filters == \
        (("priority", "gte", 3),)


@pytest.mark.parametrize("text, value", [
    ("done==true", True),
    ("done==1", True),
    ("done==false", False),
    ("done==0", False),
])
def test_parse_expression_coerces_bools(text, value):
    assert parse_expression(text).filters[0][2] is value


def test_parse_expression_keeps_text_values():
    assert parse_expression("title==Write docs").filters == \
        (("title", "eq", "Write docs"),)


@pytest.mark.parametrize("text", ["priority", "priority>= ", ">=3", ""])
def test_parse_expression_requires_a_full_expression(text):
    with pytest.raises(ValidationError, match="must look like"):
        parse_expression(text)


def test_parse_expression_rejects_unknown_field():
    with pytest.raises(ValidationError, match="unknown field 'colour'"):
        parse_expression("colour==red")


def test_parse_expression_rejects_bad_priority():
    with pytest.raises(ValidationError, match="bad value for priority"):
        parse_expression("priority>=high")


def test_parse_expression_rejects_bad_bool():
    with pytest.raises(ValidationError, match="bad value for done"):
        parse_expression("done==maybe")


def test_parse_expression_rejects_contains_on_priority():
    with pytest.raises(ValidationError, match="needs a text field"):
        parse_expression("priority~3")


def test_parsed_expression_filters_the_seed():
    hits = apply_query(seeded(), parse_expression("priority>=3"))
    assert [item.id for item in hits] == ["T-1", "T-2", "T-3", "T-5"]


# --------------------------------------------------------------------------- #
# Seed loading
# --------------------------------------------------------------------------- #
def test_load_bundled_seed():
    items = load_tasks()
    assert [item.id for item in items] == \
        ["T-1", "T-2", "T-3", "T-4", "T-5", "T-6"]
    assert SEED_TASKS.is_file()


def test_load_seed_is_deterministic():
    assert load_tasks() == load_tasks()


def test_load_seed_missing_file(tmp_path):
    with pytest.raises(ValidationError, match="file not found"):
        load_tasks(tmp_path / "absent.json")


def test_load_seed_invalid_json(tmp_path):
    broken = tmp_path / "tasks.json"
    broken.write_text("{nope", encoding="utf-8")
    with pytest.raises(ValidationError, match="could not parse tasks.json"):
        load_tasks(broken)


def test_load_seed_requires_an_array(tmp_path):
    bad = tmp_path / "tasks.json"
    bad.write_text('{"id": "T-1"}', encoding="utf-8")
    with pytest.raises(ValidationError, match="JSON array"):
        load_tasks(bad)


def test_load_seed_requires_records(tmp_path):
    empty = tmp_path / "tasks.json"
    empty.write_text("[]", encoding="utf-8")
    with pytest.raises(ValidationError, match="no records"):
        load_tasks(empty)


def test_load_seed_requires_objects(tmp_path):
    bad = tmp_path / "tasks.json"
    bad.write_text('["T-1"]', encoding="utf-8")
    with pytest.raises(ValidationError, match="record 0 must be a JSON"):
        load_tasks(bad)


def test_load_seed_names_missing_fields(tmp_path):
    bad = tmp_path / "tasks.json"
    bad.write_text('[{"id": "T-1", "title": "x", "priority": 2}]',
                   encoding="utf-8")
    with pytest.raises(ValidationError, match="missing field\\(s\\): done"):
        load_tasks(bad)


def test_load_seed_indexes_validation_errors(tmp_path):
    bad = tmp_path / "tasks.json"
    bad.write_text('[{"id": "T-1", "title": "x", "priority": 9, '
                   '"done": false}]', encoding="utf-8")
    with pytest.raises(ValidationError, match="record 0: priority"):
        load_tasks(bad)


def test_load_seed_defaults_missing_tags(tmp_path):
    good = tmp_path / "tasks.json"
    good.write_text('[{"id": "T-1", "title": "x", "priority": 2, '
                    '"done": false}]', encoding="utf-8")
    assert load_tasks(good)[0].tags == ()


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_demo_returns_zero(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "API DESIGN PLAYGROUND" in out
    assert "Cross-checks OK:" in out
    assert out.endswith("Demo completed successfully.\n")


def test_demo_is_deterministic(capsys):
    run_demo()
    first = capsys.readouterr().out
    run_demo()
    assert capsys.readouterr().out == first


def test_demo_reports_the_flow(tmp_path, monkeypatch, capsys):
    import api
    monkeypatch.setattr(api, "SEED_TASKS", tmp_path / "absent.json")
    with pytest.raises(ValidationError):
        run_demo()
    assert "API DESIGN PLAYGROUND" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# CLI helpers
# --------------------------------------------------------------------------- #
def test_parser_exposes_documented_flags():
    dests = {action.dest for action in build_parser()._actions}
    assert {"demo", "file", "query", "order_by", "desc", "limit", "version",
            "json", "quiet"} <= dests


def test_cli_build_query_ands_expressions():
    query = build_query(["priority>=3", "done==false"], None, False, None)
    assert len(query.filters) == 2


def test_cli_build_query_applies_order_and_limit():
    query = build_query(None, "priority", True, 2)
    assert query.order_by == "priority" and query.descending is True
    assert query.limit == 2


def test_cli_build_query_rejects_desc_without_order():
    with pytest.raises(ValidationError, match="--desc requires --order-by"):
        build_query(None, None, True, None)


def test_cli_build_query_is_empty_by_default():
    assert build_query(None, None, False, None) == Query()


# --------------------------------------------------------------------------- #
# CLI behaviour
# --------------------------------------------------------------------------- #
def test_cli_demo_exit_zero(capsys):
    assert main(["--demo"]) == 0
    assert "Cross-checks OK:" in capsys.readouterr().out


def test_cli_demo_quiet_prints_nothing(capsys):
    assert main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_lists_every_seed_task(capsys):
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "6 of 6 tasks" in out
    assert "Ship auth middleware" in out


def test_cli_filters_with_one_expression(capsys):
    assert main(["--query", "priority>=3"]) == 0
    out = capsys.readouterr().out
    assert "4 of 6 tasks" in out and "T-5" in out


def test_cli_filters_with_two_expressions(capsys):
    assert main(["--query", "priority>=3", "--query", "done==false"]) == 0
    assert "3 of 6 tasks" in capsys.readouterr().out


def test_cli_orders_descending_and_limits(capsys):
    assert main(["--order-by", "priority", "--desc", "--limit", "2"]) == 0
    out = capsys.readouterr().out
    assert "2 of 6 tasks" in out
    assert out.index("T-2") < out.index("T-3")


def test_cli_version_flag_changes_the_payload(tmp_path, capsys):
    target = tmp_path / "v1.json"
    assert main(["--version", "v1", "--json", str(target)]) == 0
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["api_version"] == "v1"
    assert "schema" not in payload["tasks"][0]
    assert capsys.readouterr().out != ""


def test_cli_json_defaults_to_v2(tmp_path):
    target = tmp_path / "out" / "v2.json"
    assert main(["--json", str(target)]) == 0
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["count"] == 6
    assert payload["tasks"][0]["schema"] == "v2"


def test_cli_quiet_suppresses_output_but_writes_json(tmp_path, capsys):
    target = tmp_path / "quiet.json"
    assert main(["--json", str(target), "--quiet"]) == 0
    assert capsys.readouterr().out == ""
    assert json.loads(target.read_text(encoding="utf-8"))["count"] == 6


def test_cli_bad_expression_exits_two(capsys):
    assert main(["--query", "priority>="]) == 2
    assert "must look like" in capsys.readouterr().err


def test_cli_unknown_field_exits_two(capsys):
    assert main(["--query", "colour==red"]) == 2
    assert "unknown field" in capsys.readouterr().err


def test_cli_desc_without_order_exits_two(capsys):
    assert main(["--desc"]) == 2
    assert "--desc requires --order-by" in capsys.readouterr().err


def test_cli_zero_limit_exits_two(capsys):
    assert main(["--limit", "0"]) == 2
    assert "limit must be an int >= 1" in capsys.readouterr().err


def test_cli_missing_file_exits_two(tmp_path, capsys):
    assert main(["--file", str(tmp_path / "absent.json")]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_unknown_version_is_a_usage_error(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--version", "v3"])
    assert excinfo.value.code == 2
