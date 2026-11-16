<div align="center">

# 🖼️ Image Viewer

### The legacy viewer resized with `int(width * scale)` — so a **3×1 sliver in a 2×2 box came out 2×0**, a 3000×1000 panorama lost a pixel of height, and a 90×160 portrait was either 112×200 or 200×356 depending on which side the author picked. This one compares two products to find the binding side, and rounds in integers.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

```python
def resize(image, box):
    scale = min(box[0] / image[0], box[1] / image[1])
    return int(image[0] * scale), int(image[1] * scale)
```

**1 → `int()` truncates, twice, and a placed image cannot be zero pixels tall.**
A 3×1 image in a 2×2 box has a scale of `0.6666666666666666`. Its height is
`1 × 0.6666666666666666 = 0.6666666666666666`, and `int()` of that is **0** — a
window with nothing in it:

```text
tiny             3x1       2x2       2x1       2x0  wrong
```

**2 → One dimension has to be exact.** A fitting rectangle makes one side equal the box
and *derives* the other. Rounding both sides independently gives two roundings, and two
rounded sides are not a rounded ratio. Four of the nine bundled images come out the wrong
size, three of them by exactly one pixel:

```text
wide       3000x1000   320x240   320x107   320x106  wrong
portrait      90x160   200x200   113x200   112x200  wrong
odd           101x51   320x240   320x162   320x161  wrong
```

**3 → Which side binds is two products, not a habit.** `box.width / image.width <=
box.height / image.height` is the same comparison as `box.width * image.height <=
box.height * image.width`, with no division and no float. A viewer that always scales by
width puts a portrait photograph at **200×356** in a 200×200 box and clips a third of it;
the fitted answer is **113×200**.

**4 → Fitting and filling are two different rounding problems.** Fitting must never
overflow, so its derived side rounds *nearest*; filling must never leave a seam, so its
derived side rounds **up**. The side that binds for one is the opposite of the side that
binds for the other. `100×50` in a `40×40` box covers with **80×40** at `(-20, 0)`, while
the *same* image fitted inside it is **40×20** — half the box empty.

**5 → A size of zero has no scale.** `box[0] / image[0]` with a zero width raises, and a
viewer that catches it and returns `(0, 0)` draws a window with no pixels. A `Size` here
cannot be zero, so the division never happens.

So this module keeps a `Size` that refuses zero, computes both placements in integers
(`round_div`, `ceil_div`), and states the binding side by comparing two products. The
legacy path is kept beside it, executable, so every claim above is reproduced with a pixel
count.

The demonstration is offline: one bundled file of images and boxes.

---

# ✨ Features

- `Size` — positive whole width and height; `pixels()`, `orientation()`, `ratio()` reduced
  by `gcd`, `transposed()`, `scaled()`, and refusals for zero, negative, float and `True`
- `binding_side(image, box)` — one comparison of two products, naming the side that limits
  the fit
- `fit_inside(image, box)` — the largest rectangle of the image's ratio inside the box; the
  binding side is **exactly** the box's side, the derived side rounds to nearest
- `fill_box(image, box)` — the smallest rectangle of that ratio that covers the box, the
  derived side rounded **up**, with the negative offsets a centred crop needs
- `centred(image, box)` — the fitted rectangle moved to the middle, so a letterbox has a
  stated offset
- `Placement` — the rectangle, the offsets, the mode, `contains()`, `covers()`, and
  `error()`, the cross-product distance from the exact ratio
- `round_div` / `ceil_div` — half-up and up, from integers, with a refusal for a zero
  denominator
- `legacy_resize()` — the transcribed float path, including its `ZeroDivisionError`
- `audit` — eleven named checks, every one falsifiable by corrupting a measurement or a
  bundle
- CLI: `--images`, `--image WxH`, `--box WxH`, `--mode fit|fill`, `--centre`, `--legacy`,
  `--audit`, `--json`, `--quiet`, `--demo`
- 153 passing pytest tests

---

# 📂 Folder Structure

```text
03_Image_Viewer/
│
├── src/
│   ├── main.py    # CLI: one image or the bundle, fit or fill, the audit
│   └── images.py  # sizes, the binding side, both placements, integer rounding
│
├── tests/
│   └── test_images.py
│
├── data/
│   └── images.txt   # nine images, each with the box it is shown in
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 09_Desktop_Applications/03_Image_Viewer

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: nine images, four wrong sizes, eleven checks
python src/main.py --demo

# Every bundled image, fitted
python src/main.py

# One image in one box, and which side binds
python src/main.py --image 4000x3000 --box 320x240

# Cover the box instead of fitting inside it
python src/main.py --image 100x50 --box 40x40 --mode fill

# Centre a fitted image, so the letterbox offsets are visible
python src/main.py --image 1000x3000 --box 320x240 --centre

# What the float-based resize would have said
python src/main.py --legacy

# Every check
python src/main.py --audit

# The placements as JSON
python src/main.py --audit --json placements.json
```

