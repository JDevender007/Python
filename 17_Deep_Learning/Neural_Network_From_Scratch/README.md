<div align="center">

# 🧠 Neural Network From Scratch

### A pure-NumPy multilayer perceptron — forward propagation, hand-derived backprop, mini-batch gradient descent, and a gradient check that proves the math. Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-from%20scratch-FCC624?style=for-the-badge&logo=numpy&logoColor=black)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Neural Network From Scratch implements a fully-connected binary classifier with **no deep-learning framework** — just NumPy matrix multiplication. You get explicit `forward`, `gradients` (backpropagation), and `fit` (mini-batch gradient descent) implementations, He/Xavier weight initialisation, ReLU/tanh hidden layers, a sigmoid output trained with binary cross-entropy, and per-epoch learning curves for both the training split and a sealed hold-out.

The bundled dataset is **concentric circles**: two classes arranged as an inner disk and an outer ring. No straight line can separate them, so a logistic-regression-style model fails — and a hidden-layer network succeeds. That makes the demo's "lift over majority baseline" (+0.500) a genuine demonstration of non-linear feature learning rather than a trivial win.

Because the backprop is hand-derived, the project ships a **gradient checker**: it compares every analytic derivative against central-difference numerical differentiation (`(f(x+ε) − f(x−ε)) / 2ε`). The demo asserts the maximum relative error is below `1e-6` — measured at ~3×10⁻¹⁰. If a sign or transpose were wrong anywhere, this catches it.

Everything runs on local files: the bundled **deterministic** sample (600 rows, balanced 300/300) ships in `data/`, and `--demo` trains, reports, gradient-checks, and re-trains to prove determinism. **No network, no downloads, no framework.**

---

# ✨ Features

- Pure NumPy MLP: `forward`, `gradients` (backprop), `fit` (mini-batch GD)
- Configurable architecture via `--layers 32,16`; ReLU or tanh hidden units
- He initialisation for ReLU, Xavier for tanh — seeded and deterministic
- Numerically stable sigmoid and BCE (epsilon-clamped logs)
- Gradient checker: analytic vs central-difference, max relative error reported
- Learning curves: train loss/accuracy **and** hold-out loss/accuracy per epoch
- Hold-out evaluation against a majority-class baseline (honest "lift")
- Strict validation: layer sizes, learning rate, epochs, batch size, data schema
- JSON export of params + metrics; deterministic across runs
- Bundled deterministic sample: 600 concentric-circle rows (300/300)
- 41 passing pytest tests

---

# 📂 Folder Structure

```text
Neural_Network_From_Scratch/
│
├── src/
│   ├── main.py   # CLI: --demo, --file, --layers, --epochs, --lr, --json
│   └── mlp.py    # activations, MLP, gradient check, training, report, demo
│
├── tests/
│   └── test_mlp.py
│
├── data/
│   └── dataset.csv   # 600 deterministic rows (concentric circles)
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 17_Deep_Learning/Neural_Network_From_Scratch

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

(Only NumPy is required — no PyTorch, no TensorFlow.)

---

# ▶️ Run

```bash
# Offline demo: train 2->16->16->1 on circles, gradient check, cross-checks
python src/main.py --demo

# Train on your own CSV with a custom architecture
python src/main.py --file dataset.csv --layers 32,16 --epochs 500

# Tune the optimiser and export metrics
python src/main.py --file dataset.csv --lr 0.05 --batch 16 \
    --json metrics.json
```

Input schema (header row required):

```csv
x1,x2,label
0.8421,-1.2034,1
```

(`label` is `0` or `1`; ≥ 50 rows, ≥ 10 per class.)

**Exit codes:** `0` = success · `2` = usage/schema/config error.

---

# 🧠 How It Works

```text
        x (m×2)
         │
    z₁ = W₁x + b₁  ──►  a₁ = ReLU(z₁)      W₁: 16×2  (He init)
         │
    z₂ = W₂a₁ + b₂ ──►  a₂ = ReLU(z₂)      W₂: 16×16
         │
    z₃ = W₃a₂ + b₃ ──►  ŷ = σ(z₃)           W₃: 1×16  (Xavier)
         │
    BCE(y, ŷ) = −[y log ŷ + (1−y) log(1−ŷ)]
         │
    ∂L/∂z₃ = (ŷ − y)/m          ← sigmoid + BCE cancel
    ∂L/∂W₃ = ∂L/∂z₃ · a₂ᵀ
    ∂L/∂z₂ = (W₃ᵀ ∂L/∂z₃) ⊙ 1[z₂ > 0]       ← ReLU derivative
    ... and so on back through the layers
         │
    W ← W − lr · ∂L/∂W          (mini-batch, shuffled each epoch)
```

The gradient checker validates every one of those derivatives numerically:

```text
numeric_i  = (L(θᵢ + ε) − L(θᵢ − ε)) / 2ε        ε = 1e-5
relative_i = |numeric_i − analytic_i| / max(|numeric_i|, |analytic_i|, 1e-8)
max relative error  ≈ 3e-10   ✓  (threshold 1e-6)
```

Why circles are the right demo: with inputs (x, y) only, the optimal boundary is `x² + y² = r²` — a circle. A linear model's boundary is `wx + b = 0` — a line — which cannot cut out a disk. The MLP learns curved decision boundaries by composing ReLUs, which is exactly what the hold-out accuracy (1.000 vs 0.500 baseline) demonstrates.

---

# 🛠 Technologies

- Python 3
- NumPy (matrix ops, RNG, vectorised activations)
- pandas (CSV loading, validation, stratified splitting)
- argparse / json / logging / dataclasses
- pytest

---

# 📚 Concepts Covered

- Forward propagation as a sequence of affine + non-linear maps
- Hand-derived backpropagation (chain rule layer by layer)
- Sigmoid + binary cross-entropy gradient cancellation
- ReLU derivative and the vanishing-gradient contrast with sigmoid
- He vs Xavier initialisation and why they differ
- Mini-batch gradient descent with per-epoch shuffling
- Numerical gradient checking (central differences) as a correctness proof
- Train/hold-out discipline and majority-class baselines
- Learning curves as a diagnostic (loss vs accuracy vs validation)
- Numerical stability (clamped exponentials, epsilon-guarded logs)
- Deterministic training with seeded RNG

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**41 tests passed** covering activation maths, every config and data validation rule, gradient checks on two architectures (the core correctness proof), loss reduction, baseline lift, determinism and seed-sensitivity, split arithmetic, learning-curve length, `to_dict` JSON safety, report sections, demo idempotency, and every CLI path — all offline.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
