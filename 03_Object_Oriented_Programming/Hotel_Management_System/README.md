<div align="center">

# 🏨 Hotel Management System

### The legacy project tracked occupancy with a `status` string — no arrival date, no departure date, any string accepted — so "is room 101 free on the 14th?" was a question the model could not even ask. Its overlap test was inclusive at both ends, which makes a guest leaving on the 12th collide with one arriving on the 12th.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

The old `HotelService` did this:

```python
room.status = "Occupied"
guest = Guest(..., room_id=room.id, check_in_date=datetime.now())
```

and its `rooms` table held `price_per_night = Column(Float)` beside
`phone = Column(String(10))`. Three separate problems hide in those four lines.

**1 · A status string is not a schedule.** There were no arrival or departure
dates, only `datetime.now()` stamped when the row was inserted. Occupancy was
whatever the last `UPDATE` said, so two bookings for the same room on the same
night both "succeeded" and a room could read `"Somehow Occupied"` — any string
is legal.

**2 · The overlap test was inclusive at both ends:**

```python
return start <= other_end and end >= other_start
```

A guest leaving on the 12th and a guest arriving on the 12th both touch the
12th, so the hotel refuses a booking that is perfectly legal.

**3 · `String(10)` does not limit anything in SQLite.** SQLite ignores the
width in a type name, so a forty-character phone number is stored without
complaint. Length has to be enforced in code.

The replacement is three ideas.

**A stay is a half-open interval.** `Stay(check_in, check_out)` covers
`[check_in, check_out)`: the checkout date is not a night. Overlap is then one
line —

```python
return self.check_in < other.check_out and other.check_in < self.check_out
```

— and back-to-back stays do not collide. The demo runs both tests on the same
pair of dates and prints the two different answers.

**Status is a state machine.** Five states, one table:

```text
HELD        -> CONFIRMED | CANCELLED
CONFIRMED   -> CHECKED_IN | CANCELLED
CHECKED_IN  -> CHECKED_OUT
CHECKED_OUT -> (nothing)
CANCELLED   -> (nothing)
```

`booking.check_in(day)` on a held booking is refused, and the error names the
moves that were allowed. `check_in` also refuses a day outside the stay, so a
booking cannot be checked in before it starts.

**A rate is a strategy object.** `Rate.for_night(day)` returns integer cents for
one night and `Rate.total(stay)` sums it, so `FlatRate`, `WeekendRate` (Friday
and Saturday cost more) and `SeasonRate` (a percentage inside a date window) are
interchangeable, and no code branches on a room type.

Money is integer cents throughout, and every night is priced from the rate
object that owns the room.

Standard library only: no ORM, no database file, no network.

---

# ✨ Features

- `Stay` — half-open `[check_in, check_out)`, night enumeration, overlap, containment
- `legacy_overlaps` — the original inclusive test, reproduced so the demo can prove it wrong
- `Rate` — ABC with `for_night`, `total`, `describe`, `to_dict`, value equality and hashing
- `FlatRate`, `WeekendRate` (Fri/Sat), `SeasonRate` (basis-point peak, half-up rounding)
- `Guest` — ten-digit phone, trimmed name, lowercased email, frozen
- `Room` — number, type, capacity, a `Rate`; priced per stay
- `Status` + `ALLOWED` — the five states and the moves that are legal from each
- `Booking` — reference, room, guest, stay, history of moves, folio, price
- `Hotel` — rooms, bookings, clash detection, free rooms, occupancy, revenue
- `Hotel.consistency` — four named invariants, each reported pass or fail
- `load_hotel` / `save_hotel` — JSON round trip, unknown keys refused
- `data/hotel.json` — 6 rooms, 5 bookings (one cancelled), 117,500 cents of revenue
- CLI: `--rooms`, `--availability`, `--book`, `--cancel`, `--check-in`, `--check-out`, `--folio`, `--occupancy`, `--consistency`, `--legacy`, `--write`, `--json`, `--quiet`
- Exit `2` on a `HotelError`; `--demo` always returns `0`
- 235 passing pytest tests

---

# 📂 Folder Structure

```text
Hotel_Management_System/
│
├── src/
│   ├── main.py   # CLI: rooms, availability, book, move, folio, occupancy
│   └── hotel.py  # Stay, Rate + 3 strategies, Guest, Room, Booking, Hotel
│
├── tests/
│   └── test_hotel.py
│
├── data/
│   └── hotel.json  # 6 rooms, 5 bookings, 117,500 cents
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 03_Object_Oriented_Programming/Hotel_Management_System

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo
python src/main.py --demo

# Every room with its rate strategy
python src/main.py

# What is free on those nights
python src/main.py --availability 2026-03-10:2026-03-12
python src/main.py --availability 2026-03-03:2026-03-04

# Take a booking
python src/main.py --book "203:Meera Iyer:9876500000:meera@example.com:2026-04-01:2026-04-03"

# Move one booking through the state machine
python src/main.py --check-in BK-0002 --date 2026-03-03
python src/main.py --check-out BK-0001 --date 2026-03-05
python src/main.py --cancel BK-0002

# Night-by-night pricing
python src/main.py --folio BK-0003

# Sold nights, capacity, revenue
python src/main.py --occupancy 2026-03-02:2026-03-05

# The four invariants
python src/main.py --consistency

# What the legacy model did
python src/main.py --legacy
```

