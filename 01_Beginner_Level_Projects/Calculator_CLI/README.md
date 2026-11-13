<div align="center">

# 🧮 Calculator CLI

### An arithmetic calculator written the long way round: a tokenizer, a shunting-yard parser that emits reverse polish notation, and an RPN evaluator — no `eval()` anywhere.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Offline-No%20Network-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

`eval("2 + 3 * 4")` works, and that is exactly why it teaches nothing: it hides the three decisions a calculator has to make — how to split the text, how to respect precedence, and how to apply an operator to the right two numbers. This project makes all three explicit.

**Stage 1 — tokenize.** A single regex splits the input into typed tokens (`number`, `name`, `operator`, `(`, `)`, `,`) and refuses anything it cannot explain:

```text
"max(2, 7) - 1"  ->  [name:max] [(] [number:2] [,] [number:7] [)] [op:-] [number:1]
"2 & 3"          ->  CalculatorError: unexpected character '&' at position 2
```

**Stage 2 — shunting-yard.** Dijkstra's algorithm moves operators onto an output queue in postfix order, using a precedence table, and remembers one *frame* per open parenthesis so it knows how many arguments a call received:

```text
"2 + 3 * 4"    ->  2 3 4 * +
"(2 + 3) * 4"  ->  2 3 + 4 *
"2 ^ 3 ^ 2"    ->  2 3 2 ^ ^        ^ is right-associative, so 512
"-2 ^ 2"       ->  2 2 ^ u-         unary minus binds looser than ^, so -4
"(-2) ^ 2"     ->  2 u- 2 ^         parentheses win, so 4
```

Unary `-` and `+` are not a special case bolted on afterwards: when an operator appears where a value cannot start, it is renamed to `u-` / `u+` and given its own precedence row. That single rule is why `2 - -3` is `5` and `2 * -3` is `-6`.

**Stage 3 — evaluate.** A stack machine pops the numbers an operator needs, applies it, and pushes the answer. Arity is checked against the table, not guessed from how many values happen to be on the stack:

| Failure | Message |
| --- | --- |
| `1 / 0` | `division by zero` |
| `1 % 0` | `modulo by zero` |
| `sqrt(-1)` | `sqrt(-1) failed: math domain error` |
| `(-2) ^ 0.5` | `cannot raise -2.0 to 0.5` |
| `max(1)` | `max() takes 2 argument(s), got 1` |
| `sqrt()` | `sqrt() takes 1 argument(s), got 0` |
| `(2 + 3` | `unbalanced '('` |
| `2 + 3)` | `unbalanced ')'` |
| `2 3` | `missing operator before '3'` |
| `2(3)` | `missing operator before '('` |
| `foo(1)` | `unknown name 'foo'` |
| `sqrt 4` | `sqrt() used without parentheses` |
| `* 2` | `operator '*' is missing an operand` |
| `(1, 2)` | `misplaced comma` |
| `()` | `empty parentheses` |

**Everything in the demo is falsifiable.** It checks ten documented expressions against their documented values, the exact token kinds of a call, the exact postfix form of two expressions, that all seven malformed inputs above are rejected with the right message, that `1 / 0` raises instead of returning `inf`, that history undo/clear/total behave, that a batch keeps going after a bad line, and that `0.1 + 0.2` prints as `0.3`. The `--quiet` path is checked separately: it prints nothing at all.

No network, no `eval()`, no third-party maths library.

---

# ✨ Features

- Hand-written tokenizer with typed `Token` records and position-aware errors
- Shunting-yard parser producing reverse polish notation
- Full precedence table: `+ -` < `* / %` < unary `+ -` < `^` (right-associative)
- Unary minus handled by the parser, so `-2 ^ 2 == -4` and `(-2) ^ 2 == 4`
- Parentheses at any depth, including nested calls: `abs(abs(-5))`
- Eight functions with checked arity: `sqrt`, `abs`, `round`, `log`, `exp`, `min`, `max`, `pow`
- Constants `pi` and `e`
- Decimal and exponent number forms (`3.5`, `.25`, `1e-3`)
- `Calculator` session with history, `last()`, `undo()`, `clear()` and `total()`
- `evaluate_lines` batch runner that skips comments and blank lines and never aborts on a bad line
- `format_value` output with no floating-point noise and no exponents
- CLI with `--expr` (repeatable), `--file`, `--json`, `--demo` and `--quiet`
- Exit `0` when every expression evaluated, `2` when any failed
- 100 passing pytest tests

