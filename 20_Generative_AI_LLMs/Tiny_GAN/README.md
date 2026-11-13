<div align="center">

# 🌙 Tiny GAN

### A generative adversarial network in ~90 lines of PyTorch — MLP generator vs MLP discriminator on the classic two-moons dataset, trained on CPU in about 15 seconds. Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Two moons is the smallest dataset where a GAN can visibly succeed or visibly fail. The generator maps 8-dimensional Gaussian noise through `Linear → ReLU → Linear → ReLU → Linear` to a 2-D point; the discriminator scores points with `Linear → LeakyReLU(0.2) → Linear → LeakyReLU(0.2) → Linear`. Both use Adam (`betas=(0.5, 0.999)`, the standard GAN setting), BCE-with-logits, and alternating updates — one discriminator step on real+fake, one generator step on fake-only.

Training is fixed at **800 steps of batch 128**. That number is not arbitrary: at 400 steps the generator is still producing one inflated blob between the moons — coverage 44% of real points, mode balance 35/65. Doubling the steps takes coverage to **95.5%**, pulls the mean nearest-neighbour distance to **0.088** standardised units, and balances the moons at 50/50. The demo asserts all three metrics, so a regression in training quality fails the build instead of silently shipping a blob.

Every design choice is measured rather than assumed, and everything is seeded — two runs with the same seed produce identical loss curves down to the float.

No network, no API keys, no downloads: the 2000-row dataset ships in `data/moons.csv`.

---

# ✨ Features

- Hand-written GAN loop (no `torchgan`, no Lightning)
- LeakyReLU discriminator, ReLU generator, BCE-with-logits
- Per-feature standardisation with a zero-variance guard
- Three independent quality metrics: coverage, nearest-real distance, mode balance
- Deterministic training and sampling via seeded generators
- `--demo`, `--data`, `--steps`, `--batch-size`, `--latent`, `--seed`, `--json`
- Strict flag validation before the dataset is read
- 67 passing pytest tests

---

# 📂 Folder Structure

```text
Tiny_GAN/
│
├── src/
│   ├── main.py  # CLI: --demo, --data, --steps, --json
│   └── gan.py   # dataset, models, training loop, metrics, demo
│
├── tests/
│   └── test_gan.py
│
├── data/
│   └── moons.csv   # 2000 rows: x,y,label
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 20_Generative_AI_LLMs/Tiny_GAN

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: train 800 steps, then score the generated cloud
python src/main.py --demo

# Train on your own CSV (columns: x,y,label) and print metrics
python src/main.py --data data/moons.csv --steps 1200 --seed 3

# Export the run summary
python src/main.py --data data/moons.csv --steps 200 --json run.json
```

**Input:** a CSV with columns `x`, `y`, `label` and at least 200 rows.

**Exit codes:** `0` = success · `2` = usage/validation/dataset error.

---

# 🧠 How It Works

```text
moons.csv ──► standardise (zero mean, unit variance)
                    │
        ┌───────────┴────────────┐
        ▼                        ▼
   real batch (128)        noise z ~ N(0, I)  (128 x 8)
        │                        │
        │                        ▼
        │                   Generator  (8 -> 64 -> 64 -> 2)
        │                        │
        └──────────┬─────────────┘
                   ▼
            Discriminator (2 -> 64 -> 64 -> 1)
                   │
        ┌──────────┴───────────┐
        ▼                      ▼
  D loss: real->1, fake->0   G loss: fake->1
  (one Adam step)            (one Adam step)
                   │
                   ▼  800 iterations
        ┌──────────────────────────────────┐
        ▼                                  ▼
 coverage(real, fake)             mode_balance via
 % real points with a             nearest real point
 fake within 0.35                  -> moon0 / moon1
```

The two networks are locked in the minimax game

```text
min_G max_D  E[log D(x)] + E[log(1 - D(G(z)))]
```

implemented in the numerically stable form: `BCEWithLogitsLoss` folds the sigmoid into the loss, so no `log(0)` ever appears.

---

# 🛠 Technologies

- Python 3
- PyTorch (`nn.Module`, autograd, Adam, `torch.cdist`)
- Standard library (`csv`, `math`, `json`, `dataclasses`)
- pytest

---

# 📚 Concepts Covered

- Generative adversarial networks and the minimax objective
- Generator/discriminator architecture choices (ReLU vs LeakyReLU)
- BCE-with-logits and why it replaces sigmoid + BCE
- Adam with `beta1 = 0.5` for GAN stability
- Alternating optimisation and detaching fake samples in the D step
- Mode collapse and how to detect it quantitatively
- Coverage and nearest-neighbour metrics for generative models
- Feature standardisation and zero-variance handling
- Reproducibility with seeded `torch.Generator`
- Recognising under-training: 400 steps → 44% coverage, 800 → 95.5%

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**67 tests passed** covering CSV loading (missing columns, non-numeric, non-finite, bad labels, undersized data), standardisation correctness and edge cases, generator/discriminator shapes and validation, training history length and finiteness, training determinism and seed sensitivity, batch/step/lr guards, sampling shape and reproducibility, coverage and nearest-distance properties, mode-balance arithmetic, JSON serialisation, demo idempotency, quiet mode, and every CLI error path.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