**Exit codes:** `0` = the command ran · `2` = an unknown room or booking, a
clash, a refused move (wrong state or a day outside the stay), a bad phone, a
bad date, a malformed spec, or a missing data file.

---

# 🧠 How It Works

```text
 Stay(check_in, check_out)   half-open: the checkout day is not a night
   │
   ├── nights / each_night / contains / overlaps
   └── legacy_overlaps        inclusive at both ends -> back-to-back collides

 Rate (ABC)
   ├── FlatRate      the same every night
   ├── WeekendRate   Friday and Saturday priced apart
   └── SeasonRate    base + basis points inside a peak window

 Booking  --->  Status  with ALLOWED[status] as the only legal moves
    │              held -> confirmed -> checked_in -> checked_out
    │              any of the first three -> cancelled
    └── price() = room.rate.total(stay)

 Hotel
   ├── clashes(room, stay)   active bookings whose nights intersect
   ├── book()                refuse a clash, then number BK-0001
   ├── occupancy(stay)       sold room-nights, capacity, revenue
   ├── revenue()             every booking that is not cancelled
   └── consistency()         4 invariants
```

Details worth knowing:

- **The checkout day is free.** A booking of `2026-03-02..2026-03-05` occupies
  three nights. `contains("2026-03-05")` is `False`, and the next guest may
  arrive that morning — which the seeded file does on room 101.
- **`check_in` checks the calendar before the state machine.** A booking cannot
  be checked in on a day the room is not held for, even from `CONFIRMED`.
- **Cancelling releases the room.** `holds_room` is `True` for `HELD`,
  `CONFIRMED` and `CHECKED_IN` only, so a cancelled booking is ignored by
  `clashes`, `free_rooms` and `occupancy`. `revenue()` also skips it — the
  money was never earned — while a `CHECKED_OUT` booking still counts.
- **SeasonRate rounds half up, in integers.** `1` cent at `+50%` is `2`, not
  `1`; the calculation is `(cents * (10000 + bp) + 5000) // 10000`.
- **Weekend means Friday and Saturday nights** (`WEEKEND_NIGHTS = (4, 5)`),
  because those are the nights a hotel charges more for.
- **`consistency` checks the invariant, not the total.** A booking marked
  `CHECKED_IN` must have a history whose last date is its arrival date, so a
  record edited by hand fails.

---

# 🛠 Technologies

- Python 3 standard library: `dataclasses`, `datetime`, `enum`, `abc`, `json`,
  `pathlib`, `argparse`, `contextlib`, `sqlite3` (in-memory, to prove the
  `VARCHAR(10)` behaviour), `tempfile`
- pytest 9.1.1

No ORM, no database file, no network.

---

# 📚 Concepts Covered

- Half-open intervals and why `[start, end)` fixes back-to-back bookings
- The inclusive overlap bug, and how it refuses legal bookings
- State machines as a table of allowed moves
- Strategy objects instead of branching on a type string
- Abstract base classes and polymorphic pricing
- Integer cents and half-up rounding in integers
- Frozen dataclasses as validated records
- SQLite type affinity: `VARCHAR(10)` stores forty characters
- Invariants checked by name, and a negative control for each
- Strict ISO date parsing with a render-and-compare round trip

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**235 tests passed** covering date parsing (ISO, objects, seven bad shapes, the
30th of February, non-dates, booleans, labels), `Stay` (nights, enumeration,
containment at both ends, overlaps in four shapes, self-overlap, three
refusals, frozen, equality), the legacy overlap (back-to-back and clashing),
`FlatRate` (per night, total, describe, round trip, equality, hashing,
cross-class inequality, three refusals), `WeekendRate` (all four weekdays,
totals, describe, round trip, a refused negate), `SeasonRate` (outside, the
peak start, after the peak end, totals, half-up both directions, round trip,
three refusals), `rate_from_dict` (non-object, unknown kind, missing price),
`Guest` (trim, lowercase, two name refusals, six phones, four emails, the loose
email rule, frozen, round trip), `Room` (kind, price, equality, hashing, repr,
round trip, five refusals), the state machine (the table itself, every legal
move, every refused move, history dates, `folio`, non-status targets), `Hotel`
(naming, lookup, duplicates, numbering, containment, iteration, clashes,
back-to-back, held and cancelled bookings, free rooms, moves through
references), occupancy (empty, sold nights, revenue, window edges, cancelled,
truncation), revenue (live, cancelled, checked out), the four consistency
checks and four ways to fail them, persistence (round trip, fifteen
refusals, save idempotence), the seeded file (rates, revenue, occupancy, the
back-to-back pair, the cancelled booking, the checked-in history), the demo,
and every CLI mode including JSON, `--write` and `--quiet`.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
