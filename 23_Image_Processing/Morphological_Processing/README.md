<div align="center">

# 🔲 Morphological Processing

### Binary morphology from scratch: dilation, erosion, opening, closing and their combinations, plus connected-component labelling and Zhang-Suen thinning. Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-2.5.2-013243?style=for-the-badge&logo=numpy&logoColor=white)
![Pillow](https://img.shields.io/badge/Pillow-12.3.0-3776AB?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

Morphology is set arithmetic on pixel neighbourhoods. A **structuring element** — a small binary pattern such as a 3×3 square or a plus — decides which neighbour configurations matter, and two operations decide everything else:

```text
dilate(A, B)(p) = OR  { A(q) : q ∈ p + B }     grows the foreground
erode (A, B)(p) = AND { A(q) : q ∈ p + B }     shrinks the foreground
```

**Composing the two gives the practical filters.** `opening = erode then dilate` deletes specks smaller than the element. `closing = dilate then erode` fills holes smaller than the element. `gradient = dilate − erode` is an edge band, `boundary = A − erode(A)` is the inner contour, and `top-hat`/`black-hat` isolate the detail that opening/closing would discard.

**Everything is verified as an algebraic identity, not eyeballed.** The demo and the suite assert:

- `~dilate(~A, B) == erode(A, B)` — erosion is dilation on the complement;
- `opening(A) ⊆ A` and `closing(A) ⊇ A` (anti-extensive / extensive);
- `opening(opening(A)) == opening(A)` and the same for closing (idempotence);
- `area(erode(A)) <= area(A) <= area(dilate(A))`;
- `dilate(dilate(A, 3×3), 3×3) == dilate(A, 5×5)` — the Minkowski sum;
- the boundary of an `n × n` solid square is exactly `4n − 4` pixels;
- on a **bimodal** image, every threshold level strictly between the two modes gives a bit-identical mask.

**A real bug the tests caught.** The first implementation ANDed each window with the element and then required *all* cells of the whole window to be true — which made a cross or a disk behave exactly like its bounding box, because the masked-out cells contributed `False` to the intersection. Erosion now fills cells outside the element with the *neutral* value (`True` for an intersection, `False` for a union), so `erode(A, cross)` and `erode(A, square)` are genuinely different. The duality identity is what exposed it.

**Border handling is where morphology quietly breaks.** Treating everything outside the frame as background is the natural convention, but then `closing` would *trim* the outermost foreground ring instead of extending it, and `closing(A) ⊇ A` would fail. Opening, closing and their derivatives therefore run on a background-extended canvas and crop afterwards, which is exactly the operation over the infinite background extension. That is why idempotence holds to the last border pixel.

**The bundled 128×128 sample is a deliberately noisy binary image** — three blobs, 304 salt specks of 4 px or fewer, and 110 enclosed pepper holes. With a 3×3 square element:

| Operation | Pixels | Share | vs input | Components |
| --- | --: | --: | --: | --: |
| input | 4406 | 26.89% | +0 | 307 |
| erode 3×3 | 2778 | 16.96% | −1628 | 3 |
| dilate 3×3 | 7388 | 45.09% | +2982 | 149 |
| open 3×3 | 3974 | 24.26% | −432 | 3 |
| close 3×3 | 4651 | 28.39% | +245 | 242 |
| gradient | 4610 | 28.14% | +204 | 188 |
| boundary | 1628 | 9.94% | −2778 | 346 |
| clean (open→close) | 4140 | 25.27% | −266 | 3 |

**And the check that matters is comparative, not absolute.** Opening removes all 304 specks; plain erosion would also remove them but keeps only 2778 pixels instead of 4140, because it eats 2 px off every shape. The demo asserts both facts, plus a negative control: a 1×1 element must be the identity, so the removal really comes from the element size and not from the threshold.

After cleaning, exactly **three** components remain and they account for **all 4140** foreground pixels — nothing but the shapes is left. Thinning (Zhang-Suen) then reduces 4140 pixels to a 36-pixel skeleton (0.9%), deleting pixels only, and preserving all three connected parts.

Note that on this deliberately noisy sample a 5×5 element erodes everything to nothing until the specks are gone first — which is exactly the argument for cleaning before a large opening.

No network, no API keys, no OpenCV, no SciPy, no skimage.

---

# ✨ Features

- `dilate` / `erode` with background or replicate border handling
- Structuring elements: square, cross, disk, diamond, rectangle, plus a named factory
- Composite filters: opening, closing, gradient, boundary, top-hat, black-hat, clean
- Background-extended canvas so closing is extensive and both filters are idempotent
- Connected-component labelling with 4- or 8-connectivity via BFS
- Per-component area, bounding box, centroid, height/width and border flag
- Speck counting, enclosed-hole counting, largest-component ranking
- Zhang-Suen thinning with a configurable iteration cap
- Metrics: area, foreground fraction, perimeter, IoU
- Binary ASCII preview with a 2:1 character aspect
- `--demo`, `--file`, `--threshold`, `--shape`, `--size`, `--radius`
- Repeatable `--op` pipeline applied in order, plus `--skeleton`, `--components`, `--ascii`
- `--save`, `--json`, `--quiet`
- Fast-fail flag validation (`parser.error`) before any file is read
- Deterministic bundled data: `data/noisy_shapes_128.png`
- 188 passing pytest tests

---

# 📂 Folder Structure

```text
Morphological_Processing/
│
├── src/
│   ├── main.py   # CLI: --op pipeline, --components, --skeleton, --json
│   └── morph.py  # elements, morphology, components, thinning, demo
│
├── tests/
│   └── test_morph.py
│
├── data/
│   └── noisy_shapes_128.png   # 3 blobs + 304 specks + 110 holes
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 23_Image_Processing/Morphological_Processing

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: 14 self-checks, cleaning table, components, skeleton
python src/main.py --demo

# Default action: threshold, then clean
python src/main.py

# A pipeline of operations, applied in order
python src/main.py --op open --op close --shape disk --radius 2

# Report components and thin the result
python src/main.py --components --skeleton --ascii

# Save the mask and the statistics
python src/main.py --op boundary --save output/ring.png --json output/run.json
```

**Input:** a PNG/JPEG up to 512×512 (colour images are converted to grey), binarised at `--threshold` (pixels strictly above it are foreground).

**Exit codes:** `0` = success · `2` = usage, validation or IO error.

---

# 🧠 How It Works

```text
image ──► threshold(level) ──► binary mask
                                  │
                        ┌─────────┴─────────┐
                        ▼                   ▼
                     dilate              erode
                    (any)               (all)
                        │                   │
        ┌───────────────┴───────────────────┘
        ▼
  opening = erode → dilate      closing = dilate → erode
  gradient = dilate − erode     boundary = A − erode(A)
  top_hat  = A − opening(A)     black_hat = closing(A) − A
        │
        ├──► label_components (BFS, 4/8-connectivity)
        └──► skeleton (Zhang-Suen, two sub-iterations per pass)
```

The two sub-iterations of Zhang-Suen delete a foreground pixel `p` only when

```text
2 <= B(p) <= 6        B = number of foreground neighbours
A(p) == 1             A = number of 0→1 transitions around the ring
p2·p4·p6 == 0 and p4·p6·p8 == 0        (first pass)
p2·p4·p8 == 0 and p2·p6·p8 == 0        (second pass)
```

The first condition pair peels the north-west side, the second the south-east side, together producing a thin skeleton without shortening it from both ends at once.

---

# 🛠 Technologies

- Python 3 standard library (`json`, `logging`, `argparse`, `pathlib`, `dataclasses`, `collections.deque`)
- NumPy 2.5.2 (`sliding_window_view`, `np.pad`, boolean reductions)
- Pillow 12.3.0 (PNG decode/encode only)
- pytest

No OpenCV, no SciPy, no scikit-image.

---

# 📚 Concepts Covered

- Binary morphology as neighbourhood set arithmetic
- Structuring elements and why non-rectangular ones need a neutral fill value
- Dilation/erosion duality under complement
- Anti-extensiveness, extensiveness and idempotence as testable laws
- The Minkowski sum: composing dilations vs a bigger element
- Border conventions and the background-extended canvas
- Salt-and-pepper removal by opening, hole filling by closing
- Inner boundary, morphological gradient, top-hat and black-hat
- Connected-component labelling with BFS and 4- vs 8-connectivity
- Region properties: area, bounding box, centroid, border contact
- Zhang-Suen thinning and connectivity preservation
- IoU, area fractions and per-stage reporting

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**188 tests passed** covering threshold semantics and every validation path, all five structuring-element shapes and their argument checks, element validation (dims, emptiness, even sizes, inactive elements), dilation/erosion on known patterns, the duality law, the Minkowski sum, border modes, opening/closing anti-extensiveness, extensiveness and idempotence, top-hat/black-hat/boundary/gradient relationships, component labelling with both connectivities (including diagonal joining), bounding boxes, centroids, border flags, speck and hole counting, largest-component ranking, Zhang-Suen subset/thinning/connectivity/iteration-cap behaviour, IoU and perimeter metrics, image IO limits, ASCII preview, demo idempotency, and every CLI path including the repeatable operation pipeline and fast-fail flag validation.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
