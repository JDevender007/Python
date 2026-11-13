<div align="center">

# 🧩 Image Segmentation

### Otsu thresholding, k-means colour clustering, and connected-component labelling implemented from scratch in NumPy — with OpenCV cross-checks. Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-Cross--check-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Image Segmentation splits an image into meaningful regions without any pre-trained model. It implements three classic algorithms **from first principles**:

1. **Otsu thresholding** — searches all 256 grey levels for the split that maximises between-class variance (`σ²_B = ω₀ω₁(μ₀−μ₁)²`), using cumulative sums over the histogram.
2. **k-means clustering** — seeded k-means++ initialisation, vectorised assignment/update over pixel colours, inertia (SSE) and iteration count reported.
3. **Connected components** — explicit BFS stack labelling with 4- or 8-connectivity, region sizes sorted descending.

OpenCV is used only to decode PNGs and to **verify** the from-scratch results: the demo asserts the Otsu threshold equals `cv2.THRESH_OTSU` exactly and the component count equals `cv2.connectedComponents - 1`. Everything ships with deterministic procedural samples in `data/` — no network, no downloads, no keys.

---

# ✨ Features

- Otsu threshold computed from the 256-bin histogram (no library call)
- k-means++ seeding, vectorised distance/update steps, inertia + convergence report
- BFS connected components with 4/8-connectivity and region statistics
- ASCII preview of any mask, downsampled to a fixed 48 columns
- `--mode otsu|kmeans|components|all` and JSON metric export
- Strict validation: cluster range 2–8, connectivity ∈ {4, 8}, threshold 0–255
- Deterministic: same seed → identical labels and centres
- 61 passing pytest tests

---

# 📂 Folder Structure

```text
Image_Segmentation/
│
├── src/
│   ├── main.py         # CLI: --demo, --file, --mode, --clusters, --json
│   └── segmentation.py # Otsu, k-means, components, reports, demo
│
├── tests/
│   └── test_segmentation.py
│
├── data/
│   ├── otsu_shapes.png   # 160x160 procedural shapes
│   ├── components.png    # 128x128 disjoint blobs
│   └── color_blocks.png  # 160x160 noisy colour blocks
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 18_Computer_Vision/Image_Segmentation

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: Otsu vs cv2, components vs cv2, k-means determinism
python src/main.py --demo

# Segment your own image
python src/main.py --file photo.png --mode otsu
python src/main.py --file photo.png --mode kmeans --clusters 5
python src/main.py --file mask.png --mode components --connectivity 4
python src/main.py --file photo.png --mode all --json report.json
```

**Input:** any local PNG/JPG readable by OpenCV. Grayscale or colour.

**Exit codes:** `0` = success · `2` = usage/validation/decode error.

---

# 🧠 How It Works

```text
image.png ──► cv2.imread (grayscale or BGR)
                    │
      ┌─────────────┼───────────────────┐
      ▼             ▼                   ▼
   OTSU          K-MEANS           COMPONENTS
 histogram      pixels → k        Otsu mask
 256 bins       k-means++ seed    BFS stack
 cumulative     assign / update   label regions
 ω, μ, σ²_B     SSE + iters       sizes sorted
      │             │                   │
      └─────────────┴─────────┬─────────┘
                              ▼
              stats + ASCII preview + JSON export
```

Otsu's trick is that both class means can be accumulated incrementally:

```text
ω(t)  = Σ_{i≤t} p(i)                 # background weight
μ(t)  = Σ_{i≤t} i·p(i)               # background mean accumulator
σ²_B(t) = (μ_T·ω(t) − μ(t))² / (ω(t)(1 − ω(t)))
threshold = argmax_t σ²_B(t)
```

k-means uses k-means++ seeding (farthest-point weighted sampling) so results are stable across runs with a fixed seed. Connected components use an explicit stack instead of recursion, so a 160×160 image can never blow the Python stack.

---

# 🛠 Technologies

- Python 3
- NumPy (histograms, cumulative sums, vectorised k-means)
- OpenCV (PNG decoding + exact cross-checks)
- argparse / json / logging
- pytest

---

# 📚 Concepts Covered

- Between-class variance and the Otsu criterion
- Histogram accumulation with `np.cumsum`
- k-means++ seeding and the assignment/update loop
- Inertia (SSE) as a clustering quality measure
- BFS flood fill and 4- vs 8-connectivity
- Region-size statistics and tiny-region filtering
- Downsampling masks into fixed-width ASCII art
- Validating from-scratch algorithms against a trusted library
- Deterministic pipelines with seeded RNG

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**61 tests passed** covering loading edge cases, grey conversion for 2-D/3-channel/4-channel input, Otsu correctness on synthetic bimodal images and exact cv2 agreement, threshold validation, k-means range/seed/determinism/inertia checks, 4- vs 8-connectivity on diagonal pixels, component sizes, every CLI mode, JSON export, demo idempotency, and quiet-mode output suppression.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
