<div align="center">

# 💱 Currency Converter API

### The legacy converter kept one float per pair and used it in both directions. A hundred dollars became 92 euro, and 92 euro became **84.64 dollars** — fifteen dollars and change gone, with no exception. A currency the table did not hold converted **at par**, because `rates.get(code, 1.0)`.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

```python
def convert(amount, rate):
    return round(amount * rate, 2)

def rate_for(rates, code):
    return rates.get(code, 1.0)
```

**1 → A rate has a direction.** `0.92` means "one dollar is 0.92 euro". Multiplying
euros by it says "one euro is 0.92 euro", which is not a rate at all:

```text
EUR  rate 0.9200  100.00 USD ->   92.00 EUR ->   84.64 USD
GBP  rate 0.7900  100.00 USD ->   79.00 GBP ->   62.41 USD
CHF  no rate      100.00 USD ->  100.00 CHF  (par, because get() defaults to 1.0)
```

The return leg is a **15.36 % loss per round trip**, and it is silent: the number is
positive, has a currency symbol and two decimals, and is wrong.

**2 → `get(code, 1.0)` is a currency that always exists.** A code the table does not hold
converts **at par**. A typo in a currency code is a valid conversion, and the answer looks
perfectly reasonable.

**3 → `round()` is not the rounding an invoice means.** `round(2.675, 2)` is **2.67**,
because the binary double for 2.675 is below the tie, and `round` goes to the even
neighbour anyway — `round(2.5)` is 2, `round(3.5)` is 4:

```text
round(2.675, 2)                = 2.67
half-up of 2.675 to two places = 2.68
round(2.5) is 2 and round(3.5) is 4: round() goes to the even neighbour
```

**4 → A rate without a date is a rate of unknown age.** The sheet says `as_of 2026-11-14`.
Converting December's money with it is a decision, and the decision is printed:

```text
fresh  quoted 2026-11-14, read 2026-11-15, 1 day(s) old, limit 7
STALE  quoted 2026-11-14, read 2026-11-22, 8 day(s) old, limit 7
STALE  quoted 2026-11-14, read 2026-12-20, 36 day(s) old, limit 7
```

**5 → A minor unit is a property of the currency.** Yen has no subunit; dollars and euros
have hundredths. A ratio of **major** units applied to **minor** amounts needs the exponent
in the arithmetic, or a hundred dollars is 151 yen instead of 15,100 — and the legacy path,
which has no exponents at all, reports **2,280,100.00 USD** for 100 dollars of yen:

```text
USD/JPY  151.000000   (USD/JPY = 151/1)
100.00 USD -> 15,100 JPY -> 100.00 USD   drift +0
```

| step | legacy | here |
|---|---|---|
| 100.00 USD → EUR | `92.00` | `92.00` |
| 92.00 EUR → USD | `84.64` | `100.00` |
| 100.00 USD → JPY | `15100.00 JPY` | `15,100 JPY` |
| 100.00 USD → CHF | `100.00 CHF` (par) | refused: holds no rate for CHF |
| 2.675 rounded to cents | `2.67` | `2.68` |
| a rate read in December | no age at all | `STALE`, 36 days old |
| 6 cents → EUR → USD | — | `7`, drift `+1`, reported |

The demonstration is offline: one bundled rate sheet and one bundled list of amounts.
Standard library only: no `requests`, no HTTP client, no API key.

---

# ✨ Features

- `Rate` — **two integer parts and a direction** (`base`, `quote`, `numerator`,
  `denominator`), validated at construction: two different three-letter codes, a positive
  numerator and denominator, and a zero rate refused because it has no inverse
- `Rate.inverse()` — the pair swapped, **nothing divided**, so inverting twice is the
  identity and no precision is lost
- `Rate.text()` / `Rate.decimal_text()` — `USD/EUR = 92/100` and `0.920000`, the ratio
  exactly as the sheet holds it and as a person reads it
- `convert(rate, amount, from_exponent, to_exponent)` — integer arithmetic with the
  currency exponents in the ratio, rounded half-up
- `divide_half_up` — half away from zero, written out, because `round(2.5)` is 2
- `money_text` — minor units printed with the currency's own number of decimals and
  thousands separators: `100.00 USD`, `15,100 JPY`, `1,234.567 KWD`
- `Quote` — a `date`, a base, and the rates; `for_currency()` names the code it is missing
  and lists the ones it holds, `age_days()`, `is_stale(on, limit)`
- `Sheet` — a quote and every currency's exponent, with `convert`, `convert_back`,
  `drift`, `money`, `fresh`
- `legacy_convert` / `legacy_rate` — the two legacy lines, executable, so the demo refutes
  them
- `parse_sheet` / `parse_amounts` — `as_of`, `base`, `exp CODE N`, `rate CODE N D` and
  `CODE amount`, with line-numbered errors
- `audit` — nine named checks with a guard, and the reading day injected so a negative
  control can read the sheet on a day it was never meant for
- CLI: `--quote`, `--amounts`, `--on`, `--limit`, `--convert`, `--audit`, `--json`,
  `--quiet`, `--demo`
- 176 passing pytest tests

---

# 📂 Folder Structure

