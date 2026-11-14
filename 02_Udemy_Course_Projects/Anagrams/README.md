<div align="center">

# 🔤 Anagrams

### An anagram is an equality between multisets of letters, not a string trick. This project makes that explicit: one signature function decides every comparison, and the original one-liner's two bugs are shown and fixed.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Offline-No%20Network-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

The course exercise compared two strings character by character:

```python
for i in S1:
    if i.isalpha():
        if S1.count(i) != S2.count(i):
            print("Not Anagrams")
            break
else:
    print("Anagrams")
```

It looks right and is wrong twice.

**It only checks one direction.** Every character of `S1` is counted, but nothing checks that `S2` has no *extra* letters. `is_anagram("abc", "abcd")` would report `Anagrams`, because `a`, `b` and `c` all match.

**It never removes punctuation from `S2`.** `"Alas, no more Z's"` keeps its comma and apostrophe, so the counts can never line up with a cleaned `S1` — unless the punctuation happens to cancel, which it does here only by luck.

Both bugs disappear with one idea: **reduce each string to a signature and compare signatures.**

```text
normalise("Snooze alarms")        -> "snoozealarms"
normalise("Alas, no more Z's")    -> "alasnomorezs"
signature(...)                    -> sorted letters, so order stops mattering
signature("Snooze alarms")        == "aaelmnoorssz"
signature("Alas, no more Z's")    == "aaelmnoorssz"      equal -> anagram
```

Now the comparison is symmetric by construction, punctuation cannot interfere, and grouping a whole word list becomes a dictionary lookup rather than an O(n²) scan:

```python
buckets[signature(word)].append(word)
```

**The original pair really does work.** `"Snooze alarms"` and `"Alas, no more Z's"` both sign as `aaelmnoorssz` — twelve letters, no digits, no punctuation. The demo asserts the exact signature rather than trusting the claim.

**The negative controls matter as much as the positive one.** `"listen"` vs `"silen"` is one letter short; `"listen"` vs `"silentt"` is one letter too many; `"aabc"` vs `"abc"` is a subset but not equal. The last one is the exact shape of bug the original loop had, and `difference()` makes it visible:

```text
difference("listen", "silentt")  ->  {"t": -1}      second has an extra t
difference("abc",     "abd")     ->  {"c": 1, "d": -1}
```

**Empty input is refused, not called equal.** Two letter-free strings have identical signatures — both `""` — so a naive implementation reports them as anagrams. That is a technicality, not a finding, so `is_anagram` returns `False` and `find_anagrams` raises.

**Everything in the demo is falsifiable.** It asserts the twelve-letter signature, three normalisation cases, three negative controls with a signed letter difference, that letter-free input is refused, that `listen` finds exactly three of four candidates, that 48 bundled words form 6 groups whose members all re-sign correctly with no word reused, that the largest group has five members, that there are exactly 34 unordered pairs starting at `("ager", "gear")`, that grouping is independent of input order, and that empty inputs produce no invented groups.

No network, no third-party library.

---

# ✨ Features

- `normalize` — letters only, case-folded, punctuation and digits dropped
- `signature` — the sorted letters; equal signatures mean anagram
- `is_anagram` with symmetric comparison and a letter-free guard
- `letter_counts` — a sorted `Counter` view of one text
- `difference` — the signed letter surplus between two texts
- `group_anagrams` — one pass into signature buckets, singletons dropped
- `find_anagrams` — matches for one word, excluding the word itself
- `anagram_pairs` — every unordered pair, de-duplicated and sorted
- `longest_group` — the biggest group, ties broken alphabetically
- `load_words` — a `#`-comment-aware word list reader
- `data/words.txt` — 48 words forming 6 groups and exactly 34 pairs
- CLI with `--check`, `--find`, `--pairs`, `--file`, `--json`, `--quiet`
- Text rendering for groups (with key and member count) and pairs
- Exit `0` on success, `2` on a missing file or letter-free input
- `--demo` and `--quiet` (prints nothing)
- 73 passing pytest tests

---

# 📂 Folder Structure

