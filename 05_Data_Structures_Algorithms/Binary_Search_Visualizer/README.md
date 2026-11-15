<div align="center">

# 🔎 Binary Search Visualizer

### The legacy project called `values = sorted(array)` before it searched, so every index it drew — the middle bar, the found bar, the left and right boundaries — was an index into a **copy**. On `[30, 10, 20]` with target `10` it returned index `0`, and index `0` of the array the caller passed holds `30`. The bug is invisible on sorted input, which is exactly the input a demo uses.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

The old project animated a search over bar heights:

```python
def binary_search_steps(array, target):
    values = sorted(array)          # <- a different array
    left = 0
    right = len(values) - 1
    ...
    return middle                   # <- an index into that copy
```

Four things follow.

**1 → A search returns an index into the array it searched.** If the function
sorts a copy, "the" answer refers to a different array than the one the caller
holds. This module never sorts: it checks that the input is ascending and refuses
it otherwise, so every index it returns is an index into the sequence you passed.

**2 → Binary search on an unsorted array is not a slower search, it is an
undefined one.** It does not merely take longer — it can *miss* a value that is
present. The legacy code hid that by sorting first. A refusal with a reason is the
honest behaviour, and it puts the precondition at the call site where it belongs.

**3 → "Found" is not enough when values repeat.** The bundled array holds three
copies of `13`. A search that returns whichever copy its midpoint happened to land
on cannot answer "where does the block start and end". `first_index` and
`last_index` can, and `count_of` is their difference plus one — a lookup and a
range query are different questions.

**4 → A comparison bound is checkable.** A binary search over `n` sorted values
needs at most `floor(log2(n)) + 1` comparisons to succeed and `ceil(log2(n + 1))`
to fail. Every result is checked against that bound, so an off-by-one loop cannot
pass as "fast".

| | legacy | here |
|---|---|---|
| `[30, 10, 20]`, target 10 | sorts, returns `0` → reads `30` | refused: "the sequence must be ascending" |
| index into | `sorted(array)` | `array` |
| three copies of 13 | one index, whichever it met | `6`, `8`, and `count_of` → `3` |
| comparisons | drawn, never bounded | checked against `log2(n)` bounds |
| a miss | an empty `found` flag | `index is None`, and the target is proven absent |
| fastest claim | "binary is faster" | 47 vs 132 total comparisons, with the first element named as the case where linear wins |

Standard library only: no `tkinter`, no `bisect` in the module (it is
re-implemented, then cross-checked against `bisect` in the tests), no network.

---

# ✨ Features

- `Probe` — one look: the window, the middle, and the comparison it cost; refuses
  an empty window or a middle outside it
- `Result` — the sequence, the target, the index (or `None`), the probes;
  `found`, `comparisons`, `value`, `is_hit`, `windows_shrink`, `summary`, `to_dict`
- `binary_search` — refuses an unsorted sequence and a non-integer target
- `linear_search` — the same question one position at a time, for comparison
- `first_index` / `last_index` / `count_of` — the range of a duplicate block
- `comparison_bound(size, found)` — the `log2` bound a correct search must respect
- `legacy_sorted_index` / `legacy_wrong_value` / `legacy_note` — the defects as
  executable functions with pinned source lines
- `audit` — seven named checks; `audit_pairs` — one more, over totals
- `data/numbers.txt` — 16 ascending numbers with three 13s and two 4s
- CLI: `--target`, `--linear`, `--range`, `--legacy`, `--audit`, `--json`,
  `--numbers`, `--quiet`, `--demo`
- 137 passing pytest tests

---

# 📂 Folder Structure

```text
Binary_Search_Visualizer/
│
├── src/
│   ├── main.py     # CLI: rows, range, legacy, audit, json
│   └── search.py   # the searches, the bounds, the audit, the demo
│
├── tests/
│   └── test_search.py
│
├── data/
│   └── numbers.txt   # 2 4 4 7 9 11 13 13 13 17 19 23 29 31 37 41
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 05_Data_Structures_Algorithms/Binary_Search_Visualizer

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: the hit, the miss, the legacy defect, the duplicate block, the audit
python src/main.py --demo

# One target, with the linear scan beside it
python src/main.py
python src/main.py --linear

# A range query
python src/main.py --target 13 --range

# What sorting a copy does to the answer
python src/main.py --legacy

# Every check, and the JSON
python src/main.py --audit --linear
python src/main.py --json results.json

# Your own numbers, one integer per line, ascending
python src/main.py --numbers .\my_numbers.txt --target 42
```

