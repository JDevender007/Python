<div align="center">

# 🍽️ Restaurant Menu

### The course version aligned a menu with `20 - len(dish) - len(str(price))` spaces of dashes. A long dish name produced **no gap at all**, because `'-' * -7` is `''` in Python — and `len()` is not the number of columns a string occupies.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

Six lines, and four separate problems:

```python
n = int(input())
for i in range(n):
    dish = input()
    price = int(input())
    dash = 20 - len(dish) - len(str(price))
    print(dish + ('-' * dash) + "$" + str(price))
```

**1 · A negative gap disappears silently.** `'-' * -7` is `''`, not an error. So a dish name long enough to overrun the twenty columns prints with no separator at all:

```text
legacy, short name: 'Pad Thai----------$12'
legacy, long name:  'Slow-roasted lamb shoulder$24'
```

The price is glued to the name. Nothing warns, because the expression is legal.

**2 · `len()` is not display width.** A combining mark adds nothing to the printed width but one to `len`:

```text
'Cafe' + U+0301   len 5   width 4   ->  the line ends one column short
'寿司'             len 2   width 4   ->  the line ends two columns long
```

So the rows stop lining up as soon as the menu is not plain ASCII. `unicodedata.combining` and `unicodedata.east_asian_width` are the two rules needed, and the demo pins both against `len`.

**3 · Prices are whole numbers.** `int(input())` means `4.50` raises `ValueError`, and a menu cannot express four dollars fifty. Money is an integer number of *cents*; the parsing is done with `Decimal` so `4.50` is exactly `450`.

**4 · There is no menu, no cart and no total.** Every run is one throwaway list. Nothing persists, nothing adds up, and no tax exists.

The replacement is a menu file, a renderer that guarantees a gap, and a cart:

```text
name,price
Garlic Bread,4.50
Tomato Soup,6.25
...
Lemonade,3.25
```

```text
              MENU
Garlic Bread....................$4.50
Tomato Soup.....................$6.25
...
Lemonade........................$3.25
```

Every line is exactly 34 columns wide, and the demo asserts that on all ten. When a name genuinely does not fit, the line keeps **one space** instead of losing the separator:

```text
'Sslow-roasted lamb shoulder with rosemary $24.00'
```

**Rounding is done in integers, at the boundary.** Tax is 8.75 %, held as 875 basis points, and computed as `(cents * 875 + 5000) // 10000` — half-up on the exact half cent, not `round()`, which rounds half to even and would disagree with a till. The demo pins `$10.00 -> $0.88` (87.5 cents) and `$5.71 -> $0.50` (49.9625 cents).

**Everything is falsifiable.** The demo proves the legacy collapse, the `len`/width disagreement in both directions, that `int('4.50')` raises while 450 cents parses exactly, four refused prices, the ten loaded dishes with pinned extremes, ten lines of exactly 34 columns, a cart totalling 45.00 with 3.94 tax, six impossible cart operations refused, and a byte-identical menu round trip.

Standard library only, no network.

---

# ✨ Features

- `parse_price` / `format_price` — exact integer cents, `$`, thousands separators, two decimal places enforced
- `display_width` — combining marks count 0, East Asian wide/fullwidth count 2
- `legacy_line` — the original formatter, including the negative-gap collapse
- `dot_leader` — fixed-width row, or one space when the name does not fit
- `MenuItem` — frozen dataclass; non-blank name, non-negative integer price
- `load_menu` — canonical header, comments, line-numbered errors, duplicate names refused
- `find_item` — case-insensitive exact lookup
- `render_menu` — heading plus one fixed-width line per dish
- `tax_for` — half-up integer rounding over basis points
- `Cart` — add, merge, remove, quantity, subtotal, tax, total, render
- `data/menu.csv` — 10 dishes, cheapest 3.25, dearest 19.95
- CLI: `--price`, `--order`, `--stats`, `--legacy`, `--width`, `--tax-rate`, `--write`, `--json`, `--quiet`
- Exit `2` on a `MenuError`; `--demo` always returns `0`
- 155 passing pytest tests

---

# 📂 Folder Structure

