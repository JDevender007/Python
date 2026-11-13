<div align="center">

# 🎯 Number Guessing Game

### The game is the easy part. This project proves the solver is optimal: bisection finds any secret in 1–100 within 7 guesses, the naive strategy needs up to 100, and the demo replays every secret to check the claim instead of asserting it.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Offline-Seeded%20RNG-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

"Guess a number, I'll say higher or lower" is a loop. What makes it worth studying is the question underneath: **how few guesses are necessary, and how do you know?**

Bisection answers both. Every guess halves the remaining candidates, so a range of `n` numbers needs at most `ceil(log2(n))` guesses: `log2(100) = 6.64`, so 7. The demo does not take that on faith — it plays all one hundred secrets and checks the bound:

```text
100 secrets solved; best 1, worst 7, average 5.8
distribution {1: 1, 2: 2, 3: 4, 4: 8, 5: 16, 6: 32, 7: 37}
```

Those counts are the shape of a binary search tree, and they sum to 100. That is a falsifiable result, not a slogan.

**The same secret, two strategies.** `42` is the worst case for a naive ascending search and a middling case for bisection:

```text
binary   50 25 37 43 40 41 42                      7 guesses
linear   1 2 3 ... 41 42                          42 guesses
```

**Feedback narrows an interval, not a vibe.** `Game` keeps `low..high` and updates it after each answer, so the state is inspectable:

```text
guess 50 -> high   interval 1..49    (24 candidates left after the next step)
guess 15 -> low    interval 16..49
```

**Randomness is seeded, so "random" is reproducible.** `random.Random(seed).randint(low, high)` means a round is fully described by its seed — the ten bundled rounds in `data/rounds.json` are a golden file, and a test recomputes all of them.

**Every misuse is an exception, not a silent break:**

| Misuse | Message |
| --- | --- |
| `Game(0)` | `secret 0 is outside 1..100` |
| `Game(5, 10, 10)` | `low (10) must be less than high (10)` |
| `Game(42, max_attempts=0)` | `max_attempts must be at least 1` |
| `guess(101)` | `guess 101 is outside 1..100` |
| guessing twice | `25 was already guessed` |
| guessing after the end | `the game is already over` |

No network, no interactive prompt, no unseeded randomness.

---

# ✨ Features

- `Game` with a shrinking `low..high` interval, `candidates`, `attempts` and `remaining`
- Three feedback values (`low`, `high`, `correct`) instead of a boolean
- Optional attempt limit that ends the game cleanly at the boundary
- `bisect_move` — the midpoint of everything still possible
- `solve` (optimal) and `solve_linearly` (naive) for a measured comparison
- `optimal_attempts` — the `ceil(log2(n))` bound for any range
- `random_secret` and `play_seeded` driven by `random.Random(seed)`
- `Statistics` with `played`, `solved`, `win_rate`, `average`, `best`, `worst` and a distribution
- Ten golden seeded rounds in `data/rounds.json`
- CLI with `--secret`, `--seed`, `--low`, `--high`, `--strategy`, `--json`, `--quiet`
- A transcript that replays each guess with its feedback and the interval it produced
- Exit `0` on a completed round, `2` on any invalid input
- `--demo` and `--quiet` (prints nothing)
- 56 passing pytest tests

---

# 📂 Folder Structure

```text
Number_Guessing_Game/
│
├── src/
│   ├── main.py      # CLI: play a round, print the transcript
│   └── guessing.py  # Game, strategies, seeds, statistics, demo
│
├── tests/
│   └── test_guessing.py
│
├── data/
│   └── rounds.json   # 10 seeded rounds, used as a golden file
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 01_Beginner_Level_Projects/Number_Guessing_Game

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: 100 secrets, both strategies, statistics, 10 cross-checks
python src/main.py --demo

# Bisect 42 and print every guess with its feedback
python src/main.py
python src/main.py --secret 73

# The naive strategy on the same secret
python src/main.py --secret 5 --strategy linear

# Let the seed pick the secret
python src/main.py --seed 7

# A bigger range: worst case becomes 10 guesses
python src/main.py --low 1 --high 1000 --secret 999

# Machine-readable transcript
python src/main.py --secret 42 --json out.json
```

**Round format** (`data/rounds.json`):

```json
[
  { "seed": 0, "secret": 50, "attempts": 1, "guesses": [50], "solved": true }
]
```

**Exit codes:** `0` = the round finished · `2` = secret outside the range, bad bounds or bad attempt limit.

---

# 🧠 How It Works

```text
seed ──► random.Random(seed).randint(low, high) ──► secret
                                                        │
                             ┌──────────────────────────┘
                             ▼
                     Game(secret, low, high)
                             │
        bisect_move() = (low + high) // 2  ──►  guess()
                             │                    │
                             │        low / high / correct
                             ▼                    │
                     low, high narrow  ◄──────────┘
                             │
                             ▼
                  attempts  +  Statistics.record()
```

Details worth knowing:

- **The interval is the state.** `candidates` is derived from `low..high`, so the shrinking range can be inspected and tested rather than inferred from the guess list.
- **Bounds are validated once, at construction.** Later guesses are checked against the *original* range, which is why an unhelpful guess inside the interval is allowed but an impossible one never is.
- **`solve` cannot cheat.** It only reads `game.low` and `game.high` — the same two numbers a human sees after each answer.
- **The transcript is reconstructed, not stored.** `main.py` replays the guesses against the secret to label them, which keeps `Game` from needing a parallel feedback log.
- **Statistics accept losses.** `record()` counts `played` and only increments `solved` when the game was won, so an attempt-limited loss cannot be miscounted as a win.

---

# 🛠 Technologies

- Python 3 standard library: `random`, `math`, `statistics`, `dataclasses`, `json`, `pathlib`, `argparse`, `contextlib`
- pytest

No GUI, no network, no unseeded randomness.

---

# 📚 Concepts Covered

- Binary search as an optimal strategy, not just a search routine
- Information theory: `ceil(log2(n))` guesses for `n` candidates
- Interval narrowing and interval invariants
- Seeded pseudorandomness and reproducible experiments
- Golden-file testing against recorded rounds
- Win-rate and distribution statistics from a simulation
- Explicit error types instead of silent `break`
- Transcript rendering from recorded state
- Self-asserting demos with negative controls

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**56 tests passed** covering all three feedback values, interval narrowing and collapse, `candidates`, length and `repr`, the play helper and its no-op after the end, every misuse (`secret` out of range, bad bounds, bad attempt limit, out-of-range guess, repeated guess, guess after the end, non-integer and boolean input), the exact `[50, 25, 37, 43, 40, 41, 42]` path, both edges, small ranges, both strategies, the `optimal_attempts` formula, an exhaustive check that all 100 secrets finish within the bound, seed reproducibility and range safety, the ten golden rounds, 200 seeded rounds, every `Statistics` behaviour including a recorded loss, demo determinism, and every CLI path including JSON and `--quiet`.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
