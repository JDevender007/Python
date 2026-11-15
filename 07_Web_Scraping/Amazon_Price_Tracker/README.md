<div align="center">

# 💰 Amazon Price Tracker

### The legacy parser read a price with `re.sub(r"[^\d.]", "", value)` and then `float()`. On the shop's own euro formatting it returns **1.299 for a €1,299 item** — a thousand times too small, and nothing raises.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

```python
def clean_price(value):
    if not value:
        return 0.0
    cleaned = re.sub(r"[^\d.]", "", value)
    try:
        return float(cleaned)
    except ValueError:
        return 0.0

def calculate_percentage_change(old_price, new_price):
    if old_price <= 0:
        return 0.0
    return ((new_price - old_price) / old_price) * 100
```

One regular expression, one float, and a `0.0` that means four different things at
once.

**1 → Deleting characters is not parsing.** `[^\d.]` throws away the currency symbol,
the thousands separator, the minus sign and the decimal comma, then hopes what is
left is a number. On the euro formatting the same shop uses for other customers,
`"1.299,00 EUR"` becomes `"1.29900"`, which is **1.299** — a thousand times too small,
and it does not raise:

```text
'1.299,00 EUR'              1.2990   EUR 1,299.00   129900 cents
```

**2 → A range is not a price.** A deal page shows `"$1,299.00 - $1,399.00"`. Deleting
the non-digits leaves `"1299.001399.00"`, `float` raises, and the `except` turns the
most informative price on the page into **zero**. Five of the eleven price texts in
the demo are answered with a silent `0.0`, and none of them raises.

**3 → Zero is not "unknown", and it is not free either.** Every failure path returns
`0.0`, so an unreadable price is indistinguishable from a free item — and
`calculate_percentage_change` then reports `0.0` for a price that went from unreadable
to $5, "no change", because it guards `old_price <= 0` instead of admitting it has no
baseline:

```text
change_bp(first, last)      = -7.15%
change_bp(None, last)       = unknown
change_bp(zero, last)       = refused: $0.00 cannot be a baseline
legacy_percentage_change(0.0, 1299.0) = 0.0 -- 'no change'
```

**4 → The first match is not the buy box.** The parser walked a list of selectors in
order and took the first text it found. On a discounted page the first `.a-offscreen`
is the struck-through **list** price, not the price you pay:

```text
the first .a-offscreen on the page says $1,399.00
the buy box (priceToPay) says $1,299.00
the list price, read as a list price, is $1,399.00
```

| | legacy | here |
|---|---|---|
| `"$1,299.00"` | `1299.0` | `129900` cents, `USD` |
| `"1.299,00 EUR"` | `1.299` — 1000× too small | `129900` cents, `EUR` |
| `"$1,299.00 - $1,399.00"` | `0.0` | refused, and `parse_range` reads both ends |
| `""` / `"$"` | `0.0` | refused, with the sentence |
| three decimals | `1299.005` | refused: a price has two |
| a change from an unknown price | `0.0` | `None`, printed as `unknown` |
| a change from a zero price | `0.0` | refused: no baseline |
| the price on a discounted page | the list price | the buy box, named |

The demonstration is offline: one bundled page, one bundled price log, and no
network anywhere.

Standard library only: no `requests`, no `beautifulsoup`, no network.

---

# ✨ Features

- `Money` — integer cents and a currency code, validated at construction, ordered,
  addable only within one currency, printed grouped (`$1,299.00`, `EUR 1,299.00`)
- `divide_half_up` — integer division that rounds a half away from zero, because
  `round()` is half-to-even
- `parse_amount` / `parse_price` — symbol or ISO code, both separators, `1.299` read
  as 1299 and `1.29` as 1.29, spaces as grouping, and a refusal for everything else
- `parse_range` — the two ends of a range, either of which may be absent
- `is_range` — a hyphen between two amounts, an en dash, an em dash, or the word `to`
- `change_bp` / `format_bp` — a change in basis points, `None` when there is no
  baseline, and `unknown` rather than a zero
- `Element` / `parse_html` — just enough DOM to name an element by tag, class or id
- `parse_offer` — the buy box read by name, the list price read as a list price, and
  a `note` that says why a price could not be read
- `legacy_clean_price` / `legacy_percentage_change` / `legacy_offer_price` — the three
  legacy functions, executable, so the demo can refute them
- `Watch` — tick-ordered samples, lowest, change from the first, and the samples at or
  below a target
- `audit` — nine named checks with a guard, so a broken price is a `FAIL` not a
  traceback
- CLI: `--page`, `--watch`, `--price`, `--range`, `--target`, `--audit`, `--json`,
  `--quiet`, `--demo`
- 171 passing pytest tests

---

# 📂 Folder Structure

