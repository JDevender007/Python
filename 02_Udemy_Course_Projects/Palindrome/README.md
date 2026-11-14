<div align="center">

# 🔁 Palindrome

### The legacy program printed `pythonnohtyp` on failure — a palindrome, and an answer to a question nobody asked. The fix is to normalise the text first and then *pad* it, not double it.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

The course version was five lines long:

```python
S1 = 'python'
S2 = S1.replace(' ', '')
rev = S2[::-1]
if S2.casefold() == rev.casefold():
    print(S1)
else:
    palindrome = S2.casefold() + rev.casefold()
    print(palindrome)
```

It has four problems, and they escalate.

**1 · There is no input.** `S1 = 'python'` is a constant. The program demonstrates that `'python'` is not a palindrome, permanently.

**2 · Punctuation defeats the check.** Only spaces are removed. Take the sentence every tutorial uses:

```text
A man, a plan, a canal: Panama
remove spaces  ->  Aman,aplan,acanal:Panama
reverse         ->  amanaP:lanaca,nalpa,namA
```

The comma and the colon break the mirror, so a perfectly good palindrome is rejected. The comparison is fine; the cleaning is not.

**3 · The failure branch prints nonsense.** On any non-palindrome the program prints `S2 + reverse(S2)`:

```text
'S1 = python'  ->  print('pythonnohtyp')
```

`'pythonnohtyp'` **is** a palindrome, so the output looks like a result rather than a bug. It contains the input, its reverse, and no information.

**4 · Nothing can make a palindrome.** The one genuinely useful operation — append the fewest characters that make a string read the same both ways — is missing.

So this module separates the operations:

| Function | Question it answers |
| --- | --- |
| `normalise(text)` | What is left after case-folding and dropping punctuation? |
| `is_palindrome(text)` | Does the normalised form mirror itself? |
| `check(text)` | What exactly was compared? |
| `longest_palindromic_substring(text)` | What is the longest mirrored run, anywhere? |
| `longest_palindromic_prefix/suffix(text)` | How much of the end already mirrors? |
| `complete(text)` | Fewest characters to append to make it a palindrome |
| `mirror(text)` | The legacy `s + reverse(s)`, kept for comparison |
| `legacy_output(text)` | The old failure branch, byte for byte |

**Completion is the interesting one.** `mirror('race')` is `'raceecar'` — eight characters, a palindrome, and it ignored the fact that `'race'` was already half-way there. `complete('race')` is `'racecar'` — seven characters:

```text
race     longest palindromic suffix  ->  'e'   (1 char)
prefix before it                     ->  'rac' (3 chars)
append the reverse of the prefix     ->  'race' + 'car' = 'racecar'
```

The result always starts with the input, is always a palindrome, and its length is *exactly* `2n - len(suffix)`. The demo asserts that lower bound rather than describing it.

**Everything is falsifiable.** The demo asserts the legacy string, asserts that the legacy check fails on the Panama sentence while the normalised check passes, classifies 5 palindromes and 4 near misses, refuses 5 empty inputs and 2 non-text inputs, checks 6 longest-run cases (including the earliest-on-a-tie rule), exercises prefix and suffix runs, verifies 6 completions against the measured length bound, proves the mirror is longer than the minimal completion, shows completion is idempotent, and loads 20 bundled phrases split 10/10 with the longest being its own longest run.

Standard library only, no network.

---

# ✨ Features

- `normalise` — letters and digits only, `casefold()` (so `Straße` → `strasse`)
- `is_palindrome` / `check` — verdict plus the exact strings compared
- `legacy_output` — the original failure branch, reproduced and asserted
- `longest_palindromic_substring` — expand around every centre, earliest on a tie
- `longest_palindromic_prefix` / `_suffix` — the run that already mirrors
- `complete` — minimal appending completion, with a provable length bound
- `mirror` — the trivial doubling, for comparison
- `load_phrases` / `split_phrases` / `stats` — comment-aware file loading, honest nulls
- `data/phrases.txt` — 20 phrases: 10 palindromes, 10 others
- CLI: `--check`, `--complete`, `--mirror`, `--longest`, `--file`, `--stats`, `--json`, `--quiet`
- Exit `2` on a `PalindromeError`; `--demo` always returns `0`
- 134 passing pytest tests