```text
Restaurant_Menu/
│
├── src/
│   ├── main.py   # CLI: menu, price, order, stats, legacy view
│   └── menu.py   # money, width, MenuItem, loader, Cart, tax
│
├── tests/
│   └── test_menu.py
│
├── data/
│   └── menu.csv  # 10 dishes
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 02_Udemy_Course_Projects/Restaurant_Menu

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo
python src/main.py --demo

# The printed menu
python src/main.py

# Counts and extremes
python src/main.py --stats

# One dish
python src/main.py --price "Pad Thai"

# A cart, with the tax added
python src/main.py --order "Margherita Pizza:2" --order Lemonade --order "Garlic Bread:3"

# A different tax rate
python src/main.py --order "Garlic Bread" --tax-rate 10

# What the original formatter would have printed
python src/main.py --legacy "Pad Thai:12"
python src/main.py --legacy "Slow-roasted lamb shoulder:24"

# Normalise a menu file
python src/main.py --write clean.csv
```

**Menu format** (`data/menu.csv`) — one dish per line, `#` starts a comment, prices in dollars and cents:

```text
name,price
Pad Thai,13.40
```

**Exit codes:** `0` = the command ran · `2` = missing file, wrong header, bad price, duplicate dish, unknown dish, impossible quantity, bad tax rate, or a malformed argument.

---

# 🧠 How It Works

```text
name,price
   │
   ├── parse_price()   ->  integer cents, exactly
   ├── display_width() ->  columns, not characters
   ▼
MenuItem
   │
   ├── render_menu()   ->  every line exactly N columns
   └── Cart
         ├── add / remove / quantity_of
         ├── subtotal() = sum(price * quantity)
         └── tax_for()  = (cents * 875 + 5000) // 10000
```

Details worth knowing:

- **The negative gap is a language feature, not a bug in the course author's maths.** `str * -7` is defined to be empty, so the expression is valid and the failure is silent. That is why the demo asserts the exact glued string rather than "looks wrong".
- **Display width is two rules, not one.** Combining marks (category `Mn`) draw on the previous character, and East Asian `W`/`F` characters occupy two cells. Everything else is one. A full `wcwidth` implementation also handles control characters and emoji sequences; this menu needs the two rules and says so.
- **`dot_leader` returns a longer line rather than a shorter one.** If the name cannot fit, the gap becomes a single space, so the price is never merged into the name. The alternative — truncating the name — would hide menu content.
- **Money never touches a float.** `Decimal("4.50") * 100` is exactly `450`; a rejection of `4.505` is a typo, not a rounding decision.
- **Tax rounds half-up, in integers.** `(cents * basis_points + 5000) // 10000` is the standard half-up formula for non-negative values, and the demo pins the exact half-cent case where `round()` would differ.
- **Duplicate names are refused.** A cart line identifies a dish by name, so two `Soup` rows would make `add("Soup")` ambiguous. The error names the line number.

---

# 🛠 Technologies

- Python 3 standard library: `csv`, `decimal`, `unicodedata`, `dataclasses`, `tempfile`, `os`, `argparse`, `json`, `pathlib`
- pytest

No terminal library, no locale database, no network.

---

# 📚 Concepts Covered

- Negative repeat counts and silent string arithmetic
- Display width versus `len`: combining marks and wide characters
- Dot leaders and fixed-width terminal layout
- Integer cents and exact decimal parsing
- Half-up rounding in integers versus `round()`
- Frozen dataclasses as validated records
- Line-numbered errors for data files
- Duplicate keys in a name-addressed catalogue
- Atomic file writes
- A cart as a list of `(item, quantity)` lines with derived totals

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**155 tests passed** covering price parsing (nine accepted shapes, nine refused, booleans and negatives) and formatting (padding, thousands, signs, non-integers), display width (ASCII, empty, combining, wide, fullwidth, non-text), the legacy formatter (short name, the 21-character line, the negative-gap collapse, the combining mark and CJK cases), dot leaders (full width, trailing price, long names, custom width), `MenuItem` validation and row round trips, the bundled menu (ten dishes, pinned extremes, uniqueness, average), the loader (missing, empty, wrong header, no dishes, bad price by line, extra fields, duplicates, comments, dollar signs), lookup, rendering, tax (eight pinned cases including both rounding boundaries and five refusals), the cart (empty, add, merge, remove, quantities, the pinned 41.75 subtotal, rendering, no mutation of the menu), writing (round trip, header, byte-identical rewrite, directories, no temporary files), demo determinism, and every CLI mode including JSON and quiet.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
