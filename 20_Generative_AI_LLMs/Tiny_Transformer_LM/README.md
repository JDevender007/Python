<div align="center">

# 🤖 Tiny Transformer LM

### A character-level mini-GPT (causal self-attention, learned positional embeddings, AdamW) trained on a bundled corpus — 150 steps in about 15 seconds, fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Tiny Transformer LM is a **decoder-only Transformer** (the GPT architecture) written from its components rather than imported wholesale:

- Token + learned positional embeddings
- Masked multi-head self-attention with an explicit causal `torch.tril` mask
- Pre-LayerNorm residual blocks with an MLP (`Linear → GELU → Linear`)
- Weight-tied output head over the character vocabulary
- Cross-entropy next-character objective, AdamW, random block sampling

Training is deliberately small — `d_model=64`, 2 heads, 2 layers, 150 steps — so the whole demo runs offline in seconds on CPU and the loss curve is visible in the output. Sampling supports temperature scaling and top-k truncation with a seeded `torch.Generator`, so generated text is reproducible.

No network, no tokenizers, no pretrained weights: the corpus ships in `data/corpus.txt`.

---

# ✨ Features

- Hand-built causal self-attention (no `nn.MultiheadAttention`)
- Learned positional embeddings, pre-LN residual blocks, tied head
- Character tokenizer that rejects out-of-vocabulary characters loudly
- Temperature and top-k sampling with deterministic seeds
- Ready-made training report (head/tail loss, final drop)
- `--demo`, `--file`, `--prompt`, `--length`, `--steps`, `--json` CLI
- Strict flag validation before the corpus is loaded
- 57 passing pytest tests

---

# 📂 Folder Structure

```text
Tiny_Transformer_LM/
│
├── src/
│   ├── main.py   # CLI: --demo, --file, --prompt, --length, --json
│   └── lm.py     # tokenizer, attention, GPT, training, sampling, demo
│
├── tests/
│   └── test_lm.py
│
├── data/
│   └── corpus.txt
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 20_Generative_AI_LLMs/Tiny_Transformer_LM

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: train on the bundled corpus and sample from a prompt
python src/main.py --demo

# Train on your own text
python src/main.py --file mytext.txt --steps 300

# Sample from a prompt
python src/main.py --prompt "The " --length 200 --temperature 0.8 --top-k 10

# Machine-readable run summary
python src/main.py --file data/corpus.txt --prompt "The " --json run.json
```

**Input:** a plain-text corpus of at least 500 characters, longer than `block_size`.

**Exit codes:** `0` = success · `2` = usage/validation/corpus error.

---

# 🧠 How It Works

```text
corpus.txt ──► char vocabulary (sorted set of characters)
                    │
                    ▼
   random blocks of block_size chars ──► x (inputs), y (next char)
                    │
                    ▼
   token embedding + positional embedding
                    │
        ┌───────────┴────────────┐
        ▼                        ▼
  masked self-attention     residual + LayerNorm
  (causal tril mask)             │
        └───────────┬────────────┘
                    ▼
              MLP (GELU)
                    ▼
        Linear -> vocab logits -> cross-entropy
                    │
                    ▼
             AdamW, 150 steps

sample: prompt ──► logits / temperature ──► top-k truncate ──► softmax
        ──► multinomial(seeded generator) ──► append ──► repeat
```

The causal mask is the critical piece: attention scores are filled with `-inf` above the diagonal before softmax, so position *t* can only attend to positions ≤ *t*. Without it the model would trivially copy the answer from the future and the loss would collapse to zero while generating nonsense.

---

# 🛠 Technologies

- Python 3
- PyTorch (tensors, autograd, `nn.Module`, AdamW)
- NumPy (corpus statistics)
- argparse / json / math / logging
- pytest

---

# 📚 Concepts Covered

- Decoder-only Transformer (GPT) architecture
- Scaled dot-product attention and causal masking
- Multi-head splitting and reshaping
- Learned positional embeddings
- Pre-LayerNorm residual blocks
- Weight tying between embedding and output head
- Cross-entropy over a character vocabulary
- Temperature and top-k sampling
- Deterministic generation with seeded generators
- Training-loop engineering for CPU-sized demos

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**57 tests passed** covering corpus loading and size validation, tokenizer round-trips / unknown characters / unknown ids, model shape and parameter checks, causal masking, loss decrease on a repetitive corpus, training determinism and seed sensitivity, every hyperparameter validation, prompt length limits, sampling length/temperature/top-k behaviour, sampling determinism, report rendering, JSON export, demo idempotency, quiet mode, and all CLI error paths.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
