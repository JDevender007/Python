<div align="center">

# 🧮 Calculator GUI

### The legacy calculator was `return eval(expression)` — so `2 ^ 3` was **1**, `0.1 + 0.2` showed **seventeen digits**, and `10 / 0` killed the click handler. This one tokenizes the expression, parses it with real precedence, and evaluates in `Decimal`: **8**, **0.3**, and a sentence instead of a traceback.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

```python
def calculate(expression):
    return eval(expression)
```

**1 → `eval` evaluates Python, not arithmetic.** `^` is XOR, so `2 ^ 3` is **1** where every
calculator on earth says **8**. `2 ^ 3 ^ 2` is **(2^3)^2 = 3**, not `2^(3^2) = 512`. And an
expression typed into a window can call any name in scope.

**2 → A float is not a decimal.** `0.1 + 0.2` is `0.30000000000000004`, and the label that
prints it is the only place the error is visible:

```text
0.1+0.2            0.30000000000000004      0.3
2^3                1                        8
2 ^ 3 ^ 2          3                        512
1/3                0.3333333333333333       0.33
2.675              2.675                    2.68
```

**3 → `1 / 0` raises, and `1 / 3` never ends.** The first kills the click handler. The second
prints seventeen digits that the next click will multiply by.

**4 → A display has a width.** A result with more digits than the label holds is printed as
`9.899999999999901e+15`, which is not a number anyone can read back.

**5 → Rounding is a decision, not a default.** `round(2.675, 2)` is `2.67` — the nearest
double is below the tie, so Python rounds the *double*. A calculator that shows money has to
say which way a tie goes, and write it down.

So this module evaluates the expression itself: a tokenizer that knows numbers, six operators
and brackets; a recursive-descent parser where `*` binds tighter than `+`, `^` is right
associative, and unary minus sits above power; `Decimal` arithmetic at 34 working digits; and
a `render` that rounds **half-up** to a stated number of places and **refuses** a result that
will not fit.

The demonstration is offline: one bundled file of twelve expressions. Standard library only.

---

# ✨ Features

- `tokenize()` — numbers with one optional decimal point, six operators, two brackets; refuses
  a second point, a lone point, a letter, and an empty expression, each with its position
- `Parser` — `expression → term → unary → power → primary`, a depth limit of 32, and a
  leftover-token check, so `2+3)` is refused instead of silently truncated
- `evaluate()` — `Decimal` at 34 working digits; division and remainder by zero are sentences;
  a fractional exponent is refused rather than approximated
- `render()` — **half-up**, trailing zeros stripped, `-0` shown as `0`, and a width check that
  refuses instead of printing exponent notation
- `divide_half_up()` — the same digits from integers alone (`divmod`, then `2 * remainder >=
  denominator`), as a cross-check on `Decimal.quantize`
- `legacy_calculate()` — `eval` with no builtins, so the XOR and the float are reproducible
- `Result` — the expression, what `eval` said, what the display shows, and `differs()`, which
  asks whether the disagreement *survives* rounding
- `audit` — eleven named checks, every one falsifiable by corrupting a row
- CLI: `--expressions`, `--expression`, `--places`, `--tokens`, `--legacy`, `--audit`,
  `--json`, `--quiet`, `--demo`
- 137 passing pytest tests

---

# 📂 Folder Structure

```text
01_Calculator_GUI/
│
├── src/
│   ├── main.py        # CLI: the bundle, one expression, tokens, the audit
│   └── calculator.py  # tokens, the parser, Decimal arithmetic, the display
│
├── tests/
│   └── test_calculator.py
│
├── data/
│   └── expressions.txt  # twelve expressions the two calculators read differently
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 09_Desktop_Applications/01_Calculator_GUI

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: twelve expressions, both calculators, eleven checks
python src/main.py --demo

# Every expression, with the exact answer
python src/main.py

# What `eval` said beside what the calculator says
python src/main.py --legacy

# One expression
python src/main.py --expression "2 ^ 3 ^ 2"
python src/main.py --expression "1/3" --places 8

# The tokens of one expression
python src/main.py --expression "-2 ^ 2" --tokens

# Every check
python src/main.py --audit

# All results as JSON
python src/main.py --json results.json
```

