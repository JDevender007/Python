<div align="center">

# 🏷️ Named Entity Recognizer

### Rule, pattern, and gazetteer NER for dates, money, places, and organisations — scored against a bundled annotated sample (micro F1 = 1.000). Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![NLP](https://img.shields.io/badge/NLP-Named_Entities-10A37F?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Named Entity Recognizer finds four entity types in plain text — **DATE** (`March 5, 1994`, `15 June 2019`, `2023-07-14`, `12/31/2025`, `June 2019`), **MONEY** (`$4.5 million`, `€2,000`, `12 million dollars`, `£75`), **PLACE** (bundled 25-entry gazetteer with longest-match wins) and **ORG** (10-entry gazetteer + organisation-suffix rule like `Acme Inc.`, `Stanford University`) — using nothing but regex patterns, word-boundary lookups, and a longest-span overlap resolver.

Every run can be **scored against a bundled gold sample**: 5 annotated sentences with 20 exact spans, evaluated with per-label and micro precision/recall/F1. The demo asserts micro **P/R/F1 ≥ 0.85** (the bundled sample scores a perfect 1.000), span-slice consistency, zero overlaps, determinism, and metric sanity (a perfect predictor must get 1.0; an empty one must get 0.0). **No network, no downloads, no spaCy/NLTK — rules ship in code, data ships in `data/`.**

---

# ✨ Features

- 5 date patterns: month-day-year, day-first, month-year, ISO `YYYY-MM-DD`, `M/DD/YYYY` (bare years are deliberately *not* dates)
- 2 money patterns: currency symbols with optional scale words, and scale-word + currency-noun forms
- Gazetteer loader with validation (capitalised entries, no duplicates, non-empty)
- Organisation-suffix regex (`Inc.`, `LLC`, `Corporation`, `University`, `Bank`, …) with article-trimming so `the Bank of England` never yields `The Bank`
- Longest-span-wins overlap resolution with label-priority tie-breaking; spans always slice back to the source text
- `evaluate()` computing per-label and micro P/R/F1 with exact-span matching; duplicate predictions collapse
- `load_gold()` with strict annotation-schema validation (bounds, label whitelist, declared-text consistency)
- CLI: `--demo`, `--file`, `--text`, `--gold`, `--json`, `--quiet` — fast-fail flag checks
- **51 passing pytest tests**

---

# 📂 Folder Structure

```text
Named_Entity_Recognizer/
│
├── src/
│   ├── main.py   # CLI: --demo, --file, --text, --gold, --json, --quiet
│   └── ner.py    # patterns, gazetteers, overlap resolution, metrics, demo
│
├── tests/
│   └── test_ner.py
│
├── data/
│   ├── gold.json             # 5 annotated texts, 20 gold spans
│   ├── gazetteer_places.txt  # 25 place names
│   └── gazetteer_orgs.txt    # 10 organisation names
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 19_NLP/Named_Entity_Recognizer

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: annotate sample, score vs gold, cross-checks
python src/main.py --demo

# Annotate inline text
python src/main.py --text "Acme paid $4.5 million in Geneva on 2023-07-14."

# Annotate a text file
python src/main.py --file notes.txt

# Score the recognizer against your own gold annotations
python src/main.py --gold my_gold.json

# Entities as JSON
python src/main.py --file notes.txt --json entities.json
```

Input schema (for `--gold`, JSON array of annotated texts):

```json
[
  {
    "text": "Acme Corporation paid $4.5 million in London.",
    "entities": [
      {"text": "Acme Corporation", "label": "ORG",   "start": 0,  "end": 16},
      {"text": "$4.5 million",     "label": "MONEY", "start": 23, "end": 36},
      {"text": "London",           "label": "PLACE", "start": 40, "end": 46}
    ]
  }
]
```

(`label` ∈ DATE/MONEY/PLACE/ORG; spans must satisfy `0 ≤ start < end ≤ len(text)` and the declared `text` must equal `text[start:end]`. `--text` must be non-empty; exactly one of `--demo/--file/--text/--gold` is required.)

**Exit codes:** `0` = success · `2` = usage/validation/file error.

---

# 🧠 How It Works

```text
input text
     │
     ├─► DATE patterns   (?<!\w)...  month-day-year | day-first | month-year
     │                   | YYYY-MM-DD | M/DD/YYYY
     ├─► MONEY patterns  [$€£]amount[scale]  |  amount[scale] dollars|euros|pounds
     ├─► PLACE gazetteer (?<!\w)Geneva(?!\w)  ... longest entries matched first
     └─► ORG rules       gazetteer  +  [Capitalised run]Inc|Ltd|Bank|University...
                                │
                                ▼  candidate spans (start, end, label)
        sort by (-length, start, label priority) → greedy overlap filter
                                │
                                ▼
        Entity(text[start:end], label, start, end)   sorted, non-overlapping
                                │
                                ▼  vs gold.json (exact span + label)
        per-label P / R / F1  +  micro P / R / F1
```

Details worth knowing:

- **Exact-span matching** is the strictest NER scoring: `Bank` inside `Bank of England` counts as a false positive *and* a false negative — which is why longest-match resolution happens before evaluation.
- **Bare years are not dates** — `in 1989` needs no annotation, while `June 1989` and `15 June 2019` are; the pattern set encodes that decision explicitly.
- **Overlaps are resolved globally**: candidates are sorted longest-first, then greedily accepted if they don't touch an accepted span — so the gazetteer's `New York City` beats its own `New York` entry.
- **Metrics are sanity-checked in the demo**: `evaluate(gold, gold)` must return F1 1.000 and `evaluate([], gold)` must return 0.0 — proving the scorer itself before trusting its output.

---

# 🛠 Technologies

- Python 3 (standard library only at runtime)
- `re` (five date patterns, two money patterns, org-suffix rule, boundary lookarounds)
- `dataclasses` (frozen `Entity` with validated spans)
- `json` / `argparse` / `pathlib` / `logging`
- pytest

---

# 📚 Concepts Covered

- Rule-based NER: patterns vs gazetteers vs suffix heuristics
- Gazetteer design: longest match, word-boundary lookarounds, entry validation
- Overlap/priority resolution for competing span candidates
- Precision, recall, F1 — per-label and micro-averaged
- Exact-span evaluation and why partial overlaps count as errors
- Annotation (gold) file schemas and consistency checks
- Reproducible, offline evaluation harnesses
- Fast-fail CLI validation and exit-code discipline

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**51 tests passed** covering Entity validation (labels, spans, integer types), gazetteer loading rules, every date and money pattern (including non-matches: bare years, plain numbers), longest-match and article-trimming behaviour, whole-pipeline invariants (sorted, non-overlapping, slice-consistent, deterministic), evaluation math against hand-computed values (perfect / empty / partial / duplicate predictions), gold-schema error cases, demo idempotency, and every CLI path — all offline. Extra cases pin the evaluation contract (every label reported, a perfect match scoring 1.0, a missed gold span showing up as a false negative), gazetteer order preservation, and the blank-text refusal.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
