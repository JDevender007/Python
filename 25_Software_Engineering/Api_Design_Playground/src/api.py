"""Library API design patterns: fluent builder, repository, errors, versions.

Fluent builder  - TaskQueryBuilder: method-chaining into an immutable Query
Repository      - InMemoryRepository: add/get/update/remove/list/query with
                  a proper error hierarchy instead of KeyError/IndexError
Error hierarchy - ApiError -> ValidationError / NotFoundError / ConflictError
                  / VersionError, each with a machine-readable code + status
Versioning      - respond(task, "v1"|"v2"): v2 is a strict superset of v1,
                  so existing v1 consumers keep working unchanged

Seed tasks ship in data/tasks.json. Fully offline - no network, no downloads.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SEED_TASKS = PROJECT_ROOT / "data" / "tasks.json"

TASK_FIELDS = ("id", "title", "priority", "done", "tags")
FILTER_OPS = ("eq", "ne", "gt", "gte", "lt", "lte", "contains")
PRIORITIES = range(1, 6)

CURRENT_VERSION = "v2"
SUPPORTED_VERSIONS = ("v1", "v2")


# --------------------------------------------------------------------------- #
# Error hierarchy
# --------------------------------------------------------------------------- #
class ApiError(Exception):
    """Base of the hierarchy: every failure has a code and an HTTP-ish status."""

    code = "api_error"
    status = 500

    def to_dict(self) -> dict[str, Any]:
        return {"error": self.code, "status": self.status,
                "message": str(self)}


class ValidationError(ApiError):
    code = "validation_error"
    status = 400


class NotFoundError(ApiError):
    code = "not_found"
    status = 404


class ConflictError(ApiError):
    code = "conflict"
    status = 409


class VersionError(ApiError):
    code = "unsupported_version"
    status = 406


# --------------------------------------------------------------------------- #
# Domain record
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Task:
    """Immutable task with validation; the repository's unit of storage."""

    id: str
    title: str
    priority: int
    done: bool = False
    tags: tuple[str, ...] = field(default=())

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise ValidationError("id must be a non-empty string")
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValidationError("title must be a non-empty string")
        if isinstance(self.priority, bool) or not isinstance(
                self.priority, int):
            raise ValidationError("priority must be an integer")
        if self.priority not in PRIORITIES:
            raise ValidationError(
                f"priority must be 1..5 (got {self.priority})")
        if not isinstance(self.done, bool):
            raise ValidationError("done must be a bool")
        if not isinstance(self.tags, tuple) or \
                not all(isinstance(t, str) and t for t in self.tags):
            raise ValidationError("tags must be a tuple of non-empty strings")


# --------------------------------------------------------------------------- #
# Fluent builder -> immutable query
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Query:
    """Immutable value object produced by the builder."""

    filters: tuple[tuple[str, str, Any], ...] = ()
    order_by: str | None = None
    descending: bool = False
    limit: int | None = None

    def __post_init__(self) -> None:
        for field_name, op, _value in self.filters:
            if field_name not in TASK_FIELDS:
                raise ValidationError(
                    f"unknown field {field_name!r} "
                    f"(expected one of {', '.join(TASK_FIELDS)})")
            if op not in FILTER_OPS:
                raise ValidationError(
                    f"unsupported operator {op!r} "
                    f"(expected one of {', '.join(FILTER_OPS)})")
            if op == "contains" and field_name not in ("id", "title", "tags"):
                raise ValidationError(
                    f"operator 'contains' needs a text field, "
                    f"not {field_name!r}")
        if self.order_by is not None and self.order_by not in TASK_FIELDS:
            raise ValidationError(f"cannot order by {self.order_by!r}")
        if self.limit is not None and (
                isinstance(self.limit, bool)
                or not isinstance(self.limit, int) or self.limit < 1):
            raise ValidationError("limit must be an int >= 1")


