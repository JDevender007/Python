<div align="center">

# 🐣 Beginner Level Projects

### Five offline projects that take the three things every beginner reaches for — `eval()`, a `dict`, and `random.choice` — and replace each with the real thing underneath it: a parser, a validated repository, and an entropy budget.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Projects](https://img.shields.io/badge/Projects-5-success?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

"Beginner" here does not mean "toy". It means the problem is small enough to finish, and every design decision is still visible. Each project starts from the shortcut a first version would take, and then shows what that shortcut costs:

- **Calculator_CLI** does not call `eval()`. It writes the tokenizer, the shunting-yard parser and the RPN stack machine, because that is where precedence, associativity and unary minus actually live. `-2 ^ 2` is `-4` and `(-2) ^ 2` is `4` because the parser says so, not because a Python quirk happens to agree.
- **Contact_Book** is not a `dict` of names. It is a frozen record that validates its own email and phone, plus a repository with two indexes that stay consistent through updates, and a merge with an explicit conflict policy.
- **Expense_Tracker** does not call `max()` and declare it an anomaly. It scores each charge against its own category with a median/MAD modified z-score, so one huge dinner cannot hide itself by inflating the standard deviation.
- **Number_Guessing_Game** does not stop at "guess higher". It plays all one hundred secrets and checks the `ceil(log2(100)) = 7` bound, then prints the attempt distribution that proves it.
- **Password_Generator** does not trust a length. It counts the pool, computes the bits, and refuses to call sixteen `a`s strong even though the arithmetic says `75.21` bits.

Every project runs on bundled data, prints a `Cross-checks OK` line naming what was actually verified, exits `0`, and has a `--demo --quiet` mode that prints nothing at all.

---

# 🎯 Learning Objectives

- Tokenize an expression and convert it to reverse polish notation with the shunting-yard algorithm
- Encode operator precedence and associativity in one table rather than in scattered `if`s
- Handle unary operators as ordinary operators with a renamed symbol
- Validate a record at construction so invalid state cannot exist afterwards
- Keep two indexes consistent through insert, update and delete
- Search with AND semantics over a derived haystack
- Merge two data sets under an explicit conflict policy and report the outcome
- Round money at the boundary instead of at display time
- Compute robust outlier scores with the median and MAD
- Refuse to judge a sample that is too small to support a verdict
- Prove an algorithm's bound by exhaustive replay rather than assertion
- Make randomness reproducible by injecting a seeded RNG
- Estimate password entropy from the pool and check it against observed patterns
- Generate output that satisfies every constraint by construction, not by retry

---

# 📂 Projects

No. | Project | Description | Status
--: | --- | --- | :---:
01 | Calculator_CLI | Tokenizer, shunting-yard parser to RPN, stack evaluator, 8 functions, history with undo, batch file mode. | ✅
02 | Contact_Book | Validated contacts, dual-index repository, AND search, two merge policies, JSON and CSV round-trips. | ✅
03 | Expense_Tracker | CSV loader, monthly and category aggregates, per-month budgets, median/MAD outlier detection. | ✅
04 | Number_Guessing_Game | Bisection solver, naive comparison, seeded rounds, attempt statistics, golden round file. | ✅
05 | Password_Generator | Policy object, guaranteed class coverage, entropy and label, pattern warnings, bounded history. | ✅

---

# 💡 Concepts Covered

- Lexical analysis with a compiled regular expression
- Typed tokens and position-aware error messages
- Shunting-yard conversion and postfix evaluation
- Operator precedence, associativity, and unary operators
- Stack machines and arity checking during parsing
- Frozen dataclasses as self-validating value objects
- Normalisation at the boundary (strip, collapse, case-fold)
- Dual-index repositories and index consistency
- Exception hierarchies with specific messages
- Validation before mutation, and atomic failure
- AND search over a derived haystack
- Merge with a conflict policy and an auditable report
- CSV and JSON serialisation with round-trip tests
- Money rounding and per-line error reporting
- Robust statistics: median, MAD, modified z-score
- Breakdown points and why the mean hides outliers
- Binary search as an optimal strategy, and the `log2` bound
- Seeded pseudorandomness and golden-file testing
- Entropy as `length * log2(pool)`, and its assumptions
- Guaranteed sampling (plant, fill, shuffle) versus rejection sampling
- Secrets hygiene: summaries that never contain the payload

---

# 📁 Repository Structure

```text
01_Beginner_Level_Projects/
│
├── Calculator_CLI/
├── Contact_Book/
├── Expense_Tracker/
├── Number_Guessing_Game/
├── Password_Generator/
│
└── README.md
```

Each project contains:

```text
Project_Name/
├── src/              # main.py + library module
├── tests/            # pytest test suite
├── data/             # bundled deterministic data
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠 Technologies

- Python 3 standard library: `re`, `math`, `csv`, `json`, `statistics`, `random`, `dataclasses`, `datetime`, `pathlib`, `argparse`, `contextlib`
- pytest 9.1.1

No third-party runtime dependencies, no database, no network access.

---

# 📈 Progress

| Project | Status |
| --- | :---: |
| Calculator CLI | ✅ |
| Contact Book | ✅ |
| Expense Tracker | ✅ |
| Number Guessing Game | ✅ |
| Password Generator | ✅ |

**Completed:** **5 / 5 Projects** · 418 passing tests

---

# ▶️ Quick Start

```bash
cd 01_Beginner_Level_Projects/Calculator_CLI

python src/main.py --demo     # offline demo
python -m pytest tests/ -q    # run the tests
```

Each project follows the same shape: `python src/main.py --demo` for a self-checking offline run, `python -m pytest tests/ -q` for the suite, and `--quiet` to silence both.

---

# 📚 Skills Developed

- Implementing a parser from the grammar up instead of reaching for `eval()` or `ast`
- Designing validation that makes invalid states unrepresentable
- Keeping derived indexes consistent across every write path
- Choosing a robust statistic and understanding when it applies
- Building demos that assert falsifiable properties, with a negative control beside every happy path
- Making randomness reproducible so results can be re-derived later
- Testing at the level of "what must be true" rather than "what the code does today"
- Writing 56–102 pytest cases per project, including every error message and CLI flag

---

# 🚀 Key Learning Outcomes

- Parse and evaluate arithmetic with correct precedence, associativity and unary handling
- Store validated contacts and search, merge and export them without corrupting the indexes
- Aggregate spending and identify a genuine outlier in a category of five numbers
- Explain why bisection needs 7 guesses for 100 candidates and prove it by replay
- Generate a password that provably meets a policy, and score one that does not

---

# 🔮 Future Enhancements

- Variables and assignment in the calculator, still without `eval()`
- Contact groups and fuzzy name matching
- Recurring expenses and year-over-year comparisons
- A human-style guessing strategy to compare against bisection
- Passphrase generation from a bundled word list with a dice-roll entropy model

---

# 🤝 Contributions

Contributions, issues and feature requests are welcome. Feel free to open an issue or submit a pull request.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this category useful, consider giving this repository a star.

</div>