---

# 📂 Folder Structure

```text
Calculator_CLI/
│
├── src/
│   ├── main.py        # CLI: --expr, --file, --json, --demo, --quiet
│   └── calculator.py  # tokenizer, shunting-yard, evaluator, session, demo
│
├── tests/
│   └── test_calculator.py
│
├── data/
│   └── expressions.txt   # 19 working expressions + 1 deliberate failure
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 01_Beginner_Level_Projects/Calculator_CLI

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: 10 expressions, precedence, errors, history, 9 cross-checks
python src/main.py --demo

# The bundled expression file (one line fails on purpose)
python src/main.py

# One expression
python src/main.py --expr "2 + 3 * 4"

# Several expressions at once
python src/main.py --expr "sqrt(16) + abs(-3)" --expr "max(2, 7) - min(2, 7)"

# Your own file, with the results written to JSON
python src/main.py --file my_expressions.txt --json out.json

# Silent success, for scripting
python src/main.py --expr "1 + 1" --quiet
```

**File format** (`data/expressions.txt`) — one expression per line; `#` starts a comment:

```text
# Bundled expressions
2 + 3 * 4
sqrt(16) + abs(-3)
max(1)
```

**Exit codes:** `0` = every expression evaluated · `2` = at least one failed, or the file was missing.

---

# 🧠 How It Works

```text
"2 + 3 * 4"
     │
     ▼
tokenize()  ──►  [number:2] [op:+] [number:3] [op:*] [number:4]
     │
     ▼
to_rpn()    ──►  2 3 4 * +          precedence + associativity + arity frames
     │
     ▼
evaluate_rpn() ──► push 2, push 3, push 4, * -> 12, + -> 14
     │
     ├── Calculator.evaluate()  ──►  history.append((text, 14.0))
     ▼
format_value()  ──►  "14"
```

Details worth knowing:

- **`previous` decides unary.** An operator is unary exactly when the token before it could not end a value: start of input, another operator, or `(`.
- **Arity lives in one table.** `FUNCTIONS[name] = (arity, callable)`, and the parser counts arguments per frame, so a wrong count fails before evaluation rather than mid-stack.
- **A frame is opened by `(` and closed by `)`.** Commas increment the frame's argument count; a nested call marks the enclosing frame as having a value, which is what makes `max(1, abs(-2))` work.
- **`%` is `math.fmod`, not Python's `%`.** `-7 % 4` is `-3` here, matching C and most calculators, and the zero divisor is rejected explicitly.
- **`^` is a real power operator.** A negative base with a fractional exponent would return a complex number, so it is converted into a `CalculatorError` instead.
- **Formatting rounds to 10 decimals.** `0.1 + 0.2` prints `0.3`, while `1/3` prints `0.3333333333` rather than `0.3333333333333333`.

---

# 🛠 Technologies

- Python 3 standard library: `re`, `math`, `dataclasses`, `argparse`, `json`, `pathlib`, `contextlib`
- pytest

No `eval()`, no `ast`, no SymPy, no network access.

---

# 📚 Concepts Covered

- Lexical analysis with a single compiled regular expression
- Typed tokens instead of raw strings
- The shunting-yard algorithm and reverse polish notation
- Operator precedence and left/right associativity
- Unary operators expressed as ordinary operators with a renamed symbol
- Stack machines and postfix evaluation
- Function-call arity checking during parsing
- Duck-typed error hierarchy rooted in `ValueError`
- Float formatting without binary-noise artefacts
- Batch processing that isolates failures per line
- Self-asserting demos with negative controls

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**100 tests passed** covering every token kind, whitespace and decimal/exponent forms, every malformed character and length limit, the exact postfix output for precedence, associativity, unary, nested calls, constants and both bracket errors, every arity and placement error, 19 arithmetic evaluations, all eight functions, division and modulo by zero, domain and complex-power errors, formatting and non-finite results, history/undo/clear/total and non-recording of failures, batch evaluation with comments and failures, the bundled data file, demo determinism, and every CLI path including `--json`, missing files and exit code `2`.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
