<div align="center">

# 🌊 Motion Analyzer

### Frame differencing and a running-average background model implemented in pure NumPy, with from-scratch morphology, motion statistics and ASCII overlays. Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-From%20Scratch-013243?style=for-the-badge&logo=numpy&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Motion Analyzer answers a deceptively simple question — *which pixels moved?* — two different ways:

- **Frame differencing** compares each frame with its predecessor. It is simple and fast, but blind to anything present since frame 0 and only sees the *edges* of a slowly moving object.
- **Background subtraction** learns a background model from the first `--warmup` frames and flags anything that differs. It sees the object in every frame, but the model is causal: objects that appear later do **not** leave ghosts in the past.

A from-scratch 3×3 `erode`/`dilate` pair (NumPy shifted views) cleans speckle noise via opening-then-closing. The bundled 20-frame sequence includes a moving square, a static bright box (which must be ignored) and a new object that appears at frame 10 (which must only be detected after it arrives). The demo asserts every one of those behaviours.

---

# ✨ Features

- Frame differencing with a configurable brightness threshold
- Exponential moving-average background learned from a warm-up prefix
- `erode` / `dilate` / `clean_mask` with a square structuring element, no OpenCV morphology
- Motion stats: active frames, pixel counts/ratio, bounding box, centroid
- ASCII overlay of the last frame's mask
- `--method diff|background|all`, `--threshold`, `--alpha`, `--warmup`, JSON export
- Strict flag validation before decoding frames
- 62 passing pytest tests

---

# 📂 Folder Structure

```text
Motion_Analyzer/
│
├── src/
│   ├── main.py    # CLI: --demo, --frames, --method, --threshold, --json
│   └── motion.py  # sequence, detectors, morphology, stats, demo
│
├── tests/
│   └── test_motion.py
│
├── data/
│   ├── frames/
│   │   ├── frame_00.png ... frame_19.png
│   └── truth.csv  # frame,cx,cy,half,new_x,new_y
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 18_Computer_Vision/Motion_Analyzer

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo over the bundled 20-frame sequence
python src/main.py --demo

# Analyse any folder of grayscale frame_*.png files
python src/main.py --frames data/frames
python src/main.py --frames data/frames --method diff --threshold 20
python src/main.py --frames data/frames --warmup 5 --json report.json
```

**Input schema:** a directory of `frame_00.png`, `frame_01.png`, … (grayscale or colour; colour is read as grayscale). Optional `truth.csv` next to the frames for reference.

**Exit codes:** `0` = success · `2` = usage/validation/decode error.

---

# 🧠 How It Works

```text
frame_t-1, frame_t ──► |frame_t - frame_t-1| > threshold ──► diff mask
                                                             (edges only)

frames[0:warmup] ──► background model (EMA, alpha)
                              │
frame_t ──► |frame_t - background| > threshold ──► raw mask
                              │
                     erode(1) ──► dilate(1)   (opening: kill speckles)
                              │
                     dilate(1) ──► erode(1)   (closing: fill pinholes)
                              ▼
              stats: pixels, ratio, bbox, centroid, ASCII overlay
```

The trade-off between the two detectors is the interesting part. Differencing gives ~144 px per frame — just two thin strips where the moved square entered and left — so its coverage check uses a looser threshold. Background subtraction recovers the whole 12×12 object, but only because the model was learned **before** the object arrived; computing the model over the full sequence would flag the new object in every earlier frame (a ghost artifact), which is why `warmup` exists and is asserted in the demo.

---

# 🛠 Technologies

- Python 3
- NumPy (differences, EMA, shifted-view morphology, statistics)
- OpenCV (PNG decoding + procedural drawing only)
- argparse / csv / json / logging
- pytest

---

# 📚 Concepts Covered

- Temporal differencing and its blind spots
- Exponential moving-average background models
- Causal vs global background estimation and ghost artifacts
- Threshold selection and illumination drift
- Morphological opening/closing as noise removal
- Motion statistics: pixel counts, bounding boxes, centroids
- ASCII visualisation of binary masks
- Deterministic synthetic video for repeatable tests

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**62 tests passed** covering generator determinism, truth CSV integrity, the static object's constant brightness, bundle/load round-trips, differencing thresholds and shape checks, background EMA alpha validation, mask construction, morphology iteration rules and 3-D rejection, speckle removal, motion statistics, every analyse method, warm-up validation, the new-object gating behaviour, ASCII width, JSON export, demo idempotency, quiet mode, and all CLI error paths.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