**Exit codes:** `0` = the command ran · `1` = an audit check failed · `2` = a
missing numbers file, a non-integer line, an unsorted file, or a non-integer
target.

---

# ⚙️ How It Works

```text
check_sequence(values)
  ├── every position holds a real integer (not a bool, not a float)
  └── the sequence is ascending          -> otherwise SearchError

binary_search(values, target)
  ├── low, high = 0, len(values) - 1
  ├── while low <= high:
  │     middle = (low + high) // 2
  │     record a Probe(low, high, middle, comparisons)
  │     equal -> return the index
  │     smaller -> low = middle + 1
  │     larger  -> high = middle - 1
  └── return index None (the target is not there)

first_index / last_index
  ├── the same loop, but a hit is remembered and the search continues
  └── count_of = last - first + 1
```

Details worth knowing:

- **Nothing is sorted, ever.** `check_sequence` is the precondition, written as
  code: an unsorted input raises `SearchError` naming the rule it broke.
- **An index is only meaningful on the sequence that produced it.** `Result.values`
  is the tuple that was searched, so `result.value` cannot read from another
  array — and out-of-range indices return `None` instead of raising from a
  property.
- **Every probe records its own window.** `windows_shrink()` proves the search is
  halving, not merely looping, so a linear scan wearing a binary search's name
  fails the audit.
- **A hit and a miss are both checked.** A hit must point at the target; a miss
  must be for a value the sequence does not contain. Together they rule out both
  false positives and false negatives.
- **The last check is about totals, because the per-hit claim is false.** Finding
  the *first* element costs one linear comparison and up to `log2(n)` binary ones.
  The total across every target is what "logarithmic" buys: 47 against 132 here.
- **`bisect` is not used.** The bounds are re-derived so the comparison counts are
  visible; the tests cross-check `first_index`/`last_index` against `bisect` to
  prove the re-derivation is right.

---

# 🧪 Technologies

- Python 3 standard library: `dataclasses`, `math`, `pathlib`, `json`, `argparse`,
  `contextlib`
- pytest 9.1.1 (tests also import `bisect` to cross-check the range queries)

No `tkinter`, no `pygame`, no network.

---

# 📚 Concepts Covered

- Preconditions as code: a refusal instead of a silent repair
- Index semantics: an index belongs to a sequence
- Binary search's invariant, and why `windows_shrink` proves it
- Logarithmic comparison bounds, checked per result
- Duplicate keys: lookup versus range query
- Linear versus binary, measured rather than claimed
- The case where the "faster" algorithm is not faster, and how to state it honestly
- Executable legacy code: one `sorted()` call, and the wrong array

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**137 tests passed** covering `Probe` (window validation, width, one-position
window, an inverted window, a middle outside it, a probe costing nothing),
`Result` (hit, miss, comparisons, `is_hit` both ways, a tampered index,
`windows_shrink`, summary, dict, frozen), `read_numbers` (missing file, comments,
a bad word with its line, empty, the bundled pins), `is_sorted`,
`check_sequence`/`check_target` (a word, a float, a bool, an unsorted sequence),
`binary_search` (every present value, twelve absent values, unsorted refused,
non-integer target, empty, one item, two items, no sorting of its input, the
duplicate it meets, both bounds over the whole range), `linear_search` (first copy,
one comparison per position, the full scan, empty, unsorted is fine, a bad target),
the range queries (`6`, `8`, `3`, absent, sums to the length, unsorted refused),
`comparison_bound`, the legacy functions and their pinned lines, all seven audit
checks with a negative control each, the totals check and its numbers, the demo,
and every CLI mode.

---

# 🎯 Learning Outcomes

- Notice a function that answers about one array and returns an index into another
- Turn a silent precondition violation into a refusal with a reason
- Prove a search is halving rather than looping
- Answer range questions over duplicates, not just lookups
- Check an algorithm against its own complexity bound
- State a performance claim with the exception that makes it false

---

# 🚀 Future Improvements

- Exponential search for unbounded sequences
- Interpolation search, with its failure on non-uniform data pinned
- A `--trace` mode printing each window as text bars
- Rotated sorted arrays, where binary search needs a second invariant
- A comparison-count histogram over every target

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