**Exit codes:** `0` = every expression was read and every check held · `1` = an audit check
failed (e.g. `--expression "2+2" --audit`, where one row cannot satisfy checks about eleven
others) · `2` = a missing bundle, a bundle with a `#` comment, an empty expression, or a place
count outside 0-12.

---

# ⚙️ How It Works

```text
tokenize(text)
  ├── digits and one optional '.'  -> number
  ├── + - * / % ^                  -> operator
  ├── ( )                          -> open / close
  └── anything else                -> refused, with the offset

expression  := term (('+' | '-') term)*
term        := unary (('*' | '/' | '%') unary)*
unary       := ('+' | '-') unary | power
power       := primary ('^' unary)?
primary     := number | '(' expression ')'
```

Details worth knowing:

- **`^-1` is allowed, `^0.5` is not.** A whole exponent is exact in `Decimal`; a fractional one
  needs a root, and a calculator that silently approximates it is lying about the answer.
- **`-2^2` is `-4`.** Unary minus sits *above* power in the grammar, which is what Python does
  and what the expression looks like it means. `9 - 2^2` and `-2^2 + 9` both give 5.
- **The display rounds, the arithmetic does not.** Working precision is 34 digits; `render`
  takes the last step, so `1/3` is exact internally and `0.33` on the label.
- **Half-up is written out twice.** `Decimal.quantize(..., ROUND_HALF_UP)` and
  `divide_half_up()` on integers agree on `2.675`, `1.005`, `-2.675`, `0.125` and `1234.5`.
- **Width is refused, not truncated.** A label that shows `9.9e+15` has stopped being a
  calculator, so `render` says how many digits the result needs.
- **A negative zero is a zero.** `-0.004` at two places is `0`, not `-0`.
- **A broken row is a `FAIL`.** Every check runs behind a guard, and the negative controls
  clone a `Result` past its constructor with `object.__new__`, because `Result` refuses to be
  built wrong on purpose.

---

# 🧪 Technologies

- Python 3 standard library: `decimal`, `dataclasses`, `pathlib`, `argparse`, `json`,
  `contextlib`
- pytest 9.1.1

No `eval` in the calculator's own path, no numeric library, no GUI toolkit, no network.

---

# 📚 Concepts Covered

- Why `eval` is not an expression evaluator, and what `^` means in Python
- Tokenizing with positions, so an error can point at a character
- Recursive descent: precedence, associativity, unary operators, bracket depth
- `Decimal` versus `float`, working precision versus display precision
- Half-up rounding on `Decimal` and on integers, and why `round()` is neither
- Refusing an unrepresentable answer instead of printing exponent notation
- `-0` as a display artefact of a rounding decision
- Audits whose negative controls corrupt the data rather than mock a function

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**137 tests passed** covering token construction and its three refusals, tokenizing numbers,
decimals, brackets and every refusal, fifteen arithmetic cases, precedence and associativity,
depth limits, `render` and its eight refusals, `divide_half_up` and its five, the legacy path
including its `ZeroDivisionError` and `NameError`, the bundle parser and its six refusals,
`Result` and its four refusals, `differs()` on four shapes, `compare`, eleven audit checks each
with a negative control, the demo, and every CLI mode including four exit-code-2 paths and one
exit-code-1 path — **37 `pytest.raises` refusals** in all.

---

# 🎯 Learning Outcomes

- Explain what `eval("2 ^ 3")` does and why a calculator must not use it
- Say why `0.1 + 0.2` is not `0.3` in binary floating point, and what to use instead
- Read `2 ^ 3 ^ 2` as right-associative and `-2 ^ 2` as `-(2 ^ 2)`
- Decide that a division by zero is an answer the calculator owes the user
- Round a tie in a stated direction, and show why `round()` is not that direction
- Refuse a result that cannot be displayed instead of printing something unreadable
- Cross-check a decimal rounding against integer arithmetic
- Audit a claim about numbers by handing in a row that has the wrong number

---

# 🚀 Future Improvements

- A history of the last twenty results, each kept at working precision
- A memory register, so `M+` is exact rather than a rounded display value
- Functions (`sqrt`, `ln`) evaluated at a stated precision, with a refusal when the result is
  irrational
- A keyboard layout and a real Tkinter window in front of the same `Calculator`
- A `Fraction` mode, so `1/3` can be shown as a fraction when that is the honest answer

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
