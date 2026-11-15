<div align="center">

# 📊 Sorting Visualizer

### The legacy project animated six sorts and reported two numbers per frame: comparisons and **swaps**. On merge sort the second number climbed to 44 for 12 items — but merge sort performs **zero** swaps. It writes into a second buffer, and the code incremented its `swaps` counter once per placement. A viewer comparing algorithms compared a swap count with a write count, and the animation's last frame was the only evidence that anything was sorted.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

The old project was a `tkinter` canvas drawing bars, with every algorithm written as a generator that yielded a frame and mutated two counters:

```python
if left_values[left_index] <= right_values[right_index]:
    data[target] = left_values[left_index]
    left_index += 1
else:
    data[target] = right_values[right_index]
    right_index += 1
swaps += 1
```

Four things follow.

**1 → A counter's name is a claim about what it counts.** `writes` and `swaps`
are different quantities. Selection sort makes at most `n - 1` swaps; merge sort
makes none and `n log n` writes. The rebuild counts both, separately, and refuses
to call one the other — `writes >= 2 * swaps` is checked on every result.

**2 → "It looks sorted" is not sorted.** An animation that ends on ascending bars
proves nothing; the frames could be a montage, or one item could have been
dropped. Every result here is checked three ways: the output is non-decreasing,
it is a *permutation* of the input (same multiset of keys **and** labels), and the
last frame agrees with the recorded counters.

**3 → Stability is a property of the algorithm, not of the data.** Two records
with equal keys keep their relative order only in a stable sort. The bundled data
has duplicate keys on purpose, and stability is measured by locating every pair of
equal keys in the output — including duplicates that were far apart in the input,
which a "check only adjacent duplicates" test would miss.

**4 → The worst case is chosen by the input, not by the reputation.** Lomuto
partition quick sort on an already-sorted 12-item array costs 66 comparisons —
identical to bubble sort on the same input, which is exactly the case bubble
sort's early-exit flag rescues with 11.

| | legacy | here |
|---|---|---|
| merge sort's second number (12 items) | `swaps 44` | `writes 44, swaps 0` |
| selection sort's real swaps (12 items) | `swaps 9` | `swaps 9`, and `<= n-1` is checked |
| stability | never mentioned | measured on duplicate keys |
| "is it sorted?" | the animation ended | non-decreasing **and** a permutation |
| counters in a frame | whatever was mutated | a frozen `Frame` value |
| wall clock | until the canvas closed | no time anywhere |

Standard library only: no `tkinter`, no `pygame`, no network.

---

# ✨ Features

- `Item` — a key plus a label, so two equal keys stay distinguishable; comparisons
  look at `sort_key` only
- `Frame` — a frozen snapshot: the keys, both counters at that moment
- `Tracer` — the shared recorder: `compare`, `write`, `swap`, `frame`, `result`
- `bubble_sort`, `insertion_sort`, `selection_sort`, `merge_sort`, `quick_sort`,
  `heap_sort` — each returns a `Result`
- `Result` — `keys`, `labels`, `is_sorted`, `is_permutation`, `is_stable`,
  `summary`, `to_dict`
- `read_values` — one integer per line, comments and blanks skipped, a word
  refused by file and line
- `inversions` — how far the input is from sorted
- `legacy_merge_writes` / `legacy_merge_swaps` — the same merge, counted both
  ways, so the mislabelling is a number and not a story
- `audit` — eight named checks, each falsifiable
- `data/values.txt` — 12 values with three duplicate keys, 32 inversions
- CLI: `--sort`, `--compare`, `--worst`, `--audit`, `--json`, `--values`,
  `--quiet`, `--demo`
- 175 passing pytest tests

---

# 📂 Folder Structure

```text
Sorting_Visualizer/
│
├── src/
│   ├── main.py     # CLI: the table, compare, worst case, audit, json
│   └── sorts.py    # six algorithms, frames, counters, audit, demo
│
├── tests/
│   └── test_sorts.py
│
├── data/
│   └── values.txt   # 5 2 9 2 7 1 9 4 3 6 1 8  -- duplicates on purpose
│
├── README.md
├── requirements.txt
├── LICENSE
└── .gitignore
```

---

# 🛠️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 05_Data_Structures_Algorithms/Sorting_Visualizer

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: the table, the legacy counter, the worst case, the audit
python src/main.py --demo

# The table for the bundled values
python src/main.py

# One algorithm, or one question at a time
python src/main.py --sort merge
python src/main.py --compare        # legacy "swaps" vs the honest count
python src/main.py --worst          # quick sort on an already-sorted input
python src/main.py --audit

