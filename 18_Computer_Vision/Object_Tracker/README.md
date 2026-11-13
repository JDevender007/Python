<div align="center">

# 🎥 Object Tracker

### Colour-blob centroid tracking across a 24-frame synthetic video — thresholding, centroid extraction, nearest-neighbour association and ground-truth error reporting. Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-Frames-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Object Tracker follows two coloured balls across a procedurally generated 24-frame sequence. Each frame is thresholded in RGB space to produce a boolean mask per colour, the centroid is computed from the mask coordinates, and detections are accepted only if they are within `--max-jump` pixels of the previous position — a simple, honest association rule that rejects spurious blobs.

The sequence ships as 24 PNGs plus `truth.csv`, and the demo verifies **every frame against its generator**, then asserts the tracked centroids stay within 1.5 px of the analytic ground truth, that the red ball moves left→right while blue moves right→left, that the blob area approximates `πr²`, and that repeated runs are identical.

No video codec, no camera, no network — just PNG frames and NumPy.

---

# ✨ Features

- Deterministic procedural sequence (gradient background + noise, two moving discs)
- RGB range thresholding per colour
- Centroid from mask coordinates (no library moments call)
- Nearest-neighbour association with configurable `--max-jump`
- Per-colour coverage, path length, mean/max step, start/end points
- Ground-truth CSV comparison (max/mean pixel error)
- ASCII trajectory map, single-colour mode, JSON export
- 51 passing pytest tests

---

# 📂 Folder Structure

```text
Object_Tracker/
│
├── src/
│   ├── main.py     # CLI: --demo, --frames, --colour, --json
│   └── tracker.py  # sequence generation, detection, tracking, demo
│
├── tests/
│   └── test_tracker.py
│
├── data/
│   ├── frames/
│   │   ├── frame_00.png ... frame_23.png
│   └── truth.csv   # frame,red_x,red_y,blue_x,blue_y
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 18_Computer_Vision/Object_Tracker

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo over the bundled sequence
python src/main.py --demo

# Track any folder of frame_*.png files
python src/main.py --frames data/frames
python src/main.py --frames data/frames --colour red --json report.json
```

**Input schema:** a directory containing `frame_00.png`, `frame_01.png`, … (RGB-visible coloured objects). Optional `truth.csv` with columns `frame,red_x,red_y,blue_x,blue_y` next to the frames enables error reporting.

**Exit codes:** `0` = success · `2` = usage/validation/decode error.

---

# 🧠 How It Works

```text
frame_XX.png ──► RGB array
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
  mask(red)                mask(blue)
  R>=150,G<=90,B<=90       B>=150,R<=90,G<=90
        │                       │
        ▼                       ▼
  centroid = mean(xs,ys)   centroid = mean(xs,ys)
        │                       │
        └───────────┬───────────┘
                    ▼
      association: reject if jump > MAX_JUMP
                    ▼
   stats: coverage, path length, mean step, start/end
                    ▼
        compare with truth.csv -> max/mean error
```

The centroid of a filled disc is exact, so any deviation from truth comes from two effects: integer pixel quantisation (~0.5 px) and clipping at the frame edge — which is why the generator keeps both balls at least one radius away from every border. That detail is worth 2+ px of measured error and was caught by the demo's own assertion.

---

# 🛠 Technologies

- Python 3
- NumPy (masking, centroids, trajectory metrics)
- OpenCV (PNG decoding, procedural drawing)
- argparse / csv / json / logging
- pytest

---

# 📚 Concepts Covered

- Colour-space thresholding and boolean masks
- Centroid estimation from pixel coordinates
- Frame-to-frame association and gating (`max_jump`)
- Tracking metrics: coverage, path length, mean step
- Ground-truth evaluation with max/mean pixel error
- Frame-edge clipping and its effect on centroids
- Deterministic synthetic video generation
- ASCII visualisation of trajectories

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**51 tests passed** covering generator determinism, truth CSV integrity, balls staying in-frame, opposite travel directions, bundle/load round-trips, missing/empty directories, mask validation for unknown colours and non-RGB frames, centroid maths, detection accuracy, blob area, jump rejection, path statistics, truth comparison, ASCII width, JSON export, demo idempotency, quiet mode, and every CLI error path.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
