# Password Strength Analyzer

Entropy is a property of a random string, not of the string someone chose. The legacy scorer is
three lines and a magic constant:

```python
size = 1
for name in classes: size *= CHARSET_SIZES[name]
entropy = len(password) * math.log2(size)
score = int(entropy / 1.28)
```

Each line is a defect, and each one produces a number that looks like a grade.

**1. A character set is the sum of its classes, not the product.** A password mixing lowercase and
uppercase draws from 26 + 26 = **52** possible characters. Multiplying gives **676**, so `log2`
charges 9.4 bits per character instead of 5.7. `Password2024` uses three classes, so the legacy
charset is `26 * 26 * 10 = 6760` -- a claim that 6760 different characters exist, when ASCII offers
**95**. The legacy figure for the same 12 characters is **153 bits** against **71** for the real
alphabet.

**2. Entropy assumes every character was drawn at random.** `Password2024` is a dictionary word, a
capital and a year. The formula cannot see any of that, so it awards a score of **100/100** and the
label "very strong" to a password that a rule-based guesser reaches in a few thousand attempts. The
rebuild keeps the random-string figure as a *ceiling*, subtracts **12 bits** of recognised
structure, and calls the result **59 guess bits** -- `fair`. It never pretends the deduction is a
measurement.

**3. Crack time is integer work, not float arithmetic.** `2 ** entropy / 2` overflows into
imprecision long before it overflows into an exception, and `int(value)` in the formatter silently
drops the digits that matter. The rebuild computes `1 << (bits - 1)` guesses and divides by an
integer rate, so a run is reproducible to the second and two runs print identical bytes.

## What this project teaches

- An alphabet is the union of its classes: 52 characters, never 676
- Why a product of class sizes can claim more characters than exist
- Entropy as an upper bound for *random* strings, and why chosen strings beat it
- Structure as a documented deduction from a ceiling, not a second invented scale
- A score that *is* the bit count, capped -- no hidden `1.28` divisor
- Half-open score bands and the off-by-one at each boundary
- Integer keyspaces (`1 << (bits - 1)`) and integer division for durations
- Printing very large durations as an order of magnitude instead of a float
- Keeping the password out of every line of output while reporting its length
- Auditing a report against a recomputation through an injected analyser

## How to run

```
python src/main.py --demo
python src/main.py --demo --quiet
python src/main.py --file data/passwords.csv --json out.json
python src/main.py --file data/passwords.csv --audit
python -m pytest tests -q
```

`--file` names a CSV with `label,password` columns. Exit code `2` means the input was refused -- a
missing file, non-ASCII bytes, a missing column, a blank password, a duplicated label, or a
password longer than 256 characters.

## Project structure

```
Password_Strength_Analyzer/
├── README.md
├── requirements.txt        # pytest==9.1.1
├── .gitignore
├── data/
│   └── passwords.csv       # 6 demo secrets, all invented for this lab
├── src/
│   ├── analyzer.py         # classes, penalties, crack time, checks, demo
│   └── main.py             # argparse only
└── tests/
    └── test_analyzer.py    # 177 tests
```

## What the demo shows

| label | len | classes | charset | legacy charset | random | penalty | guess | band |
| --- | --: | --: | --: | --: | --: | --: | --: | --- |
| password | 8 | 1 | 26 | 26 | 38 | 24 | 14 | very weak |
| decorated | 12 | 3 | 62 | 6760 | 71 | 12 | 59 | fair |
| leet | 11 | 4 | 95 | 223080 | 72 | 4 | 68 | strong |
| passphrase | 28 | 2 | 59 | 858 | 165 | 0 | 165 | very strong |
| repeats | 12 | 1 | 26 | 26 | 56 | 15 | 41 | weak |
| qwerty2024 | 10 | 2 | 36 | 260 | 52 | 16 | 36 | weak |

- `decorated` is **`Password2024`**: the legacy model says **100/100 very strong**, the rebuild says
  **59/100 fair** after deducting a dictionary word and a year
- `leet` gets the worst legacy inflation of all: the product claims **223080 characters**, so 72
  real bits become **195**
- `passphrase` is the counter-example: 28 characters, no recognised structure, **165 bits**
- `password` matches the common list, so 38 random bits become **14**: a throttled attacker reaches
  it in about **a minute**
- 26/26 audit checks pass, with negative controls that hand the audit the legacy product and watch
  the pinned bits and the recomputation disagree

## Requirements

Python 3.10+, standard library only (`math`, `string`, `csv`, `argparse`, `dataclasses`). Tests need
pytest==9.1.1. Nothing is uploaded, logged or stored; the CSV holds invented demo strings only.

---
**Devender J** -- https://github.com/JDevender007
