<div align="center">

# 🧩 API Design Playground

### A library API built four ways: a fluent query builder, a repository with a typed error hierarchy, immutable records that validate themselves, and a v1/v2 wire format where v2 is a strict superset of v1.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Offline-No%20Server-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Most API bugs are design bugs wearing a runtime costume: a `KeyError` where a `404` belonged, a setter that silently accepts a value the constructor rejects, a "new" response shape that quietly drops a field an old client depends on. This project builds the small library those decisions live in — six seed tasks, one repository, four layers — and then tests the design, not just the code.

**A fluent builder that snapshots.** `TaskQueryBuilder` chains `where`, `order_by` and `limit`, validating **eagerly** on each call, and `build()` freezes the result into an immutable `Query`:

```python
query = (TaskQueryBuilder()
         .where("priority", "gte", 3)
         .where("done", "eq", False)
         .order_by("priority", descending=True)
         .limit(2)
         .build())
```

```text
filters=(('priority', 'gte', 3), ('done', 'eq', False))
order_by='priority'  descending=True  limit=2
-> T-2 (5), T-3 (4)
```

Because `build()` snapshots, a query you already evaluated cannot change under you when the builder is reused — a real aliasing bug in fluent APIs, pinned by a test.

**A repository that fails with meaning.** Every failure is a class in one hierarchy, each carrying a machine-readable code and an HTTP-ish status:

| Error | Code | Status | Raised by |
| --- | --- | --: | --- |
| `ValidationError` | `validation_error` | 400 | bad record, bad query, unknown update field |
| `NotFoundError` | `not_found` | 404 | `get` / `update` / `remove` on a missing id |
| `ConflictError` | `conflict` | 409 | `add` with a duplicate id |
| `VersionError` | `unsupported_version` | 406 | `respond(task, "v3")` |

`update()` re-validates through the immutable dataclass, so `repository.update("T-1", priority=99)` raises `ValidationError` **and leaves the stored task untouched** — the test asserts the old value is still there.

**Versioning that cannot break a client.** `respond(task, "v2")` returns the v1 payload plus three new keys, and the demo asserts the property that matters:

```text
v1: {id, title, priority, done}                         4 keys
v2: {id, title, priority, done, tags, status, schema}    7 keys
set(v1) < set(v2)                    strict superset
all(v2[k] == v1[k] for k in v1)      no value drifted
```

That pair of assertions is the whole contract of additive versioning, checked on real data instead of in a comment.

**Expressions for the CLI, parsed into the same builder.** `priority>=3` becomes a validated `Query` — with coercion for `priority` (integer) and `done` (`true/false/1/0`) and precise rejections (`bad value for priority: 'high'`, `operator 'contains' needs a text field`) — so the command line and the library share one code path.

**Everything in the demo is falsifiable.** It asserts the two fluent-query hits, the 409/404 payloads, the version superset property, that v1 keys are frozen at exactly four, that the repository is restored to six tasks after the add/remove cycle, that every error code is distinct, and that the seed loads identically twice. The `--quiet` path is also checked: it prints nothing at all.

No network, no web framework, no database, no API keys.

---

# ✨ Features

- Immutable, self-validating `Task` record (`frozen=True, slots=True`) with priority bounds, bool and tag checks
- Fluent `TaskQueryBuilder` with eager validation, `reset()`, and immutable `build()` snapshots
- Validated `Query` value object: fields, operators, text-only operators, order field, limit
- Seven filter operators: `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `contains` (substring or tuple membership)
- Pure `apply_query`: filter, stable sort, then truncate — never mutates its input
- In-memory repository with `add` / `get` / `list` / `count` / `update` / `remove` / `query`
- Typed error hierarchy with distinct codes, statuses and `to_dict()` payloads
- Additive v1/v2 versioning with a strict-superset guarantee and an explicit `schema` key
- `parse_expression` DSL (`==`, `!=`, `>=`, `<=`, `>`, `<`, `~`) with type coercion
- Bulk `respond_many` serializer
- Seed loader with indexed error messages (`record 0: priority must be 1..5`)
- Table output plus `--json`, `--version`, `--query` (repeatable), `--order-by`, `--desc`, `--limit`
- `--demo` and `--quiet` (prints nothing), exit `0` on success and `2` on any API error
- 145 passing pytest tests

---

# 📂 Folder Structure

```text
Api_Design_Playground/
│
├── src/
│   ├── main.py       # CLI: --query, --order-by, --desc, --limit, --version
│   └── api.py        # Task, Query, builder, repository, errors, respond, demo
│
├── tests/
│   └── test_api.py
│
├── data/
│   └── tasks.json    # 6 seed tasks
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 25_Software_Engineering/Api_Design_Playground

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: builder, CRUD errors, versioning, 12 self-checks
python src/main.py --demo

