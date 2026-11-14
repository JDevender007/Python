<div align="center">

# 💳 Card Payment

### Four lines of Python that masked a card number — and leaked any number shorter than four digits. This rebuild separates the three questions the original never asked: is it a card, is it this brand, and is it safe to print?

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Offline-No%20Network-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

The course version was this:

```python
cardno = (input())
last_4_digits = cardno[-4:]
space = ("XXXX XXXX XXXX XXXX" + ' ')
print(space + last_4_digits)
```

It runs. It even looks like a payment screen. Three things are wrong, and none of them raise an error.

**It leaks short input.** `"123"[-4:]` is `"123"`. A three-character number is printed in full, behind a row of sixteen placeholders that makes the output look redacted.

**It claims a length it never checked.** The `XXXX` prefix is hard-coded to sixteen. An Amex card is fifteen digits and a Diners card is fourteen, so the output describes twenty digits of a fifteen-digit number. The mask is a picture of a card, not a redaction of *this* card.

**It never validates.** No checksum, no brand, no length policy. A number with one digit typed wrong is masked and presented as though it were fine.

This rebuild answers the three questions separately, because conflating them is exactly how a 14-digit Amex gets accepted:

```text
digits()      "3782 822463 10005"  ->  "378282246310005"
luhn_sum()    the weighted total; a multiple of 10 passes the checksum
brand()       Visa / Mastercard / Amex / Discover / Diners / JCB
length_ok()   is that length one the brand publishes?
mask()        reveal at most the last four digits, never all of them
check()       all three answers, plus one verdict
```

**Luhn is necessary and nowhere near sufficient.** `79927398713` is Luhn-valid — it is the worked example from the Luhn article — and it is not a card number of any brand at any allowed length. It is row 11 of the bundled data on purpose, and `check()` reports it as invalid. A demo that only tested real card numbers would never have found that distinction.

**The checksum is reversible.** For any prefix, exactly one trailing digit makes the total a multiple of ten:

```text
check_digit("411111111111111")  ->  "1"
check_digit("37828224631000")   ->  "5"
check_digit("3056930902590")    ->  "4"
```

All six published prefixes in the demo regenerate their real check digit from the first fifteen digits, and flipping the regenerated digit then fails Luhn. That makes the test a real test: it would fail if the weighting were off by one position.

**Masking keeps the true length.** The mask replaces digits positionally and groups them the way the scheme prints them, so the output shows how many digits there are:

```text
Visa 16        **** **** **** 1111
Amex 15        **** ****** *0005
Diners 14      **** ****** 5904
input "123"    ***                    nothing revealed
```

**Everything in the demo is falsifiable.** It asserts the legacy program's exact output for `"123"`, four malformed inputs being refused, separators collapsing to the same digits, Luhn totals of 30 versus 31 for one changed digit, six published check digits regenerated and then broken on purpose, deterministic generation at two lengths, nine prefixes classified into six brands plus unknown, the length policy rejecting a 15-digit Mastercard and a 16-digit Amex while accepting a 13-digit Visa, a Luhn-valid unknown-brand number reported invalid, masks revealing at most four digits at the true length, reveal bounds enforced, four published groupings, and 17 bundled rows whose brand and checksum claims all agree with the code.

No network, no gateway, no third-party library. No card number leaves the process.

---

# ✨ Features

- `digits` — separator-aware normaliser that refuses letters rather than ignoring them
- `try_digits` — the same, returning `""` instead of raising
- `luhn_sum` / `luhn_valid` — the checksum, with the weighted total exposed
- `check_digit` / `with_check_digit` — recover or append the check digit
- `generate` — a deterministic Luhn-valid number for any prefix and length
- `brand` — six schemes by issuer identification number, plus `Unknown`
- `length_ok` — each brand's own allowed lengths, as a separate question
- `format_number` — Amex 4-6-5, Diners 4-6-4, everything else in fours
- `mask` — positional masking with a hard floor: short input reveals nothing
- `legacy_mask` — the original four-line behaviour, kept for the comparison
- `check` / `describe` — one dict, one safe line
- `load_cards` — CSV reader that recomputes every claim instead of trusting it
- `data/cards.csv` — 17 rows: 9 valid, 8 deliberately rejected
- CLI: `--check`, `--mask`, `--generate`, `--reveal`, `--file`, `--json`, `--quiet`
- Exit `2` on unreadable input; `--demo` always returns `0`
- 165 passing pytest tests

---

# 📂 Folder Structure

