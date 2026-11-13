<div align="center">

# 🔤 Word2Vec From Scratch

### Skip-gram with negative sampling trained in pure NumPy — no gensim, no pre-trained vectors, no downloads. Learns `king`→`queen` and solves `man : king :: woman : queen` from a bundled corpus.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-From%20Scratch-013243?style=for-the-badge&logo=numpy&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Word2Vec From Scratch implements the original **skip-gram with negative sampling** objective (Mikolov et al., 2013) end to end in NumPy:

```text
J = -log σ(u_context · v_centre)  -  Σ_{k=1..K} log σ(-u_negative_k · v_centre)
```

Negatives are drawn from the unigram distribution raised to the 0.75 power, using a pre-computed cumulative search-sorted table — exactly the trick the original C implementation uses to make sampling O(1). Gradients are derived by hand (and verified numerically during development) and applied with **dense Adam**, which keeps the effective step size scale-free so a 103-word embedding table trains stably in a couple of seconds.

The bundled corpus is generated deterministically from sentence templates that deliberately expose semantic structure: royal pairs (`king`/`queen`, `prince`/`princess`), gender pairs (`man`/`woman`, `boy`/`girl`), capital cities (`paris`/`france`, `tokyo`/`japan`), animals, fruit and weather. After 20 epochs the demo asserts that `king`'s nearest neighbour is `queen`, that `cos(king, queen)` beats `cos(king, banana)` by a clear margin, and that the analogy `man : king :: woman` ranks `queen` first.

No network, no API keys, no downloads.

---

# ✨ Features

- Skip-gram pair generation with configurable window (both directions)
- Unigram^0.75 negative-sampling table (`np.searchsorted`, O(1) draws)
- Hand-derived gradients, mini-batch updates, dense Adam optimiser
- `similarity`, `most_similar`, `analogy` vector queries
- Deterministic training: same seed → bit-identical vectors
- `--demo`, `--corpus`, `--similar`, `--analogy`, `--json` CLI
- Strict flag validation before reading or training
- 66 passing pytest tests

---

# 📂 Folder Structure

```text
Word2Vec_From_Scratch/
│
├── src/
│   ├── main.py      # CLI: --demo, --corpus, --similar, --analogy, --json
│   └── word2vec.py  # corpus, vocab, pairs, sampling, Adam training, demo
│
├── tests/
│   └── test_word2vec.py
│
├── data/
│   └── corpus.txt   # bundled, regenerated and verified by the demo
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 19_NLP/Word2Vec_From_Scratch

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: train, neighbours, analogy, sampling check, determinism
python src/main.py --demo

# Train on your own text and query it
python src/main.py --corpus mytext.txt
python src/main.py --similar king
python src/main.py --analogy man king woman
python src/main.py --corpus mytext.txt --dim 64 --epochs 40 --json model.json
```

**Input:** any plain-text file. Lowercase alphabetic tokens are extracted with a regex, so punctuation and numbers are ignored.

**Exit codes:** `0` = success · `2` = usage/validation/unknown-word error.

---

# 🧠 How It Works

```text
corpus.txt ──► lowercase tokens ──► vocab (count desc, then alpha)
                                          │
                                          ▼
                        skip-gram pairs (centre, context), window=2
                                          │
        ┌─────────────────────────────────┴───────────────────────────────┐
        ▼                                                                 ▼
  negative table: p(w) ∝ count^0.75                              w_in, w_out matrices
  cumsum + searchsorted (O(1))                                            │
        │                                                                 ▼
        └──────────────────► batch: 1 positive + K negatives ──► loss + grads
                                          │
                                          ▼
                                   dense Adam update
                                          │
                                          ▼
                     loss 1.394 -> 1.055 over 20 epochs
```

Two details are worth calling out. First, the naive `SGD` version of this code *diverged*: with batch-mean gradients and `lr=0.2` the loss rose from 1.386 to 1.78 because the embedding rows for frequent words received far too many overlapping updates per step. Adam's per-parameter second moment fixes this, and `lr=0.005` converges cleanly — the difference between a loss curve that climbs and one that falls.

Second, the negative-sampling table is verified rather than assumed: the demo compares the empirical draw frequencies against `count^0.75 / Σ count^0.75` and asserts a maximum deviation below 0.01.

---

# 🛠 Technologies

- Python 3
- NumPy (`einsum`, `add.at`, cumulative sums, `searchsorted`)
- argparse / json / dataclasses / logging
- pytest

No gensim, no spaCy, no torch, no pre-trained embeddings.

---

# 📚 Concepts Covered

- Skip-gram objective and negative sampling
- Unigram^0.75 noise distribution and alias-free sampling tables
- Manual gradient derivation for a two-matrix embedding model
- Mini-batch training and the role of optimiser choice
- Adam: first/second moments and bias correction
- Cosine similarity, `most_similar`, and vector arithmetic analogies
- Determinism via seeded RNG
- Why small corpora need regularisation by design (dimension, epochs, LR)

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**66 tests passed** covering corpus determinism, bundling and load errors, tokenisation edge cases, vocabulary ordering and `min_count`, skip-gram pair construction (including self-pair rejection), negative-table distribution accuracy and power behaviour, all training flag validations, loss decrease, determinism across runs, seed sensitivity, similarity symmetry/self/unknown-word paths, neighbour ordering and exclusion, analogy inputs, JSON export, demo idempotency, quiet mode, and every CLI error path.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