class TaskQueryBuilder:
    """Fluent, self-returning builder; build() snapshots into a Query."""

    def __init__(self) -> None:
        self._filters: list[tuple[str, str, Any]] = []
        self._order_by: str | None = None
        self._descending = False
        self._limit: int | None = None

    def where(self, field_name: str, op: str, value: Any) -> TaskQueryBuilder:
        Query(filters=((field_name, op, value),))   # validate eagerly
        self._filters.append((field_name, op, value))
        return self

    def order_by(self, field_name: str,
                 descending: bool = False) -> TaskQueryBuilder:
        Query(order_by=field_name, descending=descending)
        self._order_by = field_name
        self._descending = descending
        return self

    def limit(self, count: int) -> TaskQueryBuilder:
        Query(limit=count)
        self._limit = count
        return self

    def reset(self) -> TaskQueryBuilder:
        self._filters.clear()
        self._order_by = None
        self._descending = False
        self._limit = None
        return self

    def build(self) -> Query:
        return Query(filters=tuple(self._filters), order_by=self._order_by,
                     descending=self._descending, limit=self._limit)


def apply_query(tasks: Sequence[Task], query: Query) -> list[Task]:
    """Pure evaluation: filter, order (stable), then truncate."""
    matched = [task for task in tasks
               if all(_matches(task, name, op, value)
                      for name, op, value in query.filters)]
    if query.order_by is not None:
        matched.sort(key=lambda task: getattr(task, query.order_by),
                     reverse=query.descending)
    if query.limit is not None:
        matched = matched[: query.limit]
    return matched


def _matches(task: Task, name: str, op: str, value: Any) -> bool:
    current = getattr(task, name)
    if op == "eq":
        return current == value
    if op == "ne":
        return current != value
    if op == "gt":
        return current > value
    if op == "gte":
        return current >= value
    if op == "lt":
        return current < value
    if op == "lte":
        return current <= value
    return value in current      # contains: substring or tuple membership


# --------------------------------------------------------------------------- #
# Repository over an in-memory store
# --------------------------------------------------------------------------- #
class InMemoryRepository:
    """CRUD + queries with hierarchy-correct exceptions."""

    def __init__(self, tasks: Iterable[Task] = ()) -> None:
        self._tasks: dict[str, Task] = {}
        for task in tasks:
            self.add(task)

    def add(self, task: Task) -> Task:
        if not isinstance(task, Task):
            raise ValidationError("add() expects a Task")
        if task.id in self._tasks:
            raise ConflictError(f"task {task.id!r} already exists")
        self._tasks[task.id] = task
        return task

    def get(self, task_id: str) -> Task:
        try:
            return self._tasks[task_id]
        except KeyError:
            raise NotFoundError(f"task {task_id!r} not found") from None

    def list(self) -> list[Task]:
        return list(self._tasks.values())

    def count(self) -> int:
        return len(self._tasks)

    def update(self, task_id: str, **changes: Any) -> Task:
        current = self.get(task_id)            # NotFound first
        unknown = [name for name in changes if name not in TASK_FIELDS]
        if unknown:
            raise ValidationError(
                f"cannot update field(s): {', '.join(unknown)}")
        if not changes:
            raise ValidationError("update() needs at least one change")
        try:
            updated = replace(current, **changes)   # frozen dataclass +
        except TypeError as exc:                    # re-validates everything
            raise ValidationError(str(exc)) from exc
        self._tasks[task_id] = updated
        return updated

    def remove(self, task_id: str) -> Task:
        removed = self.get(task_id)
        del self._tasks[task_id]
        return removed

    def query(self, query: Query | TaskQueryBuilder) -> list[Task]:
        if isinstance(query, TaskQueryBuilder):
            query = query.build()
        if not isinstance(query, Query):
            raise ValidationError("query() expects a Query or a builder")
        return apply_query(self.list(), query)


# --------------------------------------------------------------------------- #
# Backward-compatible versioning
# --------------------------------------------------------------------------- #
def _payload_v1(task: Task) -> dict[str, Any]:
    """The original wire shape - frozen forever for existing consumers."""
    return {"id": task.id, "title": task.title, "priority": task.priority,
            "done": task.done}


