<div align="center">

# 🏷️ Type Hints Refactoring

### An untyped legacy module refactored into a fully-annotated, Protocol-based, runtime-validated module — with mypy-style interface contracts enforced manually, no mypy needed. Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Type Hints](https://img.shields.io/badge/Type_Hints-100%25-brightgreen?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Type_Hints_Refactoring ships **two versions of the same module**: `legacy.py` — the *before* picture, no annotations, raw `KeyError`/`ValueError`/`ZeroDivisionError`, and silent acceptance of negative units — and `typed.py` — the *after* picture, every signature annotated, data validated at the boundary with indexed messages, structural interfaces expressed as `typing.Protocol`, and a **manual contract checker** that re-implements the parts of mypy that matter (method presence, parameter shape, annotation completeness) using `inspect`, so no external tool is required.

The demo runs both modules on the bundled `data/records.csv` and proves they **agree to the cent** on valid data, then shows the typed module *rejecting* the malformed rows the legacy module silently absorbs. **No network, no API keys, stdlib only.**

---

# ✨ Features

- `legacy.py` — deliberately untyped baseline with raw exceptions and a silent data bug
- `typed.py` — fully annotated `SaleRecord`, `Summary`, `SaleRepository`, loaders, aggregates
- `@runtime_checkable SupportsRevenue` Protocol + `Refund` duck-type adapter + negative case
- `TypedDict` wire shape (`SalePayload`) and frozen `slots` dataclass records
- Boundary validation: header/row/index-aware `RecordError` messages, first violation wins
- `check_contract` / `verify_contracts` — manual, `inspect`-based interface contracts driven by `data/interfaces.json`
- CLI: `--demo`, `--file records.csv`, `--spec interfaces.json`
- Bundled data: valid, bad, and empty CSVs + interface spec
- 51 passing pytest tests

---

# 📂 Folder Structure

```text
Type_Hints_Refactoring/
│
├── src/
│   ├── main.py     # CLI: --demo, --file, --spec, --quiet
│   ├── legacy.py   # BEFORE: untyped, raw errors, silent bugs
│   └── typed.py    # AFTER: hints, Protocols, validation, contracts, demo
│
├── tests/
│   └── test_refactor.py
│
├── data/
│   ├── records.csv       # 8 valid sales lines (id, units, price)
│   ├── records_bad.csv   # negative/zero values legacy accepts silently
│   ├── records_empty.csv # header-only file (the empty-input contrast)
│   └── interfaces.json   # method/params/annotation contracts
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 25_Software_Engineering/Type_Hints_Refactoring

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: before/after comparison + contract checks
python src/main.py --demo

# Typed load + summary of a sales CSV
python src/main.py --file data/records.csv

# Verify code against the interface spec (mypy-style, manually)
python src/main.py --spec data/interfaces.json
```

Input schema (CSV header required):

```csv
id,units,price
S-1,3,19.99
```

(`id` non-empty string; `units` integer ≥ 1; `price` number > 0 and finite. Row errors are reported as `record N: ...` with the 0-based row index.)

**Exit codes:** `0` = success · `2` = missing file, schema/row violation, contract violation, malformed spec · `2` (argparse) = no action or conflicting actions.

---

# 🧠 How It Works

```text
  BEFORE (legacy.py)                      AFTER (typed.py)
  ─────────────────                       ────────────────
  load_records(path)                      load_records(path)
    csv.DictReader, no checks               header check → "missing column"
    rows of raw strings                     parse_row(index) per row
                                            SaleRecord.__post_init__ validation
  summarize(rows)                         summarize(Sequence[SaleRecord])
    float() coercion anywhere                typed fields, Summary dataclass
    total/len → ZeroDivisionError            empty → "no records to summarize"
    negative units silently included         units >= 1 enforced at the boundary
        │                                          │
        └────────── demo asserts they agree on valid data (581.58) ──────┘
                                    │
                     SupportsRevenue Protocol (runtime_checkable)
                     SaleRecord + Refund satisfy it structurally
                                    │
                     interfaces.json ──► check_contract(inspect.signature)
                                          method presence + params + annotations
                                          → "0 violations"
```

Details worth knowing:

- **The refactor changes behaviour only on invalid input** — on valid CSVs both modules return byte-identical summaries (the demo asserts `count/total/mean/top` equality), which is exactly what a safe refactor should look like.
- **`RecordError` names the row**: `record 0: units must be >= 1` — the index, the field, and the violated rule, checked type-before-range so the *first* violation wins.
- **`runtime_checkable` only proves attribute presence** — the contract checker goes further with `inspect.signature` (declared parameter names, annotation completeness), the pieces a structural `isinstance` can never catch.

---

# 🛠 Technologies

- Python 3 (100 % standard library)
- `typing.Protocol` / `TypedDict` / `runtime_checkable`, `dataclasses(slots=True)`
- `inspect` (manual contract checking), `csv`, `json`, `math`
- `argparse` / `pathlib` / `logging`
- pytest

---

# 📚 Concepts Covered

- Incremental refactoring: keep behaviour, add guarantees
- Type-hinting every boundary: parameters, returns, dataclasses
- Structural subtyping with `Protocol` vs nominal inheritance
- Runtime validation that mirrors static types (fail fast, fail clear)
- Error messages that name the row, the field, and the rule
- Enforcing interface contracts without mypy (`inspect.signature`)
- Before/after regression proof: outputs must match on valid inputs
- Designing CLI flags that fast-fail before expensive work

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**51 tests passed** covering legacy behaviours (raw `KeyError`/`ZeroDivisionError`, silent negative-units bug), every typed validation rule (header, rows, id/units/price types and ranges, finite checks, first-error ordering), `SaleRecord` frozen/slots/`__post_init__` contracts, summary determinism, Protocol conformance (positive *and* negative cases), repository API semantics, contract-checker violations (missing method, param mismatch, missing annotations, unknown class), interface-spec errors, demo idempotency, and every CLI path — all offline.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found these projects useful, consider giving this repository a star.

</div>