```text
Card_Payment/
│
├── src/
│   ├── main.py      # CLI: list, check, mask, generate
│   └── card.py      # digits, Luhn, brand, length, mask, demo
│
├── tests/
│   └── test_card.py
│
├── data/
│   └── cards.csv     # 17 rows: published test numbers and corruptions
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 02_Udemy_Course_Projects/Card_Payment

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: legacy leak, Luhn, check digits, brands, lengths, masks
python src/main.py --demo

# The bundled 17 cards, masked
python src/main.py

# One verdict, with the reason when it fails
python src/main.py --check 4111111111111111
python src/main.py --check 4111111111111112
python src/main.py --check 79927398713

# Masked display only
python src/main.py --mask 378282246310005
python src/main.py --mask 4111111111111111 --reveal 2

# A deterministic, Luhn-valid test number
python src/main.py --generate 4111 16

# Your own file, machine-readable
python src/main.py --file cards.csv --json out.json --quiet
```

**Data format** (`data/cards.csv`) — `number,brand,luhn,note`, `#` starts a comment:

```text
number,brand,luhn,note
4111111111111111,Visa,yes,classic Visa test number
378282246310005,Amex,yes,15 digits printed 4-6-5
79927398713,Unknown,yes,Luhn-valid but no brand and no allowed length
123,Unknown,no,too short to mask - the legacy leak case
```

The loader recomputes the brand and checksum for every row and reports whether the file's own claim agrees, so the data is checked rather than assumed.

**Exit codes:** `0` = the command ran · `2` = unreadable input (empty, letters, out-of-range reveal, missing file).

---

# 🧠 How It Works

```text
raw input
   │
   ▼
digits()  ──►  "378282246310005"          spaces, hyphens, dots removed
   │                                       letters refused, not ignored
   ├── luhn_sum()   ──► 60                every second digit doubled from the right
   ├── brand()      ──► "Amex"            prefix ranges from the schemes
   └── length_ok()  ──► True              15 is an Amex length
             │
             ▼
      valid = brand known AND length ok AND checksum ok
```

Details worth knowing:

- **The check digit sits in a non-doubled position.** That is why appending one digit can always make the total a multiple of ten, and why `check_digit` can be a ten-iteration loop instead of algebra.
- **Doubling and subtracting nine is the same as summing the digits.** `2 * 7 = 14 -> 5`, and `1 + 4 = 5`. Written either way, the total is identical.
- **Brand is prefix only.** `brand("37")` is `"Amex"` even though two digits cannot be a card. Brand, length and checksum are three separate answers, and `check()` is the only place they are combined.
- **The mask is positional, not textual.** It replaces the first `n - 4` digits with `*` and keeps the rest in place, then regroups. That is why the output length always equals the input length.
- **Short input is masked completely.** `len(text) <= reveal` returns all stars rather than revealing everything — the exact inversion of `text[-4:]`.
- **`generate` fills with zeros.** `generate("4111", 16)` is always `4111000000000008`; nothing random, nothing to reproduce.
- **`legacy_mask` is shipped on purpose.** A demo that only showed the fix would be untestable; keeping the broken version lets the difference be asserted.

**What this does not do.** It does not check that a card exists, has funds, or belongs to anyone. Luhn catches single-digit typos and most adjacent transpositions — it does not catch `09` typed for `90`, and it says nothing about whether an issuer will authorise the charge. Those limits are stated rather than implied.

---

# 🛠 Technologies

- Python 3 standard library: `argparse`, `json`, `pathlib`, `tempfile`, `contextlib`
- pytest

No `stripe`, no gateway, no network access.

---

# 📚 Concepts Covered

- The Luhn checksum: weighting, modular total, check digit recovery
- Why a checksum is necessary but not sufficient
- Issuer identification numbers and prefix-range classification
- Length policy as a separate decision from checksum
- Masking by position versus slicing, and the leak in `text[-4:]`
- Display grouping per scheme (4-6-5, 4-6-4, fours)
- Deterministic generation of test data
- Validating data against recomputation instead of trusting a file
- Failing loudly on letters instead of silently dropping them
- Self-asserting demos with negative controls

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**165 tests passed** covering digit normalisation (plain, spaced, dashed, dotted, empty, separators-only, letters, non-strings, `try_digits`); Luhn totals for Visa, Mastercard, Amex and the classic example; one-digit corruption; empty and lettered input returning `False` rather than raising; six published check digits, all verified end to end; generation at four lengths plus prefix-too-long, length-too-short and type errors; fifteen prefix classifications including the `2221-2720` range and eight boundaries that must stay `Unknown`; the length table for all six brands plus the disjoint cases; four published groupings and separator-insensitivity; masking at 16, 15, 14, 13, 5 and 3 digits, with `reveal` 0 and 2, bounds `-1`, `7` and a string, and the invariant that no masked string contains its full number; `check` on valid, bad-checksum, unknown-brand and bad-length numbers; `describe` naming each failure; the bundled file's 17 rows, nine valid, every claim agreeing, plus missing-file, short-row, wrong-header, header-only and comment-skipping cases; demo determinism and the guarantee that the demo never prints a full number; and every CLI path.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
