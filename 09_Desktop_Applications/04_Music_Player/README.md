<div align="center">

# 🎵 Music Player

### The legacy player kept a single integer as "where we are" — an index into a playlist the user can edit. Delete track 0 while track 2 plays and the next track is **skipped**: `Quiet Hours` instead of `Drift`. Its `if cursor >= len(tracks): cursor = 0` also decided the repeat mode by itself, so *repeat off* played forever. This one keeps a cue into a permutation, asks the repeat mode, and shuffles with a seeded Fisher–Yates pass consumed in order.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

```python
def next_track(tracks, cursor):
    cursor = cursor + 1
    if cursor >= len(tracks):
        cursor = 0
    return cursor, tracks[cursor]
```

**1 → A position is not an index into a list people edit.** With `Ember` playing at index 2,
deleting `Kite` at index 0 shifts every track down by one. The cursor still says 2, so the
player lands on the track *after* the one that should have played — one deletion, and a track
is skipped without ever being seen:

```text
playing:               Ember (position 2)
delete:                position 0
the next track here:   Drift
the legacy next:       Quiet Hours  <- a track is skipped
```

**2 → `if cursor >= len(tracks): cursor = 0` decides the repeat mode by itself.** A playlist
with repeat *off* wraps to the top and plays forever, so the mode the user chose is never
consulted. The three modes are `off`, `one` and `all`, and `advance()` asks.

**3 → A shuffle is a permutation consumed in order, not `random.shuffle` before every draw.**
Reshuffling the whole list for each "next" can play the same track twice in a row, can play
track 3 four times before track 4 at all, and cannot be reproduced — so a bug in it is
unfixable. A seeded Fisher–Yates pass is a permutation, every track once before any track
twice, and the same seed returns the same order:

```text
Harbour, Half Light, Drift, Night Bus, Dawn Chorus, Ember, Slow Train,
Long Way Home, Kite, Last Light, Quiet Hours
11 distinct titles in 11 places
```

**4 → A duration is a whole number of seconds, and the format needs hours.**
`f"{total // 60}:{total % 60}"` prints a 64-minute playlist as `64:23` and a seven-second
remainder as `7:7`. The padded format says `1:04:23`; the legacy string says `64:23`.

So this module keeps `Track.seconds` as integers, a `Player` whose order is a permutation of
*playlist positions* that survives removal, a repeat mode that `advance()` actually asks, a
seeded Fisher–Yates shuffle consumed in order, and a `format_duration` that pads. The legacy
path is kept beside it, executable, so every claim above is reproduced.

The demonstration is offline: one bundled playlist of eleven tracks.

---

# ✨ Features

- `parse_duration` / `format_duration` — `MM:SS` and `HH:MM:SS`, with seconds below 60 and a
  padded two-digit remainder; a round trip is an identity
- `legacy_total` — the transcribed `f"{total // 60}:{total % 60}"`, no hours, no padding
- `Track` — a title, an artist and a positive whole number of seconds
- `parse_playlist` — one track per line, `;` comments, distinct titles enforced so a removal
  can name one
- `Player` — an `_order` permutation of playlist positions plus a cursor into *it*, so
  `remove()` remaps positions instead of invalidating a number
- `repeat` — `off` stops, `one` replays, `all` wraps; `advance()` consults the mode
- `shuffle(seed)` — a Fisher–Yates permutation that keeps the current track playing and is
  reproducible; `unshuffle()` returns to playlist order without interrupting playback
- `remove(position)` — keeps the cue on the track that was playing, and moves it down when the
  deleted track sat before it
- `legacy_advance` / `legacy_shuffle` — the transcribed paths, executable
- `audit` — eleven named checks, every one falsifiable from a measurement or a substitute
  `Player` factory
- CLI: `--playlist`, `--repeat`, `--seed`, `--remove`, `--steps`, `--total`, `--audit`,
  `--json`, `--quiet`, `--demo`
- 151 passing pytest tests

---

# 📂 Folder Structure

```text
04_Music_Player/
│
├── src/
│   ├── main.py    # CLI: play, remove, shuffle, audit, JSON
│   └── player.py  # durations, tracks, the cue, repeat modes, the shuffle
│
├── tests/
│   └── test_player.py
│
├── data/
│   └── playlist.txt   # eleven tracks, 3863 seconds = 1:04:23
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 09_Desktop_Applications/04_Music_Player

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: eleven tracks, one deletion, three repeat modes, eleven checks
python src/main.py --demo

# The playlist, playing the first track
python src/main.py

# Advance three times
python src/main.py --steps 3

# Keep going after the last track
python src/main.py --steps 12 --repeat all

# Delete track 0, then advance -- the cursor does not skip a track
python src/main.py --remove 0 --steps 1

# A reproducible shuffle
python src/main.py --seed 7 --steps 2

# The total, and what the legacy format says
python src/main.py --total

# Every check
python src/main.py --audit

# The run, the measurements and the checks as JSON
python src/main.py --seed 7 --audit --json run.json
```

