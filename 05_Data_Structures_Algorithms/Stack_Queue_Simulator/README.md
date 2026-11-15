<div align="center">

# 🧱 Stack & Queue Simulator

### The legacy simulator introduced the stack with the sentence *"Function calls, undo/redo systems, expression evaluation, backtracking, browser history, and syntax parsing."* Then it offered eleven controls, and **none of them undid anything**. Its work counter was a single integer, incremented in two places — once when an operation succeeded and once when it failed.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

The old simulator declared its callbacks explicitly:

```python
class ControlCallbacks:
    push: Action
    pop: Action
    peek: Action
    enqueue: Action
    dequeue: Action
    front: Action
    rear: Action
    clear: Action
    reset: Action
    random_fill: Action
    structure_changed: StructureChangeAction
```

and counted its work like this:

```python
def _record_success(self, started_at, status):
    self.operations_performed += 1
    ...

def _record_failure(self, started_at, status):
    self.operations_performed += 1
    ...
```

Three things follow.

**1 → A `Stack` cannot undo itself.** `push`, `pop` and `peek` are the whole public
surface, and the value a `pop` returns is gone the moment it is returned. There is
nothing left to put back, because the structure does not remember that the `pop`
ever happened. **Undo is not a method on the structure; it is a second structure.**
This module keeps two of them: a history of steps that can be reversed, and a future
of steps that were reversed and can be replayed. Eleven callbacks undo nothing;
two stacks undo everything.

**2 → A counter is not a history.** `operations_performed` is one integer. It cannot
say *which* operation happened, so it cannot reverse one — and because the same line
`self.operations_performed += 1` appears in both `_record_success` and
`_record_failure`, the number counts a rejected push as an operation performed, even
though nothing changed. Here the counts are separate and named: `applied` for a
change that happened, `refused` for an attempt that raised, `reads` for a lookup
that changed nothing.

**3 → Only a change belongs in the history.** A `peek` returns a value and leaves the
structure exactly as it was. Recording it would make the next undo appear to do
nothing — the user would press undo and watch the stack stay the same. Reads are
counted, not recorded, and a `clear` of an already-empty structure records nothing
either.

The history stores **steps, not snapshots**, and each step knows its own inverse:

| step | inverse |
|---|---|
| `push` | pop, and check the value coming back is the same |
| `pop` | push the value back |
| `enqueue` | `remove_rear` — the end it went in at |
| `dequeue` | `add_front` — the end it left from |
| `push_front` / `push_back` | pop the same end |
| `heap_push` | remove *that exact entry*, not whatever is smallest now |
| `heap_pop` | `push_entry`, keeping the old tie-break number |
| `clear` | put every item back, in its old order |

Two of those rows are the lesson. Undoing a heap push cannot be "pop the minimum":
later pushes may sort below it, so the inverse has to name the entry. And `heap_pop`
has to store the whole `(priority, sequence, value)` triple, because the priority
alone does not say where the value belonged among the entries it tied with. A redo
replays the step and checks the value it produced against the value recorded, so a
history that has drifted from its structures reports a **divergence** instead of
quietly corrupting them.

Standard library only: no `tkinter`, no network.

---

# ✨ Features

- `Stack` — LIFO, bounded, `push`/`pop`/`peek`/`clear`
- `Queue` — FIFO, plus `add_front` and `remove_rear`: the two ends a reversal needs
- `Deque` — both ends, so it can reverse its own operations
- `PriorityQueue` — smallest priority first, ties broken by insertion order;
  `push` returns the whole entry, `pop_entry`/`push_entry`/`remove_entry` move
  exact entries
- `Step` — a frozen record of one change: number, structure, action, value,
  priority, the items a `clear` removed, and the heap entry
- `Simulator` — four structures, `undo`/`redo`/`undo_all`/`redo_all`, and honest
  counters (`applied`, `refused`, `reads`, `discarded`)
- `read_session` / `run_session` — a scripted session file, with the failing line
  number in every error message
- `audit` — twelve named checks, each with a negative control in the test suite
- `data/session.txt` — 17 lines that change the four structures 15 times, 267 bytes
- CLI: `--session`, `--capacity`, `--history`, `--undo`, `--redo`, `--undo-all`,
  `--redo-all`, `--legacy`, `--audit`, `--json`, `--quiet`, `--demo`
- 164 passing pytest tests

---

# 📂 Folder Structure

