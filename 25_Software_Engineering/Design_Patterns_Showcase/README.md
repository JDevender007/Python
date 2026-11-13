<div align="center">

# 🧩 Design Patterns Showcase

### Five Gang-of-Four patterns — Singleton, Factory, Observer, Strategy, Decorator — each with a tiny runnable example and tests that prove the pattern's contract. Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Patterns](https://img.shields.io/badge/Patterns-5-blue?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Design Patterns Showcase implements **five classic GoF patterns** as small, honest, runnable components: a metaclass **Singleton** with a reset hook for test isolation, an **Factory** that builds orders by kind from a pluggable registry, an **Observer** event bus with ordered delivery and sandboxed handler failures, a **Strategy** pricer with three swappable shipping algorithms, and a **Decorator** pipeline whose composition order is visibly order-sensitive.

Every pattern section runs its own deterministic self-assertions against **bundled order records** (`data/orders.json`) — nothing is downloaded at runtime. The test suite proves each pattern's *contract* (single instance, pluggable construction, ordered broadcast, swappable algorithm, order-sensitive wrapping), not just that the code runs. **No network, no API keys.**

---

# ✨ Features

- `SingletonMeta` metaclass: one instance per class, `reset_singletons()` for isolation
- `OrderFactory`: registry of builders, `create`/`create_many`, unknown-kind rejection
- `EventBus`: subscription-order delivery, duplicate-subscribe guard, failing handlers sandboxed and recorded
- `PricingService`: strategy swap by instance **or** name (`standard`, `express`, `bulk`)
- `TextDecorator` stack: `UpperCase`, `Truncate`, `Prefix` — order changes output
- Strict validation of every order record (fields, types, ranges, known kinds)
- CLI: `--demo`, `--list`, `--pattern NAME`, `--file` schema validator
- Deterministic: rebuilds, quotes, and observer delivery are identical every run
- Bundled dataset: 6 order records in `data/orders.json`
- 55 passing pytest tests

---

# 📂 Folder Structure

```text
Design_Patterns_Showcase/
│
├── src/
│   ├── main.py     # CLI: --demo, --list, --pattern, --file, --quiet
│   └── patterns.py # 5 patterns + data loading + demo sections
│
├── tests/
│   └── test_patterns.py
│
├── data/
│   └── orders.json # 6 order records: id, kind, weight, distance, items
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 25_Software_Engineering/Design_Patterns_Showcase

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: all five patterns with self-assertions
python src/main.py --demo

# List the available patterns
python src/main.py --list

# Run a single pattern section
python src/main.py --pattern strategy

# Validate an orders JSON against the schema
python src/main.py --file data/orders.json
```

Input schema (JSON array of objects):

```json
[
  {"id": "ORD-1001", "kind": "standard", "weight_kg": 2.5,
   "distance_km": 120.0, "items": 3}
]
```

(`kind` ∈ `standard|express|digital`; `weight_kg`, `distance_km` ≥ 0 numbers; `items` integer ≥ 1; `id` non-empty string.)

**Exit codes:** `0` = success · `2` = unknown pattern, missing/invalid file, schema error · `2` (argparse) = no action or conflicting actions.

---

# 🧠 How It Works

```text
data/orders.json ──► load_orders()  validate: fields, types, ranges, kinds
                              │
                              ▼
              default_factory() ── create_many() ──► list[Order] (frozen)
                              │
        ┌─────────────┬───────┴────────┬──────────────┐
        ▼             ▼                ▼              ▼
   Singleton      Observer bus     PricingService   Decorator stack
   one instance   ordered +        standard/        Plain→Upper→
   per class      sandboxed        express/bulk     Truncate→Prefix
   (metaclass)    handlers         (swappable)      (order-sensitive)
                              │
                              ▼
              cross-checks: rebuild == orders, quotes deterministic,
              observer delivery reproducible ──► "Cross-checks OK"
```

Details worth knowing:

- **Singleton caches on the metaclass** (`SingletonMeta._instances`), so the one-instance guarantee is per *class*, and `reset_singletons()` keeps tests hermetic.
- **The factory rejects before it builds**: unknown kind fails first, then the shared builder re-validates defensively — so a hand-written record can never bypass the schema.
- **Observer never cascades**: a raising handler is captured into `bus.errors` and the remaining handlers still receive the payload, in subscription order.
- **Decorator composition is not commutative** — the demo proves `Prefix(Truncate(Upper(x), 4), ">> ")` ≠ `Truncate(Prefix(Upper(x), ">> "), 4)`.

---

# 🛠 Technologies

- Python 3
- `dataclasses` (frozen `Order`), metaclasses, ABC-style component base
- `json` / `pathlib` / `argparse` / `logging`
- pytest

---

# 📚 Concepts Covered

- Singleton via metaclass and why `reset` hooks matter for tests
- Factory method + registry: open for extension, closed for modification
- Observer pub/sub: ordered delivery, duplicate suppression, failure isolation
- Strategy: programme to an interface, swap algorithms at runtime
- Structural decorators: transparent wrapping and order sensitivity
- Validating external JSON at the boundary (fail fast, fail clear)
- Pure, deterministic demo sections with self-assertions
- Designing CLI flags that fast-fail before expensive work

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**55 tests passed** covering every data-validation rule (missing files, malformed JSON, missing fields, unknown kinds, type and range checks), each pattern's contract (shared singleton state, factory unknown-kind rejection, observer order + sandboxing, strategy swaps + pricing formulas, decorator composition order), `run_pattern` name validation, demo idempotency, and every CLI path — all offline.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found these projects useful, consider giving this repository a star.

</div>
