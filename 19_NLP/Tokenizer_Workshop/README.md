<div align="center">

# ✂️ Tokenizer Workshop

### A regex tokenization pipeline — normalization, stemming, stopword removal, n-grams, and token statistics over a bundled corpus. Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![NLP](https://img.shields.io/badge/NLP-Tokenization-10A37F?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Tokenizer Workshop is a **pure standard-library** text preprocessing pipeline: NFKC normalization with unicode quote/dash folding, a regex tokenizer that keeps apostrophes and hyphens glued (`don't`, `state-of-the-art`), stopword removal from a bundled list, a simplified Porter-style rule stemmer, contiguous n-grams, and deterministic token statistics.

Everything runs from bundled files — the demo tokenizes `data/corpus.txt` against `data/stopwords.txt`, so **no network, no downloads, no API keys, no NLTK**. The demo asserts its own output (bigram counts, stem rules, top-token ordering, pipeline determinism) before printing `Cross-checks OK` and finishing.

`--file` runs the same pipeline on your own text; `--text` tokenizes an inline string; `--json` exports the metrics. Bad flags fail fast — before any pipeline work starts.

---

# ✨ Features

- `normalize()`: NFKC + curly-quote/dash folding + lowercase + whitespace collapse
- `tokenize()` with a single regex: letters/digits, `'` and `-` glue, `min_length`, `keep_numbers`
- Bundled 128-word stopword list with strict loader validation (lowercase alphabetic only)
- Simplified rule stemmer (`running → run`, `studies → study`, `processed → process`, `classes → class`) — first matching suffix rule wins, doubled consonants collapse only after short vowels
- `ngrams()` for any `n ≥ 1`, plus `token_stats()` (total/unique, averages, digit counts, count-then-alphabetical top tokens)
- `process()` pipeline returning a `TokenizeResult` with a JSON-serializable `to_dict()`
- CLI: `--demo`, `--file`, `--text`, `--n`, `--min-length`, `--no-stopwords`, `--drop-numbers`, `--top`, `--json`
- Fully deterministic — running the demo twice yields identical counts
- **50 passing pytest tests**

---

# 📂 Folder Structure

```text
Tokenizer_Workshop/
│
├── src/
│   ├── main.py        # CLI: --demo, --file, --text, --n, --json, --quiet
│   └── tokenizer.py   # normalize, tokenize, stopwords, stem, n-grams, stats, demo
│
├── tests/
│   └── test_tokenizer.py
│
├── data/
│   ├── corpus.txt     # 12 bundled paragraphs (~2.1 KB of plain English)
│   └── stopwords.txt  # 128 lowercase stopwords, one per line
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 19_NLP/Tokenizer_Workshop

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: bundled corpus -> tokens, stems, bigrams, stats, cross-checks
python src/main.py --demo

# Tokenize your own text file
python src/main.py --file notes.txt

# Inline text with a trigram pipeline
python src/main.py --text "The cats are running quickly" --n 3

# Keep stopwords, drop numbers, export metrics
python src/main.py --file notes.txt --no-stopwords --drop-numbers --json stats.json
```

Input schema (for `--file`): any UTF-8 text file — one paragraph per line, blank lines ignored, no header or special delimiters required.

```text
Natural language processing begins with tokenization.
Stopwords are the tiny glue words of a language.
```

(`--text` must be a non-empty string; `--n`, `--min-length` and `--top` must be `≥ 1`; `--text` cannot be combined with `--demo`/`--file`.)

**Exit codes:** `0` = success · `2` = usage/validation/file error.

---

# 🧠 How It Works

```text
raw text (data/corpus.txt)
      │
      ▼  normalize(): NFKC → fold '’ “ ” – — → lowercase → collapse spaces
normalized string
      │
      ▼  tokenize(): regex  [a-z0-9]+(['\-][a-z0-9]+)*
raw tokens ───────────────────────────────► token_stats() (total, unique,
      │                                      avg length, digit counts,
      ▼  remove_stopwords(data/stopwords.txt)  count-then-alpha top-N)
kept tokens
      │
      ▼  stem(): ordered suffix rules, first match wins,
stems          doubled consonant collapse (run/stop) → never longer than input
      │
      ▼  ngrams(kept, n)
n-grams  →  report + optional stats.json
```

Details worth knowing:

- **Stemming is rule-ordered, not chained** — the first suffix rule that matches fires (`ational → ate`, `ies → y`, `ing → ''`, plain `s → ''` guarded against `ss/us/is`), so results are predictable and unit-testable.
- **Doubled consonants collapse only after short vowels and never `ss`/`ll`** — `running → runn → run` but `processed → process` stays intact.
- **The demo cross-checks itself**: bigram count must equal `len(tokens) − 1`, the top token must hold the maximum count, stems must never lengthen their token, and a second full pipeline run must produce an identical dict.
- **Statistics are rank-deterministic**: tokens are sorted by `(-count, token)`, so ties break alphabetically instead of by first appearance.

---

# 🛠 Technologies

- Python 3 (standard library only at runtime)
- `re` / `unicodedata` (regex tokenization, NFKC normalization)
- `collections.Counter` (token statistics)
- `dataclasses` / `pathlib` / `argparse` / `json` / `logging`
- pytest

---

# 📚 Concepts Covered

- Text normalization: NFKC, unicode folding, whitespace collapsing
- Regex tokenization and why glue characters (`'`, `-`) matter
- Stopword lists as bundled, validated data files
- Suffix-strip stemming: ordered rules, guards, doubled-consonant handling
- N-grams as local word-order features
- Type-token ratios and frequency-rank statistics
- Deterministic pipelines and idempotent demos
- Fast-fail CLI validation (bad flags rejected before any work)
- Modular programming with type hints and dataclasses

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**50 tests passed** covering every validation rule (text types, `min_length`, `n`, `top`, stopword files, corpus files), stem rules against a known word table, n-gram counts and edge cases, statistics arithmetic and tie ordering, pipeline determinism and JSON serialization, demo idempotency (run twice), and every CLI path — all offline.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