```text
Stack_Queue_Simulator/
│
├── src/
│   ├── main.py       # CLI: the state, the history, undo/redo, the audit, json
│   └── structures.py # four structures, steps, the history, the demo
│
├── tests/
│   └── test_structures.py
│
├── data/
│   └── session.txt   # 17 lines: 15 changes, 2 reads
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 05_Data_Structures_Algorithms/Stack_Queue_Simulator

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: the session, the history, undo all, redo all, the redo rule
python src/main.py --demo

# The bundled session and its final state
python src/main.py

# The recorded history, and two undos
python src/main.py --history
python src/main.py --undo 2 --history

# Undo everything, then replay it
python src/main.py --undo-all
python src/main.py --undo-all --redo-all

# The legacy claims, and every check
python src/main.py --legacy
python src/main.py --audit

# The JSON, and a session of your own
python src/main.py --json state.json
python src/main.py --session .\my_session.txt --capacity 4
```

**Exit codes:** `0` = the command ran · `1` = an audit check failed · `2` = a
missing session file, a malformed line, an overflow or underflow, or an undo/redo
with nothing left to reverse.

---

# ⚙️ How It Works

```text
read_session(path)
  ├── ';' or '//' starts a comment; blank lines are skipped
  ├── every action is checked for the right number of arguments
  └── run_session names the failing line: "line 3 (pop): stack underflow"

Simulator._record(structure, action, value, priority, restored, entry)
  ├── discards the future -- a new branch of history
  ├── appends a numbered Step to _past
  └── applied += 1

undo()
  ├── pop the newest Step from _past
  ├── _revert it, checking the value that comes back
  └── on any StructureError, put the Step back and re-raise

redo()
  ├── pop the oldest Step from _future
  ├── _replay it, checking the value it produces
  └── on any StructureError, put the Step back and re-raise
```

Details worth knowing:

- **`undo` puts the step back if the reverse fails.** A tampered structure raises
  `Divergence`, and the history is left exactly as it was — a failed undo must not
  silently consume a step.
- **The heap's inverse names an entry, not a value.** `remove_entry` takes the exact
  `(priority, sequence, value)` triple and re-heapifies; a plain pop would remove a
  different item whenever a later push sorted lower.
- **`clear` records what it removed, in drain order**, and the inverse refills in
  that same order — which is why a cleared heap comes back with its tie order intact.
- **`reads` are counted before they can fail.** A `peek` on an empty stack raises
  `Underflow` and increments nothing, so the counter never claims a read that did
  not happen.
- **`total == applied + refused`** exists only to show what the legacy counter
  reported: a number that mixes a change and a rejection.
- **The demo prints no measured value.** Every number in its output is derived from
  the session file, so two runs are byte-identical.

---

# 🧪 Technologies

- Python 3 standard library: `heapq`, `itertools`, `collections.deque`,
  `dataclasses`, `pathlib`, `json`, `argparse`, `contextlib`
- pytest 9.1.1

No `tkinter`, no network.

---

# 📚 Concepts Covered

- Undo as a stack of reversible steps, not a method on the structure
- A counter versus a history: why an integer cannot reverse an operation
- Keeping an inverse for every mutation, including the awkward ones
- Why a heap needs the whole entry to reverse a push
- Why a read must not enter a history
- Redo invalidation: a new operation discards the future
- Bookkeeping that must add up: `undoable + redoable + discarded == applied`
- Divergence detection instead of silent corruption
- Bounded structures and the difference between `Overflow` and `Underflow`
- Audits whose negative controls plant the defect where the check looks

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**164 tests passed** covering the four structures (LIFO, FIFO, both ends of the
deque, heap priority and tie order, every overflow and underflow, `clear` returning
what it removed), `Step` and its four print shapes, the simulator's counters
(`applied`, `refused`, `reads`, `total`, and a refused step being unundoable), every
inverse (push, pop, enqueue, dequeue, three deque moves, heap push after later
pushes, heap pop with its priority, clear with a heap's tie order), redo, future
invalidation and `discarded`, `undo_all`/`redo_all` round-tripping the bundled
session, two divergence cases, session parsing with every malformed shape, the pinned
bundled values, the three legacy constants, all twelve audit checks with a negative
control each, the demo, and every CLI mode including five exit-2 paths.

---

# 🎯 Learning Outcomes

- Explain why a `Stack` cannot implement undo by itself
- Build undo and redo from two stacks of reversible steps
- Choose the right inverse for each mutation, including the two-end and heap cases
- Distinguish a change, a refusal and a read in your counters
- Keep bookkeeping that provably adds up
- Write a demo whose output does not depend on the machine

---

# 🚀 Future Improvements

- Snapshot mode behind a flag, to compare step-based undo with state copying
- Grouping steps into transactions, so one undo reverses several changes
- Persisting the history to disk and replaying it in a fresh process
- A `size` cap on the history, with the oldest steps dropped first
- Ring-buffer and circular-queue structures in the same harness

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