```text
Anagrams/
│
├── src/
│   ├── main.py      # CLI: groups, pairs, one pair, one word
│   └── anagram.py   # normalise, signature, group, search, demo
│
├── tests/
│   └── test_anagram.py
│
├── data/
│   └── words.txt     # 48 words: 6 groups (23 words) + 25 singletons
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 02_Udemy_Course_Projects/Anagrams

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: signatures, negative controls, groups, pairs, 10 cross-checks
python src/main.py --demo

# Group the bundled 48-word list
python src/main.py

# Every anagram pair in the list
python src/main.py --pairs

# Test a single pair
python src/main.py --check "listen" "silent"
python src/main.py --check "listen" "silen"

# Find the anagrams of one word
python src/main.py --find listen

# Your own list, with JSON output
python src/main.py --file words.txt --json out.json
```

**Word list format** (`data/words.txt`) — one word per line, `#` starts a comment:

```text
# Bundled word list
enlist
listen
silent
tinsel
```

**Bundled groups** (6 groups, 23 words, 34 pairs):

```text
aegr    ager, gear, rage
aelrt   alert, alter, later
aelst   least, slate, stale, steal, tales
eilnst  enlist, listen, silent, tinsel
eilv    evil, live, veil, vile
opst    post, pots, stop, tops
```

**Exit codes:** `0` = the command ran · `2` = missing word list or letter-free input.

---

# 🧠 How It Works

```text
"Snooze alarms"
      │
      ▼
normalize()  ──►  "snoozealarms"      case-fold, keep letters only
      │
      ▼
signature()  ──►  "aaelmnoorssz"      sorted, so order stops mattering
      │
      ├── is_anagram(a, b)      signature(a) == signature(b), both non-empty
      ├── group_anagrams(words) buckets[signature] -> members
      ├── find_anagrams(word)   candidates whose signature matches
      └── anagram_pairs(words)  every C(n, 2) inside a bucket
```

Details worth knowing:

- **Sorting is the canonical form.** Any function that maps every permutation to the same value would work — a count vector or a prime product — but a sorted string is the version you can read in a debugger.
- **`casefold()` beats `lower()`.** It folds `ß` to `ss` and similar, so the comparison does not depend on the writer's alphabet. Only letters survive, so digits cannot smuggle in a false match.
- **Singletons are dropped.** A "group" of one is not a finding, and returning it would make every word list look like it had anagrams.
- **Pairs come from buckets, not from nested loops.** Two members give one pair, five give ten: `C(n, 2)`, which the test recomputes from the group sizes so the 34 cannot drift.
- **Letter-free input is an error where it matters.** `is_anagram` returns `False`; `find_anagrams` raises, because searching for `"123"` is a mistake rather than a no-result.
- **Grouping is order-independent.** The test reverses the word list and asserts the identical dictionary, which follows from the buckets being keyed by signature.

---

# 🛠 Technologies

- Python 3 standard library: `collections.Counter`, `pathlib`, `argparse`, `json`, `contextlib`
- pytest

No `nltk`, no word-list download, no network access.

---

# 📚 Concepts Covered

- Anagrams as equality of multisets rather than of strings
- Canonical forms (signatures) and why they simplify comparisons
- Case folding versus lower-casing
- Symmetric comparison, and the one-direction bug it fixes
- Grouping by key instead of pairwise comparison: O(n) instead of O(n²)
- Combinatorics inside a bucket: `C(n, 2)` pairs
- Signed differences for explaining a near miss
- Refusing a degenerate input instead of reporting a vacuous truth
- Deterministic ordering of keys and members
- Self-asserting demos with negative controls

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**73 tests passed** covering normalisation of case, spaces, punctuation, digits and non-text; signatures for the classic pair and five permutations of one word; nine `is_anagram` cases including the subset bug, letter-free input and symmetry; sorted counts; signed differences; grouping with sorting, singletons, letter-free words and both type errors; the bundled list's 48 words, 6 groups, sizes and member signatures; search with case-insensitivity and no-match; all 34 pairs including their order and the `C(n, 2)` identity; `longest_group` with ties; word-list loading with comments, blanks, missing files and empty files; demo determinism; and every CLI path including `--check`, `--find`, `--pairs`, `--json` and `--quiet`.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