```text
Currency_Converter_API/
│
├── src/
│   ├── main.py   # CLI: the sheet, one conversion, the audit
│   └── rates.py  # rates, inverses, exponents, money, quotes, the audit
│
├── tests/
│   └── test_rates.py
│
├── data/
│   ├── quote.txt    # as_of, base, four exponents, three rates
│   └── amounts.txt  # four amounts and the currency to convert each to
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 08_API_Development/Currency_Converter_API

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: the sheet, the legacy pair, rounding, drift, staleness
python src/main.py --demo

# Convert the bundled amounts
python src/main.py

# One conversion, in either direction
python src/main.py --convert "100.00 USD to EUR"
python src/main.py --convert "92.00 EUR to USD"

# Yen has no subunit, and the exponent knows it
python src/main.py --convert "15100 JPY to USD"

# Read the sheet a month after it was quoted
python src/main.py --on "2026-12-20" --limit 7

# Every check
python src/main.py --audit

# The reading as JSON
python src/main.py --json rates.json
```

**Exit codes:** `0` = the command ran · `1` = an audit check failed · `2` = a currency the
sheet does not hold, a conversion that cannot be parsed, an amount too precise for its
currency, a day that is not a day, or a missing file.

---

# ⚙️ How It Works

```text
convert(rate, amount, from_exponent, to_exponent)
  ├── shift = to_exponent - from_exponent
  ├── shift > 0  -> numerator   * 10 ** shift
  ├── shift < 0  -> denominator * 10 ** -shift
  └── divide_half_up(amount * numerator, denominator)

Quote.for_currency(code)
  ├── code == base      -> refused: the base needs no rate
  ├── a rate holds it   -> that rate
  └── otherwise         -> refused, naming the codes it does hold

Sheet.convert_back(minor, code)
  ├── take the rate for `code`
  ├── swap its two numbers (inverse, not 1 / rate)
  └── convert back through the base exponent
```

Details worth knowing:

- **A rate is a ratio, not a number.** `92/100` cannot drift, cannot be confused with
  `100/92`, and its inverse is exact. `0.92` can do all three.
- **The inverse is a swap.** Dividing by 92/100 and multiplying by 100/92 are the same
  thing only in exact arithmetic; a float division is close, and "close" is what the
  legacy converter shipped.
- **The exponent is part of the conversion, not of the rate.** `151/1` is 151 yen per
  dollar in *major* units; turning 10,000 cents into yen needs the two-place shift, and
  the sheet carries it per currency.
- **Rounding is half-up, written out.** `divide_half_up(2675, 10)` is 268, and `round`
  is never used on money.
- **A second rounding can drift.** 6 cents → 6 EUR cents → 7 USD cents. The sheet reports
  the drift instead of pretending the round trip is free, and 4 of 4 bundled amounts
  happen to come back exactly.
- **A quote is dated, and the day is an argument.** `--on` changes the age and the
  staleness of every line and nothing else, so the demo is reproducible.
- **A missing rate is a sentence.** `the sheet of 2026-11-14 holds no rate for CHF; it
  holds EUR, GBP, JPY`.
- **A broken rate is a `FAIL`.** Every audit check runs behind a guard, because a negative
  control plants the defect exactly where the check looks.

---

# 🧪 Technologies

- Python 3 standard library: `dataclasses`, `datetime`, `pathlib`, `json`, `argparse`,
  `contextlib`
- pytest 9.1.1

No `requests`, no HTTP client, no network, no API key, no `float` anywhere in the money
path.

---

# 📚 Concepts Covered

- An exchange rate as an exact ratio with a direction, and its inverse as a swap
- Why one float per pair is two defects: the missing direction and the lost precision
- Minor units per currency, and an exponent that belongs in the conversion
- Half-up rounding against `round()` and its even neighbour
- Round-trip drift, and reporting it rather than hiding it
- A quote as a dated fact, with an age and a freshness limit
- Refusing a code that is not on the sheet, by name
- Parsing a small fixed-format sheet with line-numbered errors
- Audits with an injected reading day, so a check can be shown to test something

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**176 tests passed** covering half-up conversion and its four refusals, `Rate`
construction and its nine refusals, the inverse and the double inverse, all three
conversions with both exponent shifts, `money_text` with three exponents, `Quote` accessors,
ages and staleness at the limit, `Sheet` conversion in both directions and the drift, the
nine legacy behaviours, the sheet parser and its eleven errors, the amount parser and its
six errors, nine audit checks with eight negative controls, the demo, and every CLI mode
including nine exit-code-2 paths.

---

# 🎯 Learning Outcomes

- Store a rate as a ratio with a direction, and derive the inverse by swapping
- Explain why `rates.get(code, 1.0)` turns a typo into a valid conversion
- Apply a currency's exponent in the conversion instead of assuming two decimals
- Round money half-up, in integers, and never with `round()`
- Measure a round trip and report the drift when a second rounding changes it
- Date a quote, measure its age, and refuse to call a stale sheet fresh
- Refuse a currency by name, listing the ones the sheet does hold

---

# 🚀 Future Improvements

- Cross rates, so EUR→GBP is computed through the base instead of refused
- A rate history, so a stale quote can be replaced by the nearest earlier one
- A second provider's sheet shape, so the field names become a strategy
- A tolerance on the drift, so two conversions that differ by one cent compare as equal
- A retry policy for a 429 sheet, reusing the retry lab from `REST_API_with_FastAPI`

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
