<div align="center">

# 🔐 Password Generator

### A policy you can read, entropy you can count, coverage that is guaranteed rather than hoped for — and an honest answer for the 16-character password made of sixteen `a`s.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Offline-No%20Network-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

`"".join(random.choice(chars) for _ in range(16))` is a password generator the way a coin flip is a random number generator. It may produce no digits. It may produce sixteen `a`s. And without a policy, there is nothing to check it against.

This project separates the three things that get tangled together.

**1. A policy is data, not a wish.**

```python
Policy(length=16, min_lower=1, min_upper=1, min_digits=1, min_symbols=1,
       forbid_ambiguous=False, name="standard")
```

The four class fields are **minimums**, validated to fit inside the length and to require at least one class at all. `Policy(length=8, min_digits=9)` fails at construction with `the minimums need 9 characters but length is 8` — before a single character is generated.

**2. Coverage is guaranteed.** Required characters are *planted* first, then the rest is drawn from the pool, then the whole list is shuffled:

```text
plant   1 lower + 1 upper + 1 digit + 1 symbol
fill    12 more characters from the 88-character pool
shuffle so the planted characters are not in positions 0..3
```

Three hundred generated passwords are checked against every minimum in the demo, and the test suite repeats it. A generator that only checks the output afterwards would eventually fail the check; this one cannot.

**3. Entropy comes from the pool, not the length.**

```text
pool = 26 lower + 26 upper + 10 digits + 26 symbols = 88
bits = 16 * log2(88) = 103.35        -> excellent
pin  =  8 * log2(10) =  26.58        -> weak
```

That is why the `pin` policy is labelled `weak` despite being "8 characters", and why `CorrectHorse9!` scores `excellent` at 14.

**The uncomfortable case.** `"aaaaaaaaaaaaaaaa"` contains 16 characters from a 26-letter pool, so the naive arithmetic says `75.21 bits` — *strong*. It is obviously terrible, because the arithmetic assumes each character was drawn at random and a repeated run disproves exactly that. So `strength()` computes the bits, then overrides the label:

```text
16 identical letters: 75.21 bits, label weak
warnings: contains a character repeated three or more times
```

The bit count is still reported — it is the *label* that refuses to be fooled. This is the difference between a formula and an answer.

**Everything in the demo is falsifiable.** It checks the 88-character pool and the 103.35-bit figure, that a seed reproduces its password and a different seed does not, that 300 passwords meet every minimum, that minima are minimums rather than exact counts, the `26.58`-bit `pin` policy, 200 ambiguous-free passwords, that `validate("short")` reports all four problems at once, that strength follows the observed pool, three pattern warnings, a bounded history that refuses reuse, six invalid policies rejected, a JSON round-trip, and that doubling the length doubles the bits.

No network, no clipboard, no files unless you ask.

---

# ✨ Features

- Frozen `Policy` with length bounds (8–128), non-negative minimums, and a fit check
- `pool`, `pool_size`, `entropy_bits` and `label` derived from the policy, not from a template
- Guaranteed minimum coverage of every requested class
- Optional exclusion of ambiguous characters (`O 0 o I l 1 |` …)
- Injectable RNG: `random.Random(seed)` for reproducible runs, `SystemRandom` otherwise
- `validate()` returns **all** problems at once, not the first
- `strength()` on any existing password: length, classes, observed pool, bits, label, repeats
- Pattern warnings for common fragments, repeated runs and reversed common passwords
- `strength_label()` with the 40/60/80-bit bands
- `PasswordHistory` that is bounded, refuses reuse, and never stores lengths you did not ask for
- `generate_unique()` — generate until new, then record
- Four named policies in `data/policies.json` (`standard`, `strong`, `memorable`, `pin`)
- CLI with `--policy`, `--length`, `--count`, `--no-symbols`, `--no-ambiguous`, `--seed`, `--check`, `--json`, `--quiet`
- `--json` records entropy and counts, never the generated passwords
- Exit `0` on success, `2` on any invalid policy or file
- 85 passing pytest tests

---

# 📂 Folder Structure