---

# 📂 Folder Structure

```text
Palindrome/
│
├── src/
│   ├── main.py        # CLI: check, complete, mirror, longest, stats
│   └── palindrome.py  # normalisation, runs, minimal completion
│
├── tests/
│   └── test_palindrome.py
│
├── data/
│   └── phrases.txt    # 20 phrases, '#' starts a comment
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 02_Udemy_Course_Projects/Palindrome

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo
python src/main.py --demo

# Classify the bundled 20 phrases
python src/main.py

# Counts and extremes
python src/main.py --stats

# One phrase, with what was compared
python src/main.py --check "A man, a plan, a canal: Panama"

# Minimal completion versus the legacy doubling
python src/main.py --complete race
python src/main.py --mirror race

# Longest mirrored run inside a string
python src/main.py --longest forgeeksskeegfor

# Your own file
python src/main.py --file my_phrases.txt
```

**Phrase file format** (`data/phrases.txt`) — one phrase per line, blank lines and `#` comments ignored:

```text
# Ten palindromes once punctuation and case are removed ...
Was it a car or a cat I saw?
Red rum, sir, is murder
...
# ... and ten that only look like one
Racecars
Python
```

**Exit codes:** `0` = the command ran · `2` = missing file, empty file, or text with no letters or digits.

---

# 🧠 How It Works

```text
"Racecar!"  ──normalise──►  "racecar"  ──►  reverse "racecar"  ──►  True
"racecars"  ──normalise──►  "racecars"  ──►  reverse "sracecar"  ──►  False

"race"  ──suffix scan──►  "e"  ──prefix "rac"──►  "race" + "car" = "racecar"
```

Details worth knowing:

- **Normalise before comparing, not after.** The legacy program compared a *cleaned* string but printed the *raw* one, which is why its output was unrecognisable.
- **`casefold`, not `lower`.** `lower('ß')` is `'ß'`, so `'STRASSE'` and `'Straße'` would not match. `casefold` maps both to `strasse`.
- **Empty is refused, not counted.** `"" == ""[::-1]` is `True`, so a naive check reports every blank line as a palindrome. `is_palindrome("")` raises instead.
- **Expand around centres, O(n²) time and O(1) extra space.** Odd centres sit on a character, even centres between two. `>` (not `>=`) keeps the earliest of two equal runs, which the `babad → bab` case pins.
- **The suffix decides the completion.** Only the part *before* the longest palindromic suffix needs mirroring, so `'abac'` needs three characters (`'aba'`), not four.
- **`complete` is idempotent.** `complete(complete(s)) == complete(s)`, because the output is already a palindrome, so nothing is appended.
- **`24 carat` style traps.** `split_phrases` calls `is_palindrome`, so single characters count — `"b"` is a palindrome, and a test with `"b"` in the "others" list catches that.

---

# 🛠 Technologies

- Python 3 standard library: `pathlib`, `argparse`, `json`, `contextlib`, `io`
- pytest

No regex, no libraries, no network.

---

# 📚 Concepts Covered

- Normalisation as a prerequisite for comparison
- `str.casefold()` versus `str.lower()`
- Expanding around a centre instead of trying every substring
- Minimal completion from the longest palindromic suffix
- Proving an optimality bound rather than asserting one
- Idempotence as a testable property
- Why `"" == ""[::-1]` is a trap
- Comment-aware line-oriented file loading
- Honest nulls in summary statistics
- CLI design with mutually independent action flags

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**134 tests passed** covering normalisation (punctuation, case, digits, sharp-s casefolding, four non-text types), the legacy program (its output, its always-palindrome property, its space removal, its punctuation failure on the Panama sentence, and its refusal of non-text), seven accepted and five rejected palindromes, four refused empty inputs, `check` (cleaned, reversed, length, raw input, both verdicts, no mutation), `mirror` (length, normalisation, doubling), longest runs (seven cases including the earliest-tie rule and case/punctuation handling), prefix and suffix runs, eight completions against expected values plus palindrome/prefix/length-bound/idempotence properties, the bundled file (count, split, longest uniqueness, comment skipping, missing file, comment-only file), stats including the empty case, demo determinism, and every CLI mode including JSON output and quiet.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
