<div align="center">

# 🔐 Password Checker

### The course version printed **"Password Changed"** when the two passwords were *identical*. It accepted `"a"` as a new password, and its only policy was whether the letters were upper case.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

The course program was nine lines:

```python
pwd1 = 'myPass'
pwd2 = 'myPass'

if pwd1 == pwd2:
    print("Password Changed")
elif pwd1.casefold() == pwd2.casefold():
    print("Please check cases and try again")
else:
    print("Password do not match")
```

**The equality test is backwards.** If the new password equals the old one, the change did not happen. The program reports success for exactly the case it should reject, and its corollary is worse — `pwd1 = 'a'` with `pwd2 = 'a'` prints "Password Changed", so a single character is a valid new password.

**Case is the entire policy.** `'myPass'` against `'MYPASS'` is refused with "Please check cases", which is a rejection based on case rather than on strength — and any differing string at all is accepted as a change, however weak.

**There is no input.** Both values are constants.

The replacement answers the question the original was reaching for: *should a system accept this password?*

| Rule | Default |
| --- | --- |
| length | at least 8 characters |
| classes | at least 3 of lower, upper, digit, symbol |
| repeats | no three identical characters in a row |
| sequences | no four consecutive alphabet or keyboard characters |
| common | not in the bundled list, even after leet substitution |
| identity | must not contain the username or email local part |
| entropy | at least 40 bits by the observed-pool estimate |

**Leet substitution is what makes the common-password check work.** `'P@ssw0rd!'` is reduced to `'password'` *before* the comparison, so swapping an `o` for a zero and an `a` for an `@` buys nothing. The reduction happens before punctuation is dropped, so `@` becomes `a` instead of disappearing:

```text
P@ssw0rd!  ->  password     (exact match, flagged)
password1  ->  passwordi    (prefix 'password', flagged)
Tr0ub4dor&3 -> troubadore   (not common)
```

Digits are matched in their plain form too, because `'123456'` is common *as digits*.

**Entropy is an upper bound, and the code says so.** `len × log₂(pool)` assumes every character was drawn uniformly at random. `'password'` scores 37.60 bits and is still a terrible password, which is exactly why the dictionary check is separate and does not depend on the number.

**The class rule is crude, and the demo admits it.** `'correct horse battery staple'` is 28 characters and 164.71 bits — and is *rejected* for having one character class. That is a property of any class-count policy, not a bug in this one, and the policy object is configurable so the rule can be relaxed deliberately.

**Everything is falsifiable.** The demo shows the legacy verdict on an unchanged password and on `'a'`, rejects six weak passwords for six *distinct* codes, catches a username and an email's dotted local part, pins the leet reduction and the prefix rule, checks that `'alert123!X'` and `'aabb'` are **not** flagged (no false positives), pins entropy at 14.10 and 37.60 bits, and verifies the bundled 40-entry list matches itself.

Standard library only. No password is ever written to disk.

---

# ✨ Features

- `legacy_verdict` — the original three-way message, with its backwards test
- `Policy` — frozen dataclass; length, classes, entropy floor and four toggles
- `classify` / `pool_size` — character classes in a fixed order
- `entropy_bits` — `len × log₂(pool)`, documented as an upper bound
- `has_repeat` / `has_sequence` — 3-in-a-row and 4-consecutive detection
- `plain` / `skeleton` — list form and de-leeted form
- `is_common` — exact and 6+ character prefix matching on both forms
- `usernames_from` — username, email local part, plus-addressing
- `check` — every finding plus a 0–100 score and a label
- `data/common.txt` — 40 common passwords
- CLI: `--check`, `--identity`, `--policy relaxed|default|strict`, `--min-length`, `--min-classes`, `--min-entropy`, `--list-common`, `--legacy`, `--json`, `--quiet`
- Exit `0` accepted · `1` rejected · `2` bad input; `--demo` always returns `0`
- 144 passing pytest tests

---

# 📂 Folder Structure

