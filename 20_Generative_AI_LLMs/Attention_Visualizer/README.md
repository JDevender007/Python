<div align="center">

# 🎯 Attention Visualizer

### Multi-head self-attention built from the maths up in NumPy — PPMI embeddings, scaled dot-product scores, causal masking, entropy and head-diversity metrics, and ASCII heat maps. Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-013243?style=for-the-badge&logo=numpy&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Attention is easy to *use* (`nn.MultiheadAttention(...)`) and hard to *see*. This project keeps every step visible and inspectable:

1. **Tokenise** four bundled sentences into 26 unique lowercase tokens.
2. **Embed** with a PPMI co-occurrence matrix over a ±2 window, plus a small SHA-256-seeded offset so no token row is all zeros, then L2-normalise.
3. **Project** into per-head query/key spaces and score with `QKᵀ / √d_k`.
4. **Softmax** each row so it becomes a probability distribution over "who I look at".
5. **Measure** what came out: mean row entropy in bits, normalised entropy, and head diversity (`1 − mean pairwise cosine`).
6. **Render** each map as an ASCII heat map, and optionally apply a causal mask.

The projection scale is the one detail that decides whether this project is interesting or useless. With `W ~ N(0, 1/d)` the scores were ~0.1, the softmax was flat, every head was identical, and the heat map rendered as solid `@` — entropy 2.58 bits, the theoretical maximum, and head diversity 0.001. Drawing `W ~ N(0, 2²)` instead gives a score spread of about 4, which produces real structure: entropy 0.91–1.67 bits over four heads and diversity 0.73. The demo now asserts both bounds, so an accidental return to the flat regime fails loudly.

No network, no API keys, no model downloads: the sentences ship in `data/texts.json`.

---

# ✨ Features

- PPMI co-occurrence embeddings with a deterministic offset
- Per-head Q/K/V projections and scaled dot-product attention
- Numerically stable row-wise softmax (max-subtraction, verified against the naive formula)
- Optional causal mask with exact zero weight for future positions
- Entropy, normalised entropy, head diversity, top-attended tokens
- ASCII heat maps in ten intensity levels
- `--demo`, `--texts`, `--sentence`, `--heads`, `--seed`, `--json`
- Strict flag validation before the corpus is read
- 105 passing pytest tests

---

# 📂 Folder Structure

```text
Attention_Visualizer/
│
├── src/
│   ├── main.py        # CLI: --demo, --texts, --sentence, --heads, --json
│   └── attention.py   # embeddings, attention maths, metrics, demo
│
├── tests/
│   └── test_attention.py
│
├── data/
│   └── texts.json     # {"sentences": [{id, text}, ...]}
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 20_Generative_AI_LLMs/Attention_Visualizer

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: embed, attend, measure, render
python src/main.py --demo

# Analyse every sentence in a local store
python src/main.py --texts data/texts.json --heads 4

# One sentence, six heads, exported summary
python src/main.py --texts data/texts.json --sentence s1 --heads 6 \
                   --json run.json
```

**Input:** a JSON object with a `sentences` list; each entry is either a plain string or `{"id": ..., "text": ...}`.

**Exit codes:** `0` = success · `2` = usage/validation/corpus error.

---

# 🧠 How It Works

```text
texts.json ──► sentences ──► tokens (lowercase, [A-Za-z']+)
                                  │
                                  ▼
              window co-occurrence counts (symmetric, ±2)
                                  │
                       PPMI = max(0, ln(p(c,w)/p(c)p(w)))
                                  │
                     + deterministic SHA-256 offset, L2 norm
                                  │
                                  ▼
                     embedding matrix  (V x V, unit rows)
                                  │
              per head h: Q = X Wq, K = X Wk, V = X Wv
                                  │
                  scores = Q K^T / sqrt(d_head)
                                  │
              [optional causal mask: future = -inf]
                                  │
                     softmax rows -> attention map
                                  │
        ┌─────────────────────────┼──────────────────────────┐
        ▼                         ▼                          ▼
  mean row entropy        head diversity            ASCII heat map
  (bits, 0..log2 n)       1 - mean cos             " .:-=+*#%@"
```

Row entropy is `−Σ p log₂ p` averaged over query positions: a one-hot row scores 0 (the model looks at exactly one token), a uniform row scores `log₂ n` (it looks at everything equally). Both extremes are reported honestly.

---

# 🛠 Technologies

- Python 3
- NumPy (`@`, `einsum`-free matmuls, `np.errstate`, `tril`, `argsort`)
- Standard library (`hashlib`, `json`, `math`, `re`, `dataclasses`)
- pytest

No PyTorch, no transformers, no attention library.

---

# 📚 Concepts Covered

- Scaled dot-product attention and the `1/√d_k` temperature
- Multi-head projection and head specialisation
- Row-wise softmax, numerical stability, and the max-subtraction trick
- Causal (decoder) masking with `-inf` before softmax
- Co-occurrence matrices, PMI and positive PMI
- Embedding normalisation and why unit rows bound the score spread
- Attention entropy as a measure of focus vs. diffusion
- Head diversity as cosine distance between flattened maps
- The effect of initialisation scale on whether attention learns anything
- Deterministic feature generation from hashes

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**105 tests passed** covering JSON loading (bad JSON, missing key, empty list, bad entries, duplicate ids, plain strings), tokenisation, vocabulary ordering, co-occurrence symmetry and window effects, PPMI against its formula and all guards, unit-row embeddings and determinism, sinusoidal position encodings (including odd dims), sentence lookup errors, score shapes and width checks, softmax correctness and stability, causal masks, projection shapes and validation, attention row sums, determinism and seed sensitivity, entropy bounds and edge cases, head diversity, top-attended ranking, ASCII rendering, per-sentence analysis, JSON export, demo idempotency, quiet mode, and every CLI error path.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
