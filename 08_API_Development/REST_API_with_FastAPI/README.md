<div align="center">

# 🔁 REST API with FastAPI

### The legacy retry wrapped `client.post()` in `for _ in range(tries)`. A connection that timed out *after* the server committed the write left the client certain it had failed, so the loop posted again — and the customer was charged twice. Four rows where three orders were meant to exist.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

```python
def post(payload, tries=3):
    for _ in range(tries):
        try:
            return client.post("/orders", payload)
        except Exception:
            continue
    return None
```

**1 → Retrying a POST is creating a second resource.** A connection that breaks after the
server committed the write leaves the client certain it failed. The loop tries again, the
server creates a second order, and nothing in either request says "this is the same order
as before".

**2 → `return None` erases the difference between "no answer" and "an answer of nothing".**
The order may well exist. The caller gets `None`, treats it as "nothing happened", and the
only record of the truth is in the server's table.

**3 → A `401` is not retryable.** An expired token fails the first attempt and will fail the
second and third for the very same reason. Three attempts cost three round trips and bury
the cause behind a generic failure.

**4 → A retry with no wait is not a retry, it is a burst.** The three attempts leave the
socket as fast as the loop can run — precisely what a service that is already struggling
does not need.

**5 → Safety needs two separate things, and neither is a retry count.** The request needs an
**idempotency key** the server can dedupe on, and the client needs to know which statuses
are worth another attempt (`5xx`, `429`, a timeout) and which are final (`401`, `400`,
`409`).

Five scripts, each run by both loops over an identical server:

```text
scenario              at mode    attempts outcome         id    rows waited  statuses
flaky                  0 legacy         3 created         1        1      0  504 504 201
flaky                  0 keyed          3 created         1        1      3  504 504 201
commit-then-timeout    0 legacy         2 created         2        2      0  504 201
commit-then-timeout    0 keyed          2 created         1        1      1  504 201
commit-then-silence    0 legacy         3 gave-up         -        1      0  504 504 503
commit-then-silence    0 keyed          3 gave-up         -        1      3  504 504 503
unavailable            0 legacy         3 gave-up         -        0      0  503 503 503
unavailable            0 keyed          3 gave-up         -        0      3  503 503 503
expired-token         60 legacy         3 unauthorized    -        0      0  401 401 401
expired-token         60 keyed          1 unauthorized    -        0      0  401
```

| the script | what the client sees | legacy | keyed |
|---|---|---|---|
| `flaky` | two timeouts, then a `201` | **1 row, id 1** | 1 row, id 1 |
| `commit-then-timeout` | committed, answer lost, then a `201` | **2 rows, id 2** — charged twice | 1 row, id 1 |
| `commit-then-silence` | committed, answer lost, then `503` ×2 | 1 row, `None` returned | 1 row, `None` returned |
| `unavailable` | `503` three times | 0 rows, 3 attempts, no wait | 0 rows, 3 attempts, waited 3 |
| `expired-token` | a token one second past its expiry | **3 attempts** at `401` | **1 attempt** at `401` |

Across the five scripts, three orders were meant to exist. The keyed loop left **3** rows.
The legacy loop left **4** — the extra one is the order that was committed and then
created a second time.

The demonstration is offline: one bundled order, one bundled token, and five scripted
exchanges. Standard library only: no `requests`, no HTTP client, no FastAPI install.

---

# ✨ Features

- `Token` — `issued`, `lifetime`, `expires_at()`, `valid_at()`, `remaining_at()`; **half-open**,
  so `issued <= now < issued + lifetime`
- `Order` — whole cents only (`quantity × unit_cents`), never a float
- `Reply` — a status, an id the client may or may not have learned, and the sentence that says
  why; `created()`, `retryable()`
- `Store` — `create()` returns `(id, created)` and dedupes on an idempotency key, so the second
  attempt is **answered, not repeated**; `rows()`, `keys()`, `order()`
- `Server` — a script of what each attempt meets; the token is checked **before** the script, so
  an expired token is always `401` and no script entry can rescue it
- `backoff_delays()` — `1, 2, 4, 8` up to the cap, **deterministic by construction**: a demo that
  printed a random number could not be checked against anything
- `legacy_post()` — the four legacy lines, executable: no key, no wait, and it retries a `401`
  exactly like a timeout
- `post_with_key()` — one key, a growing wait, and a `401` that stops it dead
- `Run` — the replies, the total wait, the id and the rows; `attempts()`, `statuses()`, `last()`
- `audit` — eleven named checks, every one falsifiable by handing in a corrupted run, a
  corrupted wait schedule, or a store factory that is wrong on purpose
- CLI: `--order`, `--scenario`, `--tries`, `--key`, `--backoff`, `--audit`, `--json`,
  `--quiet`, `--demo`
- 164 passing pytest tests

---

# 📂 Folder Structure