```text
Password_Generator/
│
├── src/
│   ├── main.py       # CLI: generate, check, JSON summary
│   └── passwords.py  # Policy, generate, validate, strength, history, demo
│
├── tests/
│   └── test_passwords.py
│
├── data/
│   └── policies.json   # standard, strong, memorable, pin
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 01_Beginner_Level_Projects/Password_Generator

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: policy, entropy, coverage, strength, history, 12 cross-checks
python src/main.py --demo

# One standard password with its entropy
python src/main.py

# Reproducible: the same seed always gives the same password
python src/main.py --seed 42

# Five strong passwords
python src/main.py --policy strong --count 5 --seed 1

# Read-aloud friendly: no symbols, no ambiguous characters
python src/main.py --length 20 --no-symbols --no-ambiguous --seed 1

# Score a password you already have
python src/main.py --check "CorrectHorse9!"

# A JSON summary that contains no secrets
python src/main.py --seed 42 --json out.json
```

**Policy format** (`data/policies.json`):

```json
{
  "pin": { "length": 8, "min_lower": 0, "min_upper": 0,
           "min_digits": 8, "min_symbols": 0, "forbid_ambiguous": false }
}
```

**Exit codes:** `0` = generated or checked · `2` = unknown policy, bad length, unreadable or invalid policy file.

---

# 🧠 How It Works

```text
data/policies.json
        │
        ▼
Policy.from_dict()  ──►  __post_init__  ──►  length / minimums / fit
        │
        ├── pool      union of the required classes, minus ambiguous
        ├── bits      length * log2(pool_size)
        └── label     weak < 40 <= fair < 60 <= strong < 80 <= excellent
        │
        ▼
generate(policy, rng)  ──►  plant minimums -> fill -> shuffle
        │
        ▼
validate(password, policy)  ──►  [] or a list of named problems
        │
        ▼
PasswordHistory.add()  ──►  bounded, no reuse
```

Details worth knowing:

- **Plant, fill, shuffle.** The order matters: filling first would leave the planted digits at the front, which is itself a pattern an attacker can exploit.
- **`validate` never short-circuits.** A password that is too short *and* missing symbols reports both, which is what a person needs to fix it in one pass.
- **`pool` is sorted and de-duplicated.** The same character in two sets cannot be counted twice, so `log2(pool_size)` stays honest.
- **The label can disagree with the bits, and says why.** `strength()` returns both, so the report shows `75.21 bits` next to `weak` instead of hiding one behind the other.
- **`--json` deliberately omits the passwords.** A summary file that contains the secrets is a leak with extra steps.
- **`SystemRandom` is the default.** Seeds exist for tests and demos, not for production use.

---

# 🛠 Technologies

- Python 3 standard library: `random`, `math`, `json`, `dataclasses`, `pathlib`, `argparse`, `contextlib`
- pytest

No `secrets` module dependency, no network, no clipboard integration.

---

# 📚 Concepts Covered

- Policy objects as data with a self-validating constructor
- Guaranteed sampling (plant-fill-shuffle) versus rejection sampling
- Entropy as `length * log2(pool_size)`, and its assumptions
- Why a bit count without a pattern check is misleading
- Injectable randomness and reproducible runs
- Collecting all validation failures instead of the first
- Character-class counting and exclusion sets
- Bounded history with a reuse guard
- Secrets hygiene: summaries without payloads
- Self-asserting demos with negative controls

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**85 tests passed** covering the policy shape, pool construction for each class combination, ambiguous exclusions, length and minimum validation, frozen behaviour, JSON round-trips, generation length, seed reproducibility and seed sensitivity, 100 repeated coverage checks, minima-versus-exact counts, pool confinement, `generate_many`, `validate` reporting four problems at once plus ambiguous and out-of-policy characters, the 40/60/80 label boundaries, observed-pool strength, the repeated-character override, `max_repeat`, three pattern warnings, every history behaviour, `generate_unique`, all four bundled policies, five policy-file failure modes, demo determinism, and every CLI path including `--check`, `--json` without secrets and `--quiet`.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
