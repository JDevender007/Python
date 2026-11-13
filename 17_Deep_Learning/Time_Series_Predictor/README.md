<div align="center">

# 📈 Time Series Predictor

### A PyTorch LSTM next-step forecaster — bundled 1200-point sine series, chronological splits, persistence baseline comparison, and correlation metrics. Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-LSTM-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Time Series Predicts the **next value** of a univariate series with a small LSTM. It loads a local `(t, value)` CSV, standardises it with **train-segment statistics only** (no leakage), cuts a **chronological** 80/20 split — never shuffling, because time order is the signal — builds sliding look-back windows, and trains `LSTM(1 → 32) → Linear(32 → 1)` with Adam and MSE on the scaled values.

The evaluation is deliberately honest: the LSTM's hold-out RMSE/MAE is reported **next to a persistence baseline** (predict the last value in the window — the forecasting equivalent of "tomorrow equals today"). The demo's bundled series (two out-of-phase sinusoids + trend + small noise) is exactly the case where persistence is decent but learnable structure exists: the LSTM wins by ~30 % RMSE with a 0.99 correlation to the actuals.

Everything runs on local files: the bundled **deterministic** sample (1200 points) ships in `data/series.csv`, and `--demo` trains, reports, forecasts the next step, and re-trains to prove determinism. **No network, no dataset downloads, no GPU required.**

---

# ✨ Features

- LSTM next-step regressor with configurable `--window`, `--hidden`, `--epochs`
- Chronological train/hold-out split (no temporal leakage) + z-score from train stats only
- Sliding-window construction with explicit segment validation
- Persistence baseline: RMSE/MAE lift reported alongside the LSTM
- Forecast correlation (Pearson) between predicted and actual hold-out values
- `forecast(recent)` → next-step prediction from the raw tail; `--forecast` CLI flag
- Strict validation: window ≥ 5, enough windows per segment, finite values, ≥ 400 points
- Deterministic: seeded weight init, shuffle, and split
- Bundled deterministic sample: 1200-point dual-sine series with trend
- 43 passing pytest tests

---

# 📂 Folder Structure

```text
Time_Series_Predictor/
│
├── src/
│   ├── main.py      # CLI: --demo, --file, --forecast, --window, --json
│   └── predictor.py # loading, windows, LSTM, training, metrics, demo
│
├── tests/
│   └── test_predictor.py
│
├── data/
│   └── series.csv   # 1200 deterministic points (dual sine + trend)
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 17_Deep_Learning/Time_Series_Predictor

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: train, report, forecast next step, cross-checks
python src/main.py --demo

# Train on your own series with a longer look-back
python src/main.py --file series.csv --window 60 --epochs 50

# Print the next-step forecast and write JSON metrics
python src/main.py --file series.csv --forecast --json metrics.json
```

Input schema (header row required):

```csv
t,value
0,0.5617
1,1.0432
```

(`t` must be unique; values finite; ≥ 400 points with variation.)

**Exit codes:** `0` = success · `2` = usage/schema/config error.

---

# 🧠 How It Works

```text
series.csv ──► validate ──► chronological split (80% train | 20% hold-out)
                                    │
                    z-score using TRAIN mean/std only
                                    │
        ┌───────────────────────────┴──────────────────────────┐
        ▼                                                      ▼
  sliding windows (W=40 → next value)                 hold-out windows
        │                                              (context may
        ▼                                               straddle split)
  LSTM(input=1, hidden=32)
    └─► take last time step ─► Linear(32, 1) ─► next value (scaled)
        │
        ▼  Adam + MSE, 12 epochs, seeded shuffle
  inverse z-score ─► RMSE / MAE vs ACTUAL
                   ─► RMSE / MAE vs PERSISTENCE baseline
                   ─► Pearson correlation
                   ─► forecast(last 40 values) → next point
```

Why persistence is the right baseline: a forecaster that can't beat "copy the last observation" has learned nothing. On the bundled series, one-step persistence error contains the full local slope + noise, giving RMSE ≈ 0.45; the LSTM captures both sinusoids and the trend, dropping RMSE to ≈ 0.31 (−30 %) with correlation 0.99 — the residual is mostly unpredictable noise.

Two leakage guards worth noting: the **z-score uses only pre-split statistics**, and **windows never include future points** (each target's inputs are strictly earlier values). The chronological split mirrors deployment, where you always forecast forward from the end of what you've seen.

---

# 🛠 Technologies

- Python 3
- PyTorch (`nn.LSTM`, `nn.Linear`, `MSELoss`, `Adam`, seeded RNG)
- pandas / numpy (loading, validation, metrics, correlation)
- argparse / json / logging / dataclasses
- pytest

---

# 📚 Concepts Covered

- Sequence-to-one forecasting with sliding windows
- Why time series must be split chronologically (and never shuffled)
- Train-only scaling to avoid leakage
- The persistence baseline and what "beating it" proves
- LSTM cell outputs vs the last hidden state
- Z-score standardisation for recurrent networks
- RMSE vs MAE and what their gap reveals
- Pearson correlation as a phase-tracking metric
- Deterministic recurrent training with seeded generators
- Forecast API design (raw recent values in, original units out)

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**43 tests passed** covering every validation rule (schema, finiteness, duplicate timestamps, minimum length, constant series, window/hyperparameter bounds), window-construction math, seeded model equality, training metrics and split arithmetic, determinism and seed sensitivity, forecast edge cases (wrong length, NaN), report sections, demo idempotency, and every CLI path — all offline.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
