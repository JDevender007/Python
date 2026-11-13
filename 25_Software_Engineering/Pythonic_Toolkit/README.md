<div align="center">

# 🐍 Pythonic_Toolkit

### Decorators, context managers, generators, and class idioms — a stdlib-only library of Python's best patterns, each with contracts proven by tests. Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Stdlib](https://img.shields.io/badge/Stdlib-Only-informational?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Pythonic_Toolkit collects the idioms that make Python code read like Python: four **decorators** (`@timed`, `@retry`, `@cached`, `@validate`) with inspectable contracts, three **context managers** (`timed_block`, `temp_directory`, `capture_stdout`) that guarantee cleanup, three **lazy generators** (`chunked`, `flatten`, `sliding_window`) that never materialise more than they must, and **class idioms** (frozen `slots` dataclasses, `__post_init__` validation, a manual `__slots__` class that raises `AttributeError` on stray attributes).

The demo validates five bundled records (`data/records.json`) against a runtime spec, runs one recipe per idiom family, and asserts its own output — deterministic every run, re-runnable, **no network, no API keys, stdlib only**.

---

# ✨ Features

- `@timed` — records `last_elapsed` on every call (including exceptions)
- `@retry(times, delay, exceptions)` — bounded retries with an `attempts` counter
- `@cached(maxsize)` — memoisation with `cache_info()` / `cache_clear()` and oldest-first eviction
- `@validate(**specs)` — signature-aware argument checks with type/min/max/choices rules
- `timed_block` / `temp_directory` / `capture_stdout` — guaranteed cleanup and measurement
- `chunked` / `flatten` / `sliding_window` — lazy generators with strict size validation
- Frozen + `slots` `Point`, `__post_init__`-validated `Reading`, manual `__slots__` `Tally`
- `RECORD_SPEC` runtime validation shared by `@validate` and the record loader
- CLI: `--demo`, `--file`, `--run RECIPE`, `--list`
- Bundled dataset: 5 records in `data/records.json`
- 54 passing pytest tests

---

# 📂 Folder Structure

```text
Pythonic_Toolkit/
│
├── src/
│   ├── main.py     # CLI: --demo, --file, --run, --list, --quiet
│   └── toolkit.py  # decorators, context managers, generators, idioms, demo
│
├── tests/
│   └── test_toolkit.py
│
├── data/
│   └── records.json # 5 records: name (str), age (0..150), score (0..100)
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 25_Software_Engineering/Pythonic_Toolkit

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: every idiom recipe with self-assertions
python src/main.py --demo

# Validate records against RECORD_SPEC
python src/main.py --file data/records.json

# Run one recipe
python src/main.py --run generators

# List the recipes
python src/main.py --list
```

Input schema (JSON array of objects):

```json
[
  {"name": "Ada", "age": 36, "score": 91.5}
]
```

(`name` non-empty string; `age` integer 0–150; `score` number 0–100. Unknown fields are ignored; missing spec fields fail validation.)

**Exit codes:** `0` = success · `2` = unknown recipe, missing/invalid file, spec violation · `2` (argparse) = no action or conflicting actions.

---

# 🧠 How It Works

```text
                       ┌── @timed      → wrapper.last_elapsed
call wrapped function ─┼── @retry      → attempts, bounded re-raises
                       ├── @cached     → store{key:value} + hits/misses
                       └── @validate   → signature.bind → check_value(spec)
                                                  │
data/records.json ──► load_records() ─────────────┤  same spec core
                                                  ▼
                                        ValidationError / ToolkitError
   with temp_directory()  → mkdtemp ──► yield ──► rmtree (always)
   with timed_block()     → t0 ──────► yield ──► stats.elapsed = t1 - t0
   with capture_stdout()  → StringIO ─ redirect_stdout ──► buffer

   chunked / flatten / sliding_window ──► yield lazily, validate sizes
                              │
                              ▼
        recipes assert every contract ──► "Cross-checks OK"
```

Details worth knowing:

- **`@validate` binds real signatures** (`inspect.signature().bind`) so defaults are validated too, and a misspelled spec name fails at *decoration* time, not at call time.
- **`check_value` fails fast and precisely**: type before range before choices — the first violated rule is the error you see.
- **The cache bypasses unhashable arguments** (lists as parameters) instead of crashing, and evicts oldest-first when `maxsize` is exceeded.
- **Context managers clean up on the error path too** — both temp-dir tests prove removal after an exception.

---

# 🛠 Technologies

- Python 3 (100 % standard library)
- `functools`, `inspect`, `contextlib`, `dataclasses`, `tempfile`, `time`
- `argparse` / `json` / `pathlib` / `logging`
- pytest

---

# 📚 Concepts Covered

- Decorator factories, `functools.wraps`, and attaching metadata to wrappers
- Bounded retry with exception-class filtering
- Memoisation: hits/misses bookkeeping and eviction policy
- Signature binding and validating defaults before a call runs
- Context-manager protocol (`__enter__`/`__exit__` via `@contextmanager`) and cleanup guarantees
- Generators: laziness, early `next()`, and size preconditions
- `frozen=True` + `slots=True` dataclasses and `__post_init__` validation
- Manual `__slots__` and the `AttributeError` contract
- Deterministic, self-asserting demos

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**54 tests passed** covering every validation rule (types, ranges, choices, bool-vs-int, unsupported specs, missing record fields), each decorator's contract (elapsed on success *and* failure, attempt counts, non-matching exceptions, eviction, cache clear, unhashable bypass, decoration-time errors), context-manager cleanup on both normal and error paths, generator laziness and arithmetic, frozen/slots/`__post_init__` contracts, bundled-record loading with indexed error messages, recipe name validation, demo idempotency, and every CLI path — all offline.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found these projects useful, consider giving this repository a star.

</div>