# Every result as JSON
python src/main.py --json results.json

# Your own values, one integer per line
python src/main.py --values .\my_values.txt
```

**Exit codes:** `0` = the command ran · `1` = an audit check failed · `2` = a
missing values file, a non-integer line, or a file with no integers.

---

# ⚙️ How It Works

```text
Tracer(items)
  ├── data, labels        two parallel lists, moved together
  ├── compare(i, j)       +1 comparison, returns data[i] <= data[j]
  ├── write(i, key)       +1 write, one frame
  ├── swap(i, j)          +2 writes, +1 swap, one frame (a no-op when i == j)
  └── result(name)        the order, every frame, and a closing frame

each algorithm
  ├── mutates the tracer
  ├── never touches a counter directly (except comparisons it reasons about)
  └── returns Result(algorithm, original, order, frames, comparisons, writes,
                     swaps)

audit(results)
  ├── every result is sorted
  ├── every result is a permutation of its input
  ├── every result keeps the item count
  ├── no result reports fewer than zero comparisons
  ├── a swap costs two writes, so writes >= 2 * swaps
  ├── the last frame agrees with the final counters
  ├── the first frame is the untouched input
  └── only the stable three are stable
```

Details worth knowing:

- **Labels make stability observable.** `Item(4, "#01")` and `Item(4, "#02")`
  compare equal by key, so a sort that exchanges them is visibly unstable — and
  `Item` is deliberately *not* ordered by `(key, label)`, because that would make
  every sort look stable.
- **`compare` returns a bool, not a number.** The counter is incremented inside
  the recorder, so an algorithm cannot forget to count, and the tests can assert
  an exact total.
- **Insertion sort shifts rather than swaps.** It reports 41 writes and 0 swaps on
  the bundled input — the clearest case that the two numbers are not the same
  number wearing different hats.
- **Merge sort's 44 is `n log n`, not `n choose 2`.** 12 items, four levels of
  merging — 12 + 12 + 8 + 12 placements — every one of them a copy into a merged
  buffer.
- **The closing frame is added only when needed.** An algorithm whose last
  operation was a comparison would otherwise leave a stale final frame, and the
  audit would catch it.
- **Quick sort on sorted input is the pinned worst case.** 66 = 12·11/2, the same
  total as bubble sort, which is why "quick sort is faster" is a statement about
  inputs and not about names.

---

# 🧪 Technologies

- Python 3 standard library: `dataclasses`, `pathlib`, `json`, `argparse`,
  `contextlib`
- pytest 9.1.1

No `tkinter`, no `pygame`, no `numpy`, no network.

---

# 📚 Concepts Covered

- Comparators, keys and labels: what a comparison is allowed to look at
- Swaps versus writes versus comparisons, and why a counter needs a definition
- Recording an algorithm's history as immutable frames
- Permutation checks: sorted is necessary, not sufficient
- Stability as a measurable property, with duplicates placed to expose it
- Best case, worst case and input-dependent complexity
- Counting instead of timing: a deterministic stand-in for "which is faster"
- Executable legacy code: two counters for one loop, and the difference

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**175 tests passed** covering `Item` (validation, ordering, `sort_key`, frozen),
`read_values` (missing file, comments, blanks, a bad word with its line, negatives,
spaces, an empty file, the bundled pins), `inversions`, `Tracer` (initial frame,
`compare`, `write`, `swap` costing two writes, a self-swap being no swap, labels
moving with keys), all six algorithms on empty, single, sorted, reversed and
all-equal inputs, every pinned count and frame total, the properties each
algorithm is chosen for (selection's `n-1`, merge's zero swaps, insertion's zero
swaps, bubble's early exit, quick's quadratic worst case, selection's constant
comparison count), stability both ways, `Result` (summary, dict, frozen), the
legacy counter, all eight audit checks with a negative control each, the demo, and
every CLI mode.

---

# 🎯 Learning Outcomes

- Read an animation's counter and ask what, exactly, it counts
- Replace "looks sorted" with sorted **and** a permutation, checked
- Measure stability on data that can expose it
- Choose the input that makes a claim about complexity false
- Keep a trace as values, so a run can be audited after the fact

---

# 🚀 Future Improvements

- Median-of-three and three-way partitioning, with the worst case re-measured
- Timsort's runs, and why real data is not random
- A `--trace` mode that prints the bars per frame as text
- Comparison-count bounds per algorithm, asserted rather than stated
- Sorting large inputs in a subprocess, to show the counters still agree

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
