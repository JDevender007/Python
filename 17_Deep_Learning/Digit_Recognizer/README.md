<div align="center">

# ✍️ Digit Recognizer

### A PyTorch MLP classifying 8×8 handwritten digits — bundled 1797-image dataset, confusion matrix, per-class metrics, and ASCII previews of test digits. Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-Classification-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Digit Recognizer trains a small fully-connected network (**64 → 128 → 64 → 10**, ReLU hidden layers, softmax output) to classify 8×8 grayscale handwritten digits. The dataset is sklearn's classic `load_digits` (1797 images, 64 pixel columns, values 0–16) **exported to a local CSV** — nothing is downloaded at runtime; the images come from `data/digits.csv`.

The report shows the learning curve, hold-out accuracy, a full **10×10 confusion matrix**, per-class precision/recall with support bars, and an **ASCII rendering** of a classified test digit (the 8×8 pixel grid mapped onto a shade ramp ` .:-=+*#%@`). `--predict` classifies a single image given as 64 comma-separated pixel values.

Training is fully reproducible: seeded weight initialisation, a seeded shuffle generator, stratified splits, and CPU-only deterministic ops. The loader validates every pixel column (0–16 greyscale), integer labels 0–9, ≥ 100 rows, and ≥ 5 samples per class. The demo trains 12 epochs (~0.94 hold-out accuracy), asserts every class recall stays above 0.6, and re-trains to prove determinism. **No network, no dataset downloads, no GPU required.**

---

# ✨ Features

- PyTorch `DigitNet`: configurable hidden layers (`(128, 64)` default), ReLU, softmax
- Adam + cross-entropy with per-epoch train/hold-out accuracy tracking
- Stratified 75/25 split; confusion matrix + per-class precision/recall/support
- `predict(pixels)` → `(label, confidence)` for a single 64-value image
- ASCII art renderer for any 8×8 image (no image libraries needed)
- Strict validation: pixel ranges, integer labels, all 10 classes, minimums
- `--predict "0,0,5,..."` with bundled-data fallback; JSON metrics export
- Deterministic: seeded init, shuffle, and split — identical results every run
- Bundled dataset: 1797 images from sklearn's `load_digits`, stored as CSV
- 50 passing pytest tests

---

# 📂 Folder Structure

```text
Digit_Recognizer/
│
├── src/
│   ├── main.py    # CLI: --demo, --file, --predict, --epochs, --json
│   └── digits.py  # loading, DigitNet, training, metrics, ASCII, demo
│
├── tests/
│   └── test_digits.py
│
├── data/
│   └── digits.csv # 1797 images x 64 pixels (0..16) + label 0..9
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 17_Deep_Learning/Digit_Recognizer

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: train, confusion matrix, ASCII preview, cross-checks
python src/main.py --demo

# Train on your own digits CSV
python src/main.py --file digits.csv --epochs 30

# Classify one 8x8 image (64 pixel values 0..16)
python src/main.py --predict "0,0,5,12,15,12,4,0,...,0"

# Metrics as JSON
python src/main.py --file digits.csv --json metrics.json
```

Input schema (header row required):

```csv
pixel_0,pixel_1,...,pixel_63,label
0,0,5,13,15,12,4,0,...,0,8
```

(`label` is 0–9; ≥ 100 rows, ≥ 5 per class; pixels are integers 0–16.)

**Exit codes:** `0` = success · `2` = usage/schema/prediction error.

---

# 🧠 How It Works

```text
data/digits.csv ──► validate (pixels 0..16, labels 0..9, all classes)
                          │
                          ▼  stratified 75 / 25 split
        x_train (/16 → [0,1])            x_test (sealed)
                          │
                          ▼
        Linear 64→128 → ReLU → Linear 128→64 → ReLU → Linear 64→10
                          │
              Adam (lr 1e-3) + CrossEntropyLoss, batches of 64
                          │
                          ▼
     hold-out: argmax(softmax) ──► accuracy, 10×10 confusion,
                                   per-class precision/recall,
                                   misclassified list, ASCII preview
```

Details worth knowing:

- **Pixels scaled to [0, 1]** (`/16`) before the first linear layer — gradient-friendly inputs.
- **Cross-entropy works on logits directly** — no softmax in the network's last layer during training (`softmax` is applied only when reporting confidence), which is the numerically stable formulation.
- **The confusion matrix is built by hand** from hold-out predictions, so the demo can assert that it sums to exactly `ceil(0.25 · n)` — every hold-out row is accounted for.
- Typical result after 12 epochs: **~0.94 hold-out accuracy**, with the classic confusions (1↔8, 4↔9) visible in the matrix — exactly the errors a human makes on 8×8 scribbles.

---

# 🛠 Technologies

- Python 3
- PyTorch (`nn.Sequential`, `CrossEntropyLoss`, `Adam`, seeded RNG)
- pandas / numpy (loading, validation, confusion matrices)
- argparse / json / logging / dataclasses
- pytest

---

# 📚 Concepts Covered

- Flattening image tensors into feature vectors
- Multiclass classification with 10-way softmax + cross-entropy
- Why training uses logits (numerical stability) and reporting uses softmax
- Stratified splitting across 10 classes
- Reading a confusion matrix and per-class precision/recall
- Reproducibility: seeding weight init, shuffling, and splits
- Confidence calibration from softmax outputs
- ASCII rendering of raster data (no image dependencies)
- Hold-out discipline and per-class failure analysis

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**50 tests passed** covering every validation rule (pixel ranges, labels, class minimums, row counts), seeded initialisation equality, tensor scaling, training metrics, confusion/support arithmetic, misclassified-count consistency, determinism and seed sensitivity, prediction edge cases (wrong length, out of range, NaN), ASCII rendering shape, parsing helpers, demo idempotency, and every CLI path — all offline. Extra cases pin tensor shapes/dtypes, unit-interval scaling, every class present in the labels, and `parse_pixels()` returning floats.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