**Exit codes:** `0` = every check held · `1` = an audit check failed (for example
`--image 4000x3000 --audit`, where a bundle of one cannot satisfy a claim about nine) ·
`2` = a size that is not `WxH`, a zero side, a missing bundle, or a `--mode` that is not
`fit`/`fill`.

---

# ⚙️ How It Works

```text
binding_side(image, box)
  box.width * image.height <= box.height * image.width
      -> "width"      (the width is the tighter ratio)
      -> "height"     otherwise

fit_inside                     fill_box
  binding side = box side        binding side = box side
  derived = round(a*b / c)       derived = ceil(a*b / c)
  one side exact                 one side exact, the other never smaller
```

Details worth knowing:

- **Which side binds.** Compare `box.width / image.width` with `box.height /
  image.height`. Whichever is **smaller** limits a fit. Cross-multiplying turns that into
  one integer comparison, so no float can decide a pixel.
- **The bind, verbatim.** `4000×3000` in `320×240` gives `320 × 3000 = 960000` against
  `240 × 4000 = 960000` — equal ratios, and the width binds. `3000×1000` gives `320000`
  against `720000`, still width. `1000×3000` gives `960000` against `240000`, so height.
- **Fit rounds to nearest, fill rounds up.** Those are not stylistic choices. `3000×1000`
  fitted to a width of 320 needs a height of `1000 × 320 / 3000 = 106.67`, so **107** is
  the closest a whole number can be. The same image *covering* a `320×240` box is
  `720 × 240`, and 719 would leave a one-pixel seam along the side.
- **A fill has negative offsets.** `80×40` in a `40×40` box is centred at `(-20, 0)`: the
  crop takes 20 pixels off each side. `Placement.covers()` is a statement about the size;
  the offsets are where the crop happens.
- **`error()` is a cross product.** `|width * image.height - height * image.width|` is
  zero for an exact ratio and grows with rounding. The audit holds every placement to
  `2 * error <= longest side`, which is the arithmetic form of "less than half a pixel off
  the exact derived side".
- **A sliver cannot collapse.** `Size` refuses zero, so `fit_inside` can never build a
  `Placement` with a zero side — the class refuses that too. The legacy path has no such
  guard, which is why it answers `2x0`.
- **Every check runs behind a guard.** A missing measurement, an empty bundle or a
  division by zero is a `FAIL`, never a traceback, so the audit always reports eleven
  verdicts.

---

# 🧪 Technologies

- Python 3 standard library: `dataclasses`, `pathlib`, `argparse`, `json`, `contextlib`
- pytest 9.1.1

No `PIL`, no `numpy`, no image codec, no GUI toolkit, no network. Every size is an integer
pair and every image is nine numbers in a text file.

---

# 📚 Concepts Covered

- Why `int(width * scale)` is not a size, and what truncation does to a one-pixel rule
- The binding side as a comparison of two products rather than a float ratio
- Deriving one dimension and keeping the other exact
- Rounding to nearest for a fit and rounding up for a cover, in the same project
- Negative offsets, centred crops, and letterboxing
- Cross-product error as a measure of how far a rectangle is from its ratio
- Refusing a zero dimension at construction instead of at division time
- Why a transposed size must not silently change which side binds
- Auditing geometry with corrupt measurements rather than mocked functions

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**153 tests passed** covering `round_div` and `ceil_div` (including a sweep proving ceil is
never below round), `Size` construction, orientation, reduction, transposition, scaling and
its five refusals, `binding_side` against the float ratio for every bundled image,
`fit_inside` on nine pinned pairs, `fill_box` including its negative offsets, `centred`,
`Placement` and its four refusals, the legacy path and its `ZeroDivisionError`, entry
validation and the parser's three refusals, every measurement, eleven audit checks each with
a negative control, the demo, and every CLI mode including four exit-code-2 paths and one
argparse refusal — **22 `pytest.raises` refusals** in all.

---

# 🎯 Learning Outcomes

- Explain why `int(1 * (2 / 3))` is `0` and why that is a bug and not a rounding rule
- Say which side binds a fit, using multiplication instead of division
- Derive one dimension from the other instead of rounding both
- Choose the rounding direction from the requirement: never overflow, or never leave a seam
- Compute a centred crop's offsets, including the negative ones
- Measure how far a rectangle is from its ratio with a cross product
- Refuse a zero size where it is created, not where it is divided by
- Audit geometry by handing in a measurement that has the wrong number

---

# 🚀 Future Improvements

- EXIF orientation, so a photograph taken sideways is rotated rather than letterboxed
- A crop rectangle as a first-class value, so a fill and a user crop are the same type
- Bilinear resampling at a stated filter width, with the same integer arithmetic
- A contact sheet, so all nine placements can be seen at once
- A real Tkinter canvas in front of the same `Placement`

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
