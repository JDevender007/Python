<div align="center">

# 📝 Text Summarizer

### Extractive summarization with TF-IDF centroid sentence ranking — bundled articles, compression metrics, and top-term coverage. Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![NLP](https://img.shields.io/badge/NLP-Summarization-10A37F?style=for-the-badge)
![NumPy](https://img.shields.io/badge/NumPy-TF--IDF-DDDDDD?style=for-the-badge&logo=numpy&logoColor=black)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Text Summarizer is an **extractive** summarizer: it never writes new words — it selects the sentences from the original article that best represent it. A rule-based splitter (abbreviation-aware: `Dr.`, `e.g.` never break a sentence) chops the article into sentences, a hand-rolled **TF-IDF matrix** (smooth idf, L2-normalised rows) embeds each one, and every sentence is scored by its **cosine similarity to the document centroid**. The top `ceil(ratio × sentences)` sentences, restored in original order, form the summary.

The demo summarizes three bundled articles (~9 sentences each) at `ratio=0.4` and asserts its own output: subsets sorted and verbatim, compression strictly below 1, coverage ≥ 0.6, the best-scored sentence always selected, and a deterministic re-run. **No network, no downloads, no scikit-learn required — TF-IDF is built here in NumPy.**

---

# ✨ Features

- `split_sentences()`: boundary regex + abbreviation protection (`mr.`, `dr.`, `e.g.`, `u.s.`, …), never emits empty sentences
- `build_tfidf()`: term counts → `tf × (ln((1+N)/(1+df)) + 1)` → L2 rows, vocabulary sorted for determinism
- `score_sentences()`: cosine of each sentence with the mean TF-IDF centroid (tie-break: earlier index wins)
- `summarize(text, ratio)`: keeps `ceil(ratio · n)` sentences, returns a `SummaryResult` with scores and metrics
- Compression metrics: char compression ratio, compression factor, **top-term coverage** (fraction of the 10 heaviest document terms retained)
- `load_articles()`: strict JSON schema validation (`title` non-empty, `text ≥ 150` chars)
- CLI: `--demo`, `--file`, `--text`, `--index`, `--ratio`, `--json`, `--quiet` with fast-fail flag validation
- Fully deterministic — same input, same summary, every run
- **51 passing pytest tests**

---

# 📂 Folder Structure

```text
Text_Summarizer/
│
├── src/
│   ├── main.py        # CLI: --demo, --file, --text, --index, --ratio, --json
│   └── summarizer.py  # splitter, TF-IDF, centroid scoring, metrics, demo
│
├── tests/
│   └── test_summarizer.py
│
├── data/
│   └── articles.json  # 3 bundled articles (Voyager, Coffee, World Wide Web)
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 19_NLP/Text_Summarizer

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: 3 bundled articles, ranked sentences, cross-checks
python src/main.py --demo

# Summarize every article in your own JSON file
python src/main.py --file articles.json

# Only article #1, keep half the sentences
python src/main.py --file articles.json --index 1 --ratio 0.5

# Summarize inline text
python src/main.py --text "First sentence here. Second one here." --ratio 0.5

# Metrics as JSON
python src/main.py --file articles.json --index 0 --json summary.json
```

Input schema (for `--file`, JSON array of objects):

```json
[
  {
    "title": "The Voyager Missions",
    "text": "NASA launched Voyager 1 in September 1977, ..."
  }
]
```

(`title` non-empty string; `text` ≥ 150 characters; `--ratio` ∈ (0, 1]; `--index` ≥ 0 and only with `--file`; `--text` cannot be combined with `--demo`/`--file`.)

**Exit codes:** `0` = success · `2` = usage/validation/file error.

---

# 🧠 How It Works

```text
article text
      │
      ▼  split_sentences(): (?<=[.!?])\s+ with abbreviations protected
sentences  [s0, s1, s2, ... sN]  (order preserved, verbatim)
      │
      ▼  build_tfidf(): counts → tf · (ln((1+N)/(1+df)) + 1) → L2 rows
sentence × vocabulary matrix          vocabulary sorted a→z
      │
      ▼  score_sentences(): cosine(row, mean(matrix))
scores  [0.42, 0.47, 0.43, ...]      ties broken by earlier index
      │
      ▼  keep top k = ceil(ratio · N), restore original order
summary = "sk0 sk1 ..."   +  metrics: compression, factor, coverage
```

Details worth knowing:

- **Extractive, so summaries always quote the source verbatim** — the demo proves it by checking every selected sentence appears in the article.
- **Smooth idf `ln((1+N)/(1+df)) + 1`** never produces zero weights for terms that appear in every sentence, so rare-but-central terms still rank.
- **Centroid cosine is a cheap centroid TextRank**: sentences similar to the document "average" represent its theme; the top-ranked sentence is always in any non-empty selection (asserted in the demo).
- **Coverage** guards against summaries that are fluent but off-topic: if the summary dropped most of the 10 heaviest document terms, the demo fails.

---

# 🛠 Technologies

- Python 3
- NumPy (TF-IDF matrix, vectorised cosine scoring, `argmax`)
- `re` (sentence boundaries, abbreviation protection, tokenization)
- `json` / `math` / `dataclasses` / `argparse` / `pathlib` / `logging`
- pytest

---

# 📚 Concepts Covered

- Extractive vs abstractive summarization
- TF-IDF from first principles: term frequency, document frequency, smooth idf, L2 normalization
- Centroid-based sentence ranking (cosine similarity)
- Sentence segmentation pitfalls: abbreviations, multiple terminators, whitespace runs
- Compression ratio and top-term coverage as summary quality metrics
- Deterministic ranking with explicit tie-breakers
- Fast-fail CLI validation before expensive work
- Modular programming with type hints and dataclasses

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**51 tests passed** covering sentence splitting (abbreviations, empties, newlines, validation), the TF-IDF formula against hand-computed values, row normalization, centroid scoring behaviour, article JSON schema validation (missing file, broken JSON, non-list, short text), summarization invariants (`ceil` selection math, verbatim reconstruction, ratio limits, determinism), metrics arithmetic, demo idempotency, and every CLI path — all offline. Extra cases pin the result contract: sentence counts, compression and coverage in [0, 1], selected indices in range and unique, the summary being a verbatim subset in document order, the character count matching the joined text, lowercase top terms, the one-sentence floor at ratio 0.1, and punctuation-free tokenisation.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
