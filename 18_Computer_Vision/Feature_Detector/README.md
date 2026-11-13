<div align="center">

# 🎯 Feature Detector

### Harris corner detection implemented from scratch in NumPy plus ORB keypoint matching with Lowe's ratio test — recovering a known image translation from keypoints. Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-ORB-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Feature detectors find the points in an image that are *distinctive* — the ones a tracker or stitcher can lock onto. This project builds **Harris corner detection from scratch**: gradient images, the structure tensor `M = [[ΣIx², ΣIxIy], [ΣIxIy, ΣIy²]]` smoothed with a from-scratch integral-image box filter, and the response `R = det(M) − k·tr(M)²`, followed by 3×3 local-maximum suppression and greedy plateau suppression.

It then pairs that with **ORB** (via OpenCV) on two views of the same scene separated by a known translation `(17, 9)`, using a Hamming `BFMatcher` with Lowe's ratio test, and reports the median displacement recovered from the matches. The demo asserts the nine checkerboard intersections land within 2 px of their analytic positions and that the recovered shift matches the truth.

Everything is offline: three procedural PNGs ship in `data/` and are verified against their generator on every demo run.

---

# ✨ Features

- Harris response from a hand-built structure tensor (integral-image box filter, no library smoothing)
- 3×3 non-maximum suppression **plus** greedy `min_distance` suppression for flat response plateaus
- ORB keypoints/descriptors with configurable feature budget
- BFMatcher Hamming kNN + Lowe ratio test
- Median/mean displacement report from matches
- `--mode harris|orb|all`, `--compare` for the second image, JSON export
- Strict flag validation before any image is decoded
- 64 passing pytest tests

---

# 📂 Folder Structure

```text
Feature_Detector/
│
├── src/
│   ├── main.py      # CLI: --demo, --file, --compare, --mode, --json
│   └── features.py  # samples, Harris, ORB, matching, reports, demo
│
├── tests/
│   └── test_features.py
│
├── data/
│   ├── checkerboard.png # 128x128, 32 px squares -> 9 interior corners
│   ├── scene_a.png      # 180x140 procedural scene
│   └── scene_b.png      # same scene shifted by (17, 9)
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 18_Computer_Vision/Feature_Detector

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: corner grid, brightness invariance, ORB shift recovery
python src/main.py --demo

# Harris corners on your own image
python src/main.py --file photo.png --threshold 5e-5

# Match two views
python src/main.py --file a.png --compare b.png --mode all --json report.json
```

**Input:** local PNG/JPG images. `--compare` is required for `--mode orb` and `--mode all`.

**Exit codes:** `0` = success · `2` = usage/validation/decode error.

---

# 🧠 How It Works

```text
image.png ──► grayscale
                 │
                 ▼
        central-difference gradients (Ix, Iy)
                 │
                 ▼
    box_filter(Ix²), box_filter(Iy²), box_filter(IxIy)
                 │  (integral image -> O(1) per window)
                 ▼
        R = det(M) - k * trace(M)^2
                 │
                 ▼
    3x3 local maximum + greedy min-distance + threshold
                 │
                 ▼
            corner list (y, x, R)

scene_a.png ──► ORB detect+compute ──┐
                                     ├──► Hamming kNN ──► ratio test
scene_b.png ──► ORB detect+compute ──┘         │
                                               ▼
                             median (dx, dy) of matched keypoints
```

Two implementation details matter. First, the box filter uses a summed-area table, so smoothing costs the same for a 3×3 or 15×15 window. Second, hard-edged synthetic images produce **response plateaus** — four adjacent pixels with identical `R` — so 3×3 NMS alone returns four corners per intersection; the greedy `min_distance` pass fixes this and is what makes the checkerboard assertion exact (9, not 32).

---

# 🛠 Technologies

- Python 3
- NumPy (gradients, structure tensor, integral images, matching statistics)
- OpenCV (PNG decoding, ORB, BFMatcher)
- argparse / json / logging
- pytest

---

# 📚 Concepts Covered

- Structure tensor and the Harris corner criterion
- Integral images (summed-area tables) for O(1) box filtering
- Non-maximum suppression and greedy distance suppression
- Brightness invariance of gradient-based detectors
- ORB: FAST keypoints + BRIEF descriptors
- Hamming distance and kNN matching
- Lowe's ratio test for rejecting ambiguous matches
- Recovering translation from matched point pairs
- Deterministic procedural test imagery

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**64 tests passed** covering sample determinism, the exact (17, 9) scene shift, box-filter correctness and validation, Harris response shape/positivity/flat regions/brightness invariance, the 9-corner checkerboard result, response ordering, `max_corners` and threshold limits, plateau suppression, ORB budgets and empty-descriptor paths, ratio-test validation, displacement statistics, every analyse mode, ASCII width, JSON export, demo idempotency, quiet mode, and all CLI error paths.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