```text
REST_API_with_FastAPI/
│
├── src/
│   ├── main.py     # CLI: scenarios, backoff, the audit, JSON export
│   └── retries.py  # tokens, orders, the deduping store, both loops, the audit
│
├── tests/
│   └── test_retries.py
│
├── data/
│   └── order.txt   # quantity 3, unit-cents 4499, issued 0, lifetime 60, now 0
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 08_API_Development/REST_API_with_FastAPI

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: five scripts, both loops, eleven checks
python src/main.py --demo

# Every scenario, both loops, one line each
python src/main.py

# One script
python src/main.py --scenario commit-then-timeout
python src/main.py --scenario expired-token

# The wait schedule for 1 to 5 tries
python src/main.py --backoff

# Every check with its verdict
python src/main.py --audit

# Five tries instead of three, with your own key
python src/main.py --tries 5 --key order-9c1d

# All runs as JSON
python src/main.py --json runs.json
```

**Exit codes:** `0` = every check held · `1` = an audit check failed (e.g. `--scenario
flaky --audit`, where one script cannot satisfy checks about the other four) · `2` = a bad
try count, an unknown scenario, a key with a space, a missing bundle, or a bundle that cannot
be parsed.

---

# ⚙️ How It Works

```text
Server.post(order, key, now)
  ├── token expired at `now` ?  ->  401, and the script never runs
  ├── take the next scripted step
  ├── "ok"                   ->  create  ->  201 + the id
  ├── "commit-then-timeout"  ->  create  ->  504, id lost
  ├── "timeout"              ->  nothing created  ->  504
  ├── "unavailable"          ->  nothing created  ->  503
  └── "unauthorized"         ->  401
```

```text
legacy_post                post_with_key
  no key                      one key, sent every attempt
  no wait                     wait 1, then 2, up to the cap
  retries 401 as if it        retryable() decides: 5xx/429 yes,
  were a timeout              401/400/409 no
  break on 201 only           break on 201 or a final status
```

Details worth knowing:

- **The token is checked before the script.** That is what makes `expired-token` honest: the
  three `"ok"` steps in its script can never be reached, so the legacy loop burns all three
  tries on `401` and the keyed loop stops at one.
- **`Store.create` returns two things, not one.** `(id, created)` is the difference between
  "here is your order" and "here is the order you already made" — a client that only gets an
  id cannot tell a replay from a duplicate.
- **The committed-then-lost order is the whole lesson in one row.** The store has the order,
  the client has a `504`, and only the key can reconnect them.
- **A timeout creates nothing; a commit-then-timeout creates exactly one row.** The two are
  indistinguishable to the client and completely different at the server, which is why the
  script has both.
- **The waits are `(1, 2, 4, 8)` and never vary.** A check recomputes the schedule from the
  tuple it was handed, so a schedule that stops growing fails it.
- **Two store checks each get their own store.** They take a **factory**, so a sibling check
  cannot leave behind the rows that make the next claim true.
- **A broken input is a `FAIL`, not a traceback.** Every check runs behind a guard, because a
  negative control hands in a `Run` written past the constructor with `object.__new__` —
  `Run` refuses to be built wrong on purpose.

---

# 🧪 Technologies

- Python 3 standard library: `dataclasses`, `pathlib`, `argparse`, `json`, `contextlib`
- pytest 9.1.1

No `requests`, no HTTP client, no FastAPI, no network. The order and the token are bundled.

---

# 📚 Concepts Covered

- Why retrying a non-idempotent request is a duplication bug, not a reliability feature
- Idempotency keys: the server dedupes, the client retries, the customer is charged once
- Which statuses are worth another attempt and which are final
- Exponential backoff with a cap, and why a demo's schedule must be deterministic
- The difference between a timeout (nothing happened) and a lost answer (something happened)
- Checking authentication before executing a handler
- Audits whose negative controls corrupt the *arguments* instead of mocking a function

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**164 tests passed** covering `Token` and its four refusals, `Order` and its three, `Reply`
and its four, `Store` dedupe and its four, `Server` scripting and its four, the wait schedule
and its four, both loops over every scripted ending, `Run` and its five refusals, the bundle
parser and its five errors, a missing bundle, the five scenarios and their offsets, eleven
audit checks each with a negative control, the demo, and every CLI mode including six
exit-code-2 paths and one exit-code-1 path — **39 `pytest.raises` refusals** in all.

---

# 🎯 Learning Outcomes

- Explain why `for _ in range(3): post()` can charge a customer twice
- Say what an idempotency key buys you that a retry count does not
- Tell a timeout from a lost answer, and know which one leaves a row behind
- Decide that a `401` is final and a `503` is not, without guessing
- Write a backoff that grows, is capped, and is the same every run
- Check a token before running a handler, so a script cannot rescue an expired request
- Audit a claim about row counts by handing in a run that has the wrong count

---

# 🚀 Future Improvements

- A `Retry-After` reader, so a `429` comes back with a time instead of a guess
- A real FastAPI app behind the same `Server` interface, so the script becomes a test client
- A key derived from the order's content hash rather than a constant
- A store that persists, so a crash mid-retry can be inspected afterwards
- Jitter on the backoff, with a seeded generator so the demo stays checkable

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