**Exit codes:** `0` = every check held · `1` = an audit check failed · `2` = a missing
playlist, a position past the end, a negative step count, or a `--repeat` that is not
`off`/`one`/`all`.

---

# ⚙️ How It Works

```text
_tracks   Kite, Harbour, Ember, Drift, ...        (playlist order)
_order    [0, 1, 2, 3, ...]                       (a permutation of positions)
_cursor    3                                      (a slot in _order)
position  _order[_cursor] -> a playlist position
```

Details worth knowing:

- **The cue points into the order, not the playlist.** `position()` is
  `_order[_cursor]`, so a shuffle can permute the order without touching the tracks and
  without losing what is playing.
- **`remove` remaps, then moves the cue.** Every position above the deleted one drops by
  one; the slot the deleted track occupied is removed from the order; and if that slot was
  at or before the cursor, the cursor moves down one — which is exactly why the track that
  followed still follows.
- **Removing the playing track leaves the previous track current**, so the next `advance()`
  plays the one that took its place. `Drift`, not `Quiet Hours`.
- **Repeat is a mode, not a side effect.** `repeat == "one"` re-records the current track;
  `off` returns `None` at the end; `all` sets the cursor back to 0. Nothing wraps by
  accident.
- **Fisher–Yates from the top down.** For `index` from `len - 1` to 1, swap with
  `randrange(index + 1)` from a `random.Random(seed)`. Every arrangement is equally likely,
  one pass is a permutation, and the seed determines it completely.
- **A shuffle keeps the music playing.** The current position is removed from the new order
  and re-inserted at slot 0, and the cursor becomes 0 — so `_order[0]` is the track you were
  already hearing.
- **The total is a sum of integers.** No float minutes, no rounding: 3863 seconds, printed
  as `1:04:23` by a format that adds hours only when the minutes overflow.
- **Every check runs behind a guard.** A missing measurement is a `FAIL`, not a traceback, so
  the audit reports eleven verdicts no matter how the input was corrupted.

---

# 🧪 Technologies

- Python 3 standard library: `random`, `dataclasses`, `pathlib`, `argparse`, `json`,
  `contextlib`
- pytest 9.1.1

No audio backend, no GUI toolkit, no network. The "player" is a pure state machine over a
text file of durations.

---

# 📚 Concepts Covered

- Why a position is not an index into a collection the user can edit
- Keeping a cue into a permutation instead of into the playlist
- Remapping indices on removal, and moving the cue with them
- Repeat as an explicit mode the advance function consults
- Fisher–Yates, seeded and consumed in order, as a reproducible shuffle
- Why reshuffling before every draw is neither fair nor debuggable
- Durations as integer seconds, formatted with hours and padded fields
- Auditing a state machine by substituting a broken subclass for a mocked function

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**151 tests passed** covering `parse_duration` and its six refusals, `format_duration` across
ten pinned lengths plus a parse round trip, the legacy total string, `Track` and its six
refusals, `parse_playlist` with comments, blank lines, CRLF and its four refusals, the legacy
advance's wrap and its skipped track, the legacy shuffle, `Player` construction and its four
refusals, every movement path, removal (including removing the playing track, removing before
the cursor, and removing every track), shuffle reproducibility, permutation and
current-track preservation, unshuffle, every measurement, eleven audit checks each with a
negative control (including three broken `Player` subclasses), the demo, and every CLI mode
including three exit-code-2 paths and one argparse refusal — **26 `pytest.raises` refusals**
in all.

---

# 🎯 Learning Outcomes

- Explain why `cursor + 1` breaks the moment a track is deleted
- Keep a cue into an order that can be permuted independently of the data
- Remap positions on removal, and decide where the cue goes
- Make a repeat mode a decision the advance function makes, not a wrap it assumes
- Implement Fisher–Yates from a seeded generator and prove it is a permutation
- Explain why reshuffling before each draw is not a shuffle
- Format a duration in hours and padded fields from integer seconds
- Audit a state machine with a deliberately broken subclass

---

# 🚀 Future Improvements

- A queue that can be reordered, with the cue expressed as "the track", not a slot
- Gapless playback boundaries, so a repeat-one is a loop rather than a new play
- A crossfade length per track, still in whole seconds
- A play count per track, so "most played" is a real number
- A real audio backend in front of the same `Player` state machine

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