def respond(task: Task, version: str = CURRENT_VERSION) -> dict[str, Any]:
    """Serialize a task for the requested API version.

    v2 is a strict superset of v1: every v1 key exists in v2 with the same
    value, so upgrading the server never breaks a v1 client.
    """
    if version not in SUPPORTED_VERSIONS:
        raise VersionError(
            f"unsupported api version {version!r} "
            f"(supported: {', '.join(SUPPORTED_VERSIONS)})")
    base = _payload_v1(task)
    if version == "v1":
        return base
    return {**base,
            "tags": list(task.tags),
            "status": "done" if task.done else "open",
            "schema": CURRENT_VERSION}


def respond_many(tasks: Iterable[Task],
                 version: str = CURRENT_VERSION) -> list[dict[str, Any]]:
    return [respond(task, version) for task in tasks]


# --------------------------------------------------------------------------- #
# Seed loading
# --------------------------------------------------------------------------- #
def load_tasks(path: str | Path | None = None) -> list[Task]:
    """Load and validate the seed tasks JSON (indexed error messages)."""
    source = Path(path) if path is not None else SEED_TASKS
    if not source.is_file():
        raise ValidationError(f"file not found: {source}")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(
            f"could not parse {source.name}: {exc}") from exc
    if not isinstance(payload, list):
        raise ValidationError("tasks file must contain a JSON array")
    if not payload:
        raise ValidationError("tasks file contains no records")
    tasks: list[Task] = []
    for index, record in enumerate(payload):
        if not isinstance(record, dict):
            raise ValidationError(f"record {index} must be a JSON object")
        missing = [name for name in TASK_FIELDS[:4]
                   if name not in record]
        if missing:
            raise ValidationError(
                f"record {index} missing field(s): {', '.join(missing)}")
        try:
            tasks.append(Task(
                id=record["id"],
                title=record["title"],
                priority=record["priority"],
                done=record["done"],
                tags=tuple(record.get("tags", ())),
            ))
        except ValidationError as exc:
            raise ValidationError(f"record {index}: {exc}") from exc
    return tasks


# --------------------------------------------------------------------------- #
# Query expression parsing (CLI --query)
# --------------------------------------------------------------------------- #
def parse_expression(text: str) -> Query:
    """Parse 'priority>=3' style expressions into a validated Query.

    Operators: == != >= <= > < ~ (contains). Values coerce to the field's
    type; anything unexpected fails fast with a specific message.
    """
    expression = str(text).strip()
    operator = None
    for symbol in ("==", "!=", ">=", "<=", ">", "<", "~"):
        if symbol in expression:
            operator = symbol
            break
    if operator is None:
        raise ValidationError(
            "query must look like 'priority>=3' "
            "(operators: == != >= <= > < ~)")
    name, _, raw_value = expression.partition(operator)
    name = name.strip()
    raw_value = raw_value.strip()
    if not name or not raw_value:
        raise ValidationError(
            "query must look like 'priority>=3' "
            "(operators: == != >= <= > < ~)")
    if name not in TASK_FIELDS:
        raise ValidationError(
            f"unknown field {name!r} "
            f"(expected one of {', '.join(TASK_FIELDS)})")
    op = {"==": "eq", "!=": "ne", ">=": "gte", "<=": "lte",
          ">": "gt", "<": "lt", "~": "contains"}[operator]
    value = _coerce(name, raw_value)
    return TaskQueryBuilder().where(name, op, value).build()