# List every seed task
python src/main.py

# One expression
python src/main.py --query "priority>=3"

# Two expressions, ANDed; only unfinished work
python src/main.py --query "priority>=3" --query "done==false"

# Text and tag matches
python src/main.py --query "title~API"
python src/main.py --query "tags~api" --order-by id

# The legacy wire shape, written to disk
python src/main.py --version v1 --json out.json

# Highest priority first, top 2 only
python src/main.py --order-by priority --desc --limit 2
```

**Seed format** (`data/tasks.json`):

```json
[
  { "id": "T-2", "title": "Ship auth middleware", "priority": 5,
    "done": false, "tags": ["security"] }
]
```

**Exit codes:** `0` = the query ran · `2` = bad expression, bad seed file or unknown version.

---

# 🧠 How It Works

```text
args --query / --order-by / --desc / --limit
        │
        ▼
build_query()  ──►  parse_expression("priority>=3")
        │                 │  coerce priority -> int, done -> bool
        │                 └─► TaskQueryBuilder.where(...)  (validates eagerly)
        ▼
   Query(filters, order_by, descending, limit)     immutable snapshot
        │
        ▼
apply_query(tasks, query)  ──►  filter (AND) -> stable sort -> [:limit]
        │
        ├── repository.query()  ──►  same function over stored tasks
        ▼
respond_many(tasks, version)  ──►  v1 keys, or v1 + {tags, status, schema}
        │
        └──► table  /  --json  {api_version, count, tasks}
```

Details worth knowing:

- **Validation happens in the value object, not the caller.** `Query.__post_init__` rejects unknown fields and operators, so a builder bug cannot produce an executable query.
- **`build()` copies the filter list.** Mutating the builder afterwards cannot change a query you already hold.
- **`update()` is atomic in the small sense**: `replace()` re-runs the record's validation before the repository stores anything, so a rejected update leaves the old value intact.
- **`contains` is substring for `title`/`id` and membership for `tags`**, which is why the operator is restricted to those three fields.
- **The v2 serializer is built from the v1 dict**, not written twice — drift becomes structurally impossible rather than a review responsibility.

---

# 🛠 Technologies

- Python 3 standard library: `json`, `dataclasses`, `typing`, `argparse`, `pathlib`, `logging`, `contextlib`
- pytest

No FastAPI, no Flask, no pydantic, no database, no network access.

---

# 📚 Concepts Covered

- Fluent interfaces and method chaining with `self` returns
- Immutable value objects and snapshot semantics
- Eager validation versus deferred validation
- Query objects as data (filter tuples) separated from evaluation
- Stable sorting and filter-then-sort-then-truncate ordering
- Repository pattern over an in-memory store
- Exception hierarchies with machine-readable codes and statuses
- Defensive `update` via dataclass `replace` re-validation
- Additive API versioning and the strict-superset contract
- DSL parsing with operator precedence, type coercion and precise errors
- Error messages that name the field, the value and the fix
- Self-asserting demos with a negative control for every happy path

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**145 tests passed** covering every `Task` validation rule, every `Query` validation rule (fields, operators, text-only `contains`, order field, limit), builder chaining, eager errors, snapshots and `reset`, all seven filter operators, AND composition, ordering, stability, truncation, non-mutation of inputs, every repository method and failure (duplicate id, missing id, unknown field, empty update, invalid update, no partial write), every error code/status/payload, the four versioning contracts, every expression operator and coercion, every malformed expression, every seed-loading failure with its indexed message, demo idempotency and `--quiet`, and every CLI path including exit code `2`.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