```text
Password_Checker/
│
├── src/
│   ├── main.py    # CLI: check, identities, profiles, legacy mode
│   └── policy.py  # classes, entropy, patterns, common list, scoring
│
├── tests/
│   └── test_policy.py
│
├── data/
│   └── common.txt # 40 common passwords
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 02_Udemy_Course_Projects/Password_Checker

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo
python src/main.py --demo

# Check a password
python src/main.py --check "Tr0ub4dor&3"

# What the original program would have said
python src/main.py --legacy myPass:myPass
python src/main.py --legacy myPass:MYPASS

# With an identity to compare against
python src/main.py --check "Alice2024!" --identity alice

# Profiles and overrides
python src/main.py --check "abc1" --policy relaxed
python src/main.py --check "Tr0ub4dor&3" --policy strict
python src/main.py --check "alllower" --min-length 4 --min-classes 1

# The dictionary
python src/main.py --list-common
```

**Exit codes:** `0` = accepted (or the information was printed) · `1` = rejected · `2` = empty password, non-text input, or a malformed `--legacy` argument.

Note: passing a password on the command line puts it in your shell history. For real use, read it from a file or a prompt; this demo keeps the interface simple on purpose.

---

# 🧠 How It Works

```text
password
   │
   ├── classify()      -> lower / upper / digit / symbol, in order
   ├── entropy_bits()  -> len * log2(pool), upper bound
   ├── has_repeat()    -> aaa
   ├── has_sequence()  -> abcd, dcba, 1234, qwer
   ├── is_common()     -> plain and de-leeted, exact and 6+ prefix
   └── identity        -> username or email local part inside the password
          │
          ▼
      findings [too_short, too_few_classes, repeated_characters,
                sequence, common_password, contains_username, low_entropy]
          │
          ▼
      score = length + classes + entropy bonus - penalties
```

Details worth knowing:

- **`check` never stores the password.** `Verdict` holds the length, classes, entropy, score and findings — no plaintext — so the JSON output is safe to log.
- **`skeleton` folds before dropping.** Translating `@→a` after removing non-alphanumerics would lose the substitution entirely.
- **The prefix rule requires six characters.** `'admin'` (five) matches only exactly, so `'adminxyz'` is not flagged, while `'secretxyz'` is flagged against `'secret'`. The demo tests both sides.
- **Sequence length is four, not three.** Using three would flag ordinary words like `'alert123'` because it contains `'ert'`. The test suite pins that negative case.
- **Scores are explained, not magic.** 2.5 points per character (capped at 40), 10 per class, an entropy bonus (capped at 20), minus 15 per finding (25 for `too_short`).
- **Identity matching is case-insensitive** and covers `bob.smith@example.com` → `bob.smith`, `bobsmith` and `bob` (via `+` addressing).

---

# 🛠 Technologies

- Python 3 standard library: `math`, `dataclasses`, `pathlib`, `argparse`, `json`, `contextlib`, `io`
- pytest

No regex engine, no network, no password manager integration.

---

# 📚 Concepts Covered

- Reading a comparison backwards: equality as "changed"
- Policy as data (a frozen dataclass) rather than a chain of `if`s
- Character-class counting and why it rejects passphrases
- Entropy as an upper bound, with its assumptions stated
- Leet substitution and normalisation order
- Prefix matching with a minimum length to control false positives
- Negative controls: proving a detector does **not** fire
- Identity-adjacent password rules
- Scoring with documented weights
- Exit codes for `0` accepted / `1` rejected / `2` error

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**144 tests passed** covering the legacy verdict's four branches, classification (single class, all four, duplicates, empty, space), pool sizes, entropy (three pinned values, growth with length and pool, rounding, non-text), repeat detection (three, two, custom lengths), sequence detection (forward, reverse, digits, keyboard rows, the four-character threshold and its three-character variant, a negative case), `skeleton` and `plain`, common-list matching (exact, leet, prefix, digit strings, injected sets, the six-character prefix boundary), the bundled list's shape and count, identity extraction (nothing, username, email, plus-addressing, short locals), policy validation and immutability, `check` for accepted and rejected passwords with each of the seven finding codes, every toggle, injected dictionaries, purity and JSON output without plaintext, label boundaries, demo determinism, and every CLI mode including profiles, overrides, `--legacy`, JSON and quiet.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