```text
Amazon_Price_Tracker/
│
├── src/
│   ├── main.py   # CLI: the offer, the watch, one price, a range, the audit
│   └── prices.py # money, parsing, ranges, change, DOM, the offer, the watch
│
├── tests/
│   └── test_prices.py
│
├── data/
│   ├── offer.html # one product page: list price first, buy box second
│   └── watch.txt  # five days of the buy-box price, tab separated
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 07_Web_Scraping/Amazon_Price_Tracker

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: the euro price read two ways, the range refused, the buy box
python src/main.py --demo

# Read the bundled page and the bundled watch
python src/main.py

# Read one price, as cents
python src/main.py --price "1.299,00 EUR"

# Read a range, because a range is not a price
python src/main.py --range "$1,299.00 - $1,399.00"

# Report the days at or below a target
python src/main.py --target "$1,250.00"

# Every check
python src/main.py --audit

# The whole reading as JSON
python src/main.py --json reading.json

# Your own page and log
python src/main.py --page .\offer.html --watch .\watch.txt
```

**Exit codes:** `0` = the command ran · `1` = an audit check failed · `2` = a price
that cannot be read, a text that is not a range, a missing file, or a line without a
tab.

---

# ⚙️ How It Works

```text
parse_amount(text)
  ├── one currency marker or none (none means USD); two is a refusal
  ├── a range is refused -- parse_range is what reads a range
  ├── nothing but digits and separators is allowed after the marker
  ├── both ',' and '.' -> the LAST one is decimal, the other groups
  ├── one separator, then exactly three digits -> thousands (1.299 = 1299)
  ├── one separator, then one or two digits -> decimals (1.29, 12,50)
  └── more than two decimals -> refused

change_bp(old, new)              # in hundredths of a percent
  ├── either end unknown          -> None
  ├── currencies disagree         -> refused
  ├── old <= 0                    -> refused: no baseline
  └── (new-old)*10000 / old, half away from zero
```

Details worth knowing:

- **Cents are integers, not floats.** `0.1 + 0.2` is not `0.3`, and a shop that adds
  a tax and a shipping line needs the sum to print the way the receipt does.
- **The rounding is written out, not borrowed.** `divide_half_up(2548, 8)` is 319
  where `round(318.5)` is 318, because `round` is half-to-even. A report that rounds
  two prices differently depending on which side of the half they land is not a
  report.
- **The last separator decides.** `1.299,00` and `1,299.00` are the same money, and
  the rule that says so is one line rather than a locale table.
- **A single separator with three digits is grouping.** `1.299` is 1,299 dollars, not
  one dollar and thirty cents — the rule a person reading the page uses, stated
  explicitly so it can be tested.
- **Unknown is a value.** `change_bp(None, x)` is `None` and prints `unknown`; a
  percentage from a price nobody read is not zero, and saying so is the whole point.
- **The buy box is named.** `priceToPay` is what the page calls the price you pay;
  `a-text-price` is what it calls the list price. Both are read, and the first is not
  allowed to be the second.
- **Bodies are text, so the tree is text.** No HTML parser dependency: `HTMLParser`,
  an `Element` with children, and three lookup methods are enough to read one page.
- **A broken price is a `FAIL`.** Every audit check runs behind a guard, because a
  negative control plants the defect exactly where the check looks.

---

# 🧪 Technologies

- Python 3 standard library: `re`, `dataclasses`, `html.parser`, `pathlib`, `json`,
  `argparse`, `contextlib`
- pytest 9.1.1

No `requests`, no `beautifulsoup4`, no network.

---

# 📚 Concepts Covered

- Money as integer cents and a currency, not a float
- Half-up rounding, written out, and why `round()` is not it
- Decimal separators, grouping separators, and the rule that reads both
- A range kept as a range instead of collapsed to zero
- Unknown as a distinct value from zero, and how a guard hides the difference
- "The first match" as a selector bug, and naming the element instead
- Reporting a reason rather than a `0.0` when text cannot be read
- Audits whose negative controls plant the defect where the check looks

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**171 tests passed** covering `Money` construction and arithmetic, ten refusals, the
half-up rounding and the `round(318.5) == 318` counterexample, every separator case
(`1.299`, `1.29`, `12,50`, `1.299.000,00`, a space as grouping), the legacy cleaner's
silent `0.0` on five texts, range detection and reading, the DOM's classes, nesting,
void elements and entities, the buy box against the first `.a-offscreen`, the `Watch`
rules, the parser's line-numbered errors, nine audit checks with seven negative
controls, the demo, and every CLI mode including four exit-code-2 paths.

---

# 🎯 Learning Outcomes

- Read money out of text as integer cents, and say why a float is not money
- Tell a decimal separator from a grouping separator, in either convention
- Distinguish a price from a range, and keep both readable
- Report an unknown change as unknown, and refuse a zero baseline
- Read an element by the name the page gives it instead of by first match
- Write a demo whose legacy defect is executable and refutable

---

# 🚀 Future Improvements

- A locale table, so a shop that writes `1 299,00` is read without a rule
- A tax and shipping line, so a total is a sum of `Money` and not a float
- `Decimal` at the boundary, when a source states more than two decimals
- A price-history chart from `Watch`, drawn from the same cents
- A second page shape, so the buy-box lookup is a strategy rather than a name

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
