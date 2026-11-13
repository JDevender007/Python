<div align="center">

# 🏷️ POS Tag Tagger

### A bigram HMM part-of-speech tagger with Viterbi decoding — bundled 600-sentence tagged corpus, per-tag metrics, and a most-frequent-tag baseline. Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-2.x-4DABCF?style=for-the-badge&logo=numpy&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

POS Tag Tagger trains a **bigram Hidden Markov Model** (initial π, transition P(t′|t), emission P(w|t)) on a CoNLL-style tagged corpus — one `word<TAB>tag` per line, blank line between sentences — and decodes the best tag sequence with the **Viterbi algorithm in log space**. The tagged corpus ships with the project: **600 sentences, 4,080 tokens, 167 distinct words, 20 Penn Treebank tags** in `data/corpus.txt`; nothing is downloaded at runtime.

The demo trains on a chronological 80/20 split, scores the held-out 120 sentences against a **most-frequent-tag baseline**, and prints per-tag precision/recall/F1 with support plus a sample tagging of a raw sentence. `--sentence` tags any input text with the trained model, `--file` evaluates your own corpus with a `--ratio` split, and `--json` exports the metrics.

Training is pure counting (no RNG anywhere), smoothing is fixed add-k with α = 0.1, and decoding breaks ties with a deterministic `argmax` — re-training reproduces byte-identical tables, which the demo asserts. The corpus loader validates every line (exactly two tab-separated fields, tags from the closed 20-tag set, ≥ 20 sentences). **No network, no downloads, no external taggers.**

---

# ✨ Features

- Bigram HMM with add-k smoothing (α = 0.1) over initial, transition, and emission tables in log space
- Log-space Viterbi decoding with `<UNK>` bucket and exact → lowercase → `<UNK>` word lookup
- Chronological train/test split (`--ratio`, default 0.8) with a most-frequent-tag baseline
- Per-tag precision / recall / F1 / support report that sums exactly to the test tokens
- `tag_text()` / `--sentence "..."` tags any raw sentence with the trained model
- Strict corpus validation: line format, unknown tags, empty sentences, minimum size
- `--json metrics.json` export, `--quiet` mode, deterministic re-training (demo asserts it)
- Bundled dataset: 600 tagged sentences (4,080 tokens, 167 words, 20 tags) as `data/corpus.txt`
- 45 passing pytest tests

---

# 📂 Folder Structure

```text
Pos_Tag_Tagger/
│
├── src/
│   ├── main.py        # CLI: --demo, --file, --sentence, --ratio, --json, --quiet
│   └── hmm_tagger.py  # corpus, HMM training, Viterbi, metrics, report, demo
│
├── tests/
│   └── test_hmm_tagger.py
│
├── data/
│   └── corpus.txt     # 600 sentences x 4,080 tokens, 167 words, 20 tags
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 19_NLP/Pos_Tag_Tagger

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: train, split, per-tag metrics, sample tagging, cross-checks
python src/main.py --demo

# Train/evaluate on your own CoNLL corpus
python src/main.py --file data/corpus.txt --ratio 0.9

# Tag one raw sentence with the bundled corpus
python src/main.py --sentence "Where does the dog sleep"

# Metrics as JSON
python src/main.py --file data/corpus.txt --json metrics.json
```

Input schema (one `word<TAB>tag` per line, blank line between sentences):

```text
Where	WRB
does	VBZ
the	DT
dog	NN
sleep	VB
```

(`tag` must be one of the 20 Penn Treebank tags — `CC CD DT IN JJ MD NN NNS PRP RB TO VB VBD VBG VBP VBZ WP WRB , .` — and a corpus needs ≥ 20 sentences.)

**Exit codes:** `0` = success · `2` = usage/corpus error.

---

# 🧠 How It Works

```text
data/corpus.txt ──► parse word<TAB>tag (validate format, tags, ≥ 20 sentences)
                          │
                          ▼  chronological 80 / 20 split
        train (480 sentences)            test (120 sentences, held out)
                          │
                          ▼
   counts ──► initial π, transition P(t'|t), emission P(w|t)
              + add-k smoothing (α = 0.1), last column = <UNK>
                          │
                          ▼
   log-space Viterbi ──► best tag sequence per sentence
                          │
                          ▼
   accuracy vs most-frequent-tag baseline, per-tag P/R/F1/support,
   sample tagging of a raw sentence
```

Details worth knowing:

- **Everything is log-space** — products of hundreds of probabilities underflow to zero; sums of logs do not.
- **The `<UNK>` column** gives unseen words one shared, smoothed emission column instead of dividing probability mass over an ever-growing vocabulary.
- **Lookup falls back exact → lowercase → `<UNK>`**, so `Where` and `where` hit the same entry while the surface form is kept for display.
- **The baseline is fierce** — on a closed 167-word corpus the most-frequent tag already scores **0.996**; the HMM's job is the last 0.004, the rare tags (WRB, WP, VBG …) that a majority guesser can never place. Typical demo result: **1.000 vs 0.996**.
- **Deterministic by construction** — pure counting, fixed smoothing, `argmax` tie-breaks; the demo re-trains and asserts the tables and the decoded sample are identical.

---

# 🛠 Technologies

- Python 3
- numpy (log-probability tables, vectorised Viterbi DP, argmax)
- argparse / logging / dataclasses / pathlib
- pytest

---

# 📚 Concepts Covered

- Hidden Markov Models: initial, transition, and emission distributions
- The Viterbi algorithm as dynamic programming over a trellis
- Why decoding runs in log space (numerical underflow)
- Add-k smoothing and the `<UNK>` bucket for open vocabulary
- Most-frequent-tag baseline and when a baseline is actually hard to beat
- Per-tag precision / recall / F1 with support, and their consistency checks
- Chronological train/test splits for sequence data
- CoNLL corpus format and closed tag-set validation

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**45 tests passed** covering every validation rule (missing corpus, bad line format, unknown tags, empty sentences, too few sentences, bad `--ratio`, bad `alpha`, empty inputs), training table shapes and probability normalisation, Viterbi correctness, determinism and unknown-word decoding, baseline arithmetic, per-tag metric consistency (supports sum to test tokens), report rendering, exact sample tagging, demo idempotency, and every CLI path — all offline.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