def _coerce(name: str, raw: str) -> Any:
    if name == "priority":
        try:
            return int(raw)
        except ValueError as exc:
            raise ValidationError(
                f"bad value for priority: {raw!r} (need an integer)"
            ) from exc
    if name == "done":
        lowered = raw.lower()
        if lowered in ("true", "1"):
            return True
        if lowered in ("false", "0"):
            return False
        raise ValidationError(
            f"bad value for done: {raw!r} (need true/false)")
    return raw


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def run_demo() -> int:
    """Exercise every public entry point with self-assertions."""
    print("=" * 68)
    print(" API DESIGN PLAYGROUND")
    print(" Fluent builder, repository, error hierarchy, versioning.")
    print(" Bundled seed tasks; fully offline.")
    print("=" * 68)

    tasks = load_tasks()
    repository = InMemoryRepository(tasks)
    print(f"\nSeeded {repository.count()} tasks from {SEED_TASKS.name}")

    # 1. Fluent builder -> query
    builder = (TaskQueryBuilder()
               .where("priority", "gte", 3)
               .where("done", "eq", False)
               .order_by("priority", descending=True)
               .limit(2))
    assert builder.where("id", "eq", "T-1") is builder, "must chain fluently"
    builder.reset()
    (builder.where("priority", "gte", 3)
            .where("done", "eq", False)
            .order_by("priority", descending=True)
            .limit(2))
    query = builder.build()
    hits = repository.query(query)
    print(f"  Builder      -> {query}")
    print(f"  Query hits   -> {[t.id for t in hits]}")
    # 2. Repository CRUD with hierarchy-correct errors
    created = repository.add(Task(id="T-7", title="Ship release",
                                  priority=4, done=False, tags=("ops",)))
    try:
        repository.add(created)
    except ConflictError as exc:
        conflict = exc.to_dict()
    else:
        conflict = {}
    try:
        repository.get("T-99")
    except NotFoundError as exc:
        missing = exc.to_dict()
    else:
        missing = {}
    repository.update("T-4", priority=5, done=True)
    reprioritised = repository.get("T-4")
    removed = repository.remove("T-7")
    print(f"  CRUD         -> added {created.id}, conflict "
          f"{conflict.get('error')}, missing {missing.get('error')}, "
          f"updated {reprioritised.id} -> p{reprioritised.priority}, "
          f"removed {removed.id}")

    # 3. Versioning: v2 is a strict superset of v1
    sample = tasks[0]
    v1 = respond(sample, "v1")
    v2 = respond(sample, "v2")
    print(f"  respond v1   -> {v1}")
    print(f"  respond v2   -> {v2}")
    try:
        respond(sample, "v3")
    except VersionError as exc:
        version_error = exc.to_dict()
    else:
        version_error = {}

    # 4. Expression parsing
    parsed = parse_expression("priority>=3")
    parsed_hits = apply_query(tasks, parsed)
    print(f"  Expression   -> 'priority>=3' matched "
          f"{[t.id for t in parsed_hits]}")

    # --- cross-checks the demo asserts ----------------------------------- #
    assert [t.id for t in hits] == ["T-2", "T-3"], "fluent query wrong"
    assert apply_query(tasks, parse_expression("priority>=3")) == parsed_hits
    assert [t.id for t in parsed_hits] == ["T-1", "T-2", "T-3", "T-5"]

    assert conflict["error"] == "conflict" and conflict["status"] == 409
    assert missing["error"] == "not_found" and missing["status"] == 404
    assert version_error["error"] == "unsupported_version"
    assert repository.count() == 6, "seed count must be restored"
    assert repository.get("T-4").priority == 5

    assert set(v1) == {"id", "title", "priority", "done"}
    assert all(v2[key] == value for key, value in v1.items()), \
        "v1 fields must survive unchanged inside v2"
    assert set(v1) < set(v2), "v2 must be a strict superset"
    assert v2["schema"] == "v2" and isinstance(v2["tags"], list)

    codes = {ApiError: ApiError.code, ValidationError: ValidationError.code,
             NotFoundError: NotFoundError.code,
             ConflictError: ConflictError.code,
             VersionError: VersionError.code}
    assert len(set(codes.values())) == len(codes), "codes must be distinct"
    assert issubclass(NotFoundError, ApiError)
    assert ValidationError("x").to_dict()["error"] == "validation_error"

    # seed loader is deterministic and isolated from repository mutations
    assert load_tasks() == tasks
    assert all(t.id in {"T-1", "T-2", "T-3", "T-4", "T-5", "T-6"}
               for t in tasks)

    print(f"\nCross-checks OK: {len(hits)} fluent-query hits, CRUD errors "
          f"409/404, v2 strict superset of v1 ({len(v2)} keys), "
          f"{len(parsed_hits)} expression matches, deterministic seed")
    print("Demo completed successfully.")
    return 0
