<div align="center">

# 🌐 API Development

### Five projects that each look like "call the endpoint and read the field" — and each one turned out to be a question about *what the wire actually said*. Is `0.0` a temperature or a failure? Is `0.92` dollars-per-euro or euros-per-dollar? Does page 2 hold the next four rows or four rows that moved? Is an empty list an answer? Does a retry create a second order? The rebuild keeps each defect executable, then removes the reason it was possible.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Projects](https://img.shields.io/badge/Projects-5-success?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

Each of these five projects began as a `requests` call (or a `FastAPI` handler) wrapped in
`try/except`, with a `tkinter` window in front of it. None of them needs the network any
more: every one runs on bundled bodies, reads them with `json` and plain text files, and
reproduces the original defect exactly — then shows what a value has to be for the defect to
be impossible.

The failure in each is never a typo. It is a **definition**: of what the body said, of what
the field means, of what "the same request" means.

**The lesson of each project is different, on purpose.** Five variations on "parse the JSON"
would teach nothing; five different ways a client invents an answer the server never gave
teach the subject.

- **Weather_API_Client** — *a fallback is a reading, and a unit conversion is not arithmetic.*
  The legacy reader was `payload["main"]["temp"] - 273.15` inside
  `except (KeyError, TypeError): return 0.0`. A `null`, a quoted string or a missing `main`
  object became **0.0 degrees** — a real temperature, drawn at freezing point — on three of
  the nine bundled bodies. The `- 273.15` subtracted Kelvin from a body whose own `units`
  said `metric`, turning `21.555` into **-251.59 C**. And `21.555` is not the number the
  server sent: `json.loads` gives a double just below the tie, so `int(value * 100)` keeps
  **2155** hundredths where `parse_float=Decimal` keeps **2156**. The rebuild keeps an
  `Observation` that names its unit, refuses a body it cannot type, converts by arithmetic
  only when the units differ, and rounds half-up from decimals instead of trusting a binary
  double.
- **Currency_Converter_API** — *a rate has a direction, a date, and a minor-unit exponent.*
  `0.92` means "one dollar is 0.92 euro". Multiplying euros by it says "one euro is 0.92
  euro", and the error compounds every time the result is converted back:
  `100.00 USD -> 92.00 EUR -> 84.64 USD`. `rates.get(code, 1.0)` invents a rate of one for
  a currency the quote never mentioned, so an unknown code converts to itself and looks
  right. A quote is only good on its own date, and a currency's minor unit is not always
  two digits — **JPY has 0, KWD has 3** — so rounding every result to two places is a
  different number on two of the three exponents. The rebuild keeps `Rate(from, to,
  numerator, denominator)` with the direction spelled out, a quote date that must match the
  requested one, and `divide_half_up` at the target currency's own exponent.
- **GitHub_Profile_Analyzer** — *a page number is an offset into a list that moves.*
  `?page=1, 2, 3...` looks like a cursor and is not: page 1 collects indices 0-3, and if the
  list shifts between requests the next page repeats a row and skips another. The loop
  stopped on `if not data`, so a total that divides evenly by the page size costs one extra
  request — and the legacy loop made that request *before* it could know. The rebuild keeps
  `Page(items, next_cursor)`, follows the cursor the server hands back rather than counting,
  detects a repeated row and calls it `overlap`, and stops when the cursor is absent instead
  of when a page looks empty.
- **News_API_Dashboard** — *a status and a body are two witnesses, and `[]` is five facts.*
  `payload["articles"]` inside `except KeyError: return []` returned an empty list for a
  rate limit, a 404 that said "Nothing matches your query", a proxy error wearing a `200`, a
  body with no `articles` field, and the one query that genuinely matched nothing. Four are
  failures and one is a success, and the caller could not tell which; the 404's sentence was
  discarded with them. `{"articles": null}` handed back `None`, which breaks an iterator a
  hundred lines away. The rebuild classifies each response into `ok`, `empty`, `partial`,
  `error` or `malformed`, keeps the server's own sentence, and uses `totalResults` to tell a
  complete answer from a truncated one.
- **REST_API_with_FastAPI** — *a retried POST is a second POST unless it carries a key.*
  `for _ in range(tries): client.post("/orders", payload)` re-posts when the answer is lost,
  and a server that committed before the connection broke creates the order again: the
  legacy loop left **4 rows where 3 orders were meant to exist**. `return None` after the
  last try made "no answer" and "an answer of nothing" the same value. And a `401` was
  retried exactly like a timeout, three round trips for a token that will never be valid
  again. The rebuild keeps an idempotency key the store dedupes on
  (`create() -> (id, created)`), a `retryable()` that calls `5xx`/`429` worth another try and
  `401`/`400`/`409` final, and a backoff of `1, 2, 4, 8` that is deterministic by
  construction.

**Every number is exact and every claim is checkable.** Cents, hundredths, exponents, page
sizes, row counts and seconds are integers, each demo prints the quantity it derived, and
each project's `audit()` re-derives the result from the data instead of restating the
summary it just printed.

Standard library only: no `requests`, no `httpx`, no `fastapi`, no `pydantic`, no `sqlite3`
schema to migrate, no `tkinter`, no network, no API keys, no downloads.

---

# 🎓 Learning Objectives

- Read a JSON field as a typed value: a number, a string, `null`, or absent — four different facts
- Report an unreadable value as unreadable, never as `0.0` and never as `1.0`
- Convert units only when the body says the units differ, and by arithmetic rather than a constant
- Read a decimal from the digits (`parse_float=Decimal`), not from a binary double
- Give a rate a direction, and refuse to multiply by the inverse
- Tie a quote to its date, and refuse a stale one
- Round at the target currency's own minor-unit exponent (0, 2 or 3)
- Tell an offset page from a cursor, and detect the overlap an offset creates
- Stop a paging loop on the absence of a cursor, not on an empty page
- Read a status and a body as two witnesses, and keep the sentence a failure carries
- Distinguish "the call failed" from "the query found nothing"
- Treat `null` as a shape error, not as an empty collection
- Use a total to tell a complete answer from a truncated one
- Make a POST safe to retry with an idempotency key the server dedupes on
- Decide which statuses are retryable and which are final, instead of retrying everything
- Write an `audit()` that returns every check, then force each one to fail

---

# 📁 Projects

No. | Project | Description | Tests | Status
--: | --- | --- | --: | :---:
01 | Weather_API_Client | Typed observations with a named unit; `0.0` is not a reading; half-up from `Decimal` keeps 2156 where the double keeps 2155. | 167 | ✅
02 | Currency_Converter_API | `Rate(from, to)` with a direction and a date; three minor-unit exponents; 100 USD -> 92 EUR -> 100 USD, not 84.64. | 176 | ✅
03 | GitHub_Profile_Analyzer | Cursors instead of page numbers; an overlap is reported, not silently concatenated; a cursorless page ends the walk. | 178 | ✅
04 | News_API_Dashboard | Five outcomes for five kinds of empty; the 404 keeps its sentence; `totalResults` exposes a truncated page. | 147 | ✅
05 | REST_API_with_FastAPI | One key, one order; `401` final and `503` retryable; a deterministic `1, 2, 4, 8` backoff. | 164 | ✅

**Total: 832 tests.**

---

# 🧠 Concepts Covered

- JSON typing: a float, a quoted number, `null`, a missing key, a missing object
- Unit conversion by arithmetic, and refusing to convert what the body already states
- `parse_float=Decimal` versus the nearest double, and why money never touches `float`
- Rate direction, quote dates, and the arithmetic that exposes an inverted rate
- Minor-unit exponents: JPY 0, USD 2, KWD 3, and rounding at the right one
- Offset paging, cursor paging, overlap, and an off-by-one request at an even total
- HTTP status versus body: `200` carrying an error, `500` carrying HTML, `429` carrying a sentence
- `null` versus `[]` versus a missing field — three different shapes
- Totals and shortfalls: detecting a partial answer from the data
- Idempotency keys, `(id, created)`, and a store that answers a replay instead of repeating it
- Retryable versus final statuses, and exponential backoff with a cap
- Audits whose negative controls corrupt the argument rather than mocking a function

---

# 🗂️ Repository Structure

```text
08_API_Development/
│
├── Weather_API_Client/
│   ├── src/    observations.py, main.py
│   ├── tests/  test_observations.py
│   └── data/   readings.txt
│
├── Currency_Converter_API/
│   ├── src/    rates.py, main.py
│   ├── tests/  test_rates.py
│   └── data/   amounts.txt, quote.txt
│
├── GitHub_Profile_Analyzer/
│   ├── src/    pagination.py, main.py
│   ├── tests/  test_pagination.py
│   └── data/   repos.txt
│
├── News_API_Dashboard/
│   ├── src/    envelopes.py, main.py
│   ├── tests/  test_envelopes.py
│   └── data/   responses.txt
│
└── REST_API_with_FastAPI/
    ├── src/    retries.py, main.py
    ├── tests/  test_retries.py
    └── data/   order.txt
```

Each project has the same shape: all logic in one library module, a thin `main.py` argparse
CLI, a `tests/` suite, deterministic data in `data/`, a pinned `requirements.txt`, a
`.gitignore`, and a `README.md` that states its own defect.

---

# ▶️ Run any project

```bash
cd 08_API_Development/Weather_API_Client

python src/main.py --demo          # offline, deterministic, exit 0
python src/main.py                 # the same work, printed as a reading
python src/main.py --audit         # every check with PASS/FAIL
python -m pytest tests -q          # the suite
```

Every project supports `--demo`, `--quiet` with `--demo` (prints nothing), `--audit`,
`--json <path>`, and flags of its own (`--readings`, `--city`, `--body`, `--amount`,
`--from`, `--to`, `--repos`, `--cursor`, `--page-size`, `--responses`, `--name`,
`--status`, `--kind`, `--order`, `--scenario`, `--tries`, `--key`, `--backoff`). Nothing
touches the network, no API key is read, and no request is sent: each demo runs on the
bundled data, writes nothing into the repository, and finishes in under two seconds.

---

# 🧪 Verify the whole category

```powershell
Get-ChildItem -Directory | ForEach-Object {
    Push-Location $_
    python -m compileall -q src tests
    python -m pytest tests -q
    python src\main.py --demo
    Pop-Location
}
```

The gates each project must pass, and does:

1. `compileall` on `src` and `tests` exits 0
2. `pytest` passes with no skips
3. `--demo` exits 0, prints `Cross-checks OK: ...` and `Demo completed successfully.`
4. `--demo` twice produces byte-identical output, and `--demo --quiet` prints nothing
5. no non-ASCII byte in `src/`, `tests/` or `data/`

---

# 🎯 Learning Outcomes

This category helps you understand:

- Why a fallback value is a claim, and why `0.0` is a worse failure than an exception
- Why deleting a constant from a number is not a unit conversion
- Why a JSON float is not the decimal in the body, and what to do instead
- Why a rate without a direction is only half a rate
- Why a quote without a date is a guess about today
- Why "round to two places" is wrong for a currency with three digits
- Why a page number is an offset, and what an offset does when the list moves
- Why a cursor is the server's statement about where you are
- Why a status code and a body must both be read before calling a response a success
- Why `[]`, `null` and a missing field are three different answers
- Why a retry is a write, and what makes it safe
- Why `401` must not be retried and `503` should be
- How to write an audit whose every check has a negative control
- How to make a demonstration reproducible byte for byte

---

# 🧰 Patterns Included

Parsing — `parse_readings`, `parse_quote`, `parse_pages`, `parse_responses`, `parse_order`
Values — `Observation`, `Rate`, `Page`, `Response`, `Outcome`, `Order`, `Token` (validated at construction)
Comparison — `convert`, `pivot`, `overlap`, `classify`, `retryable`
Refusal — `WeatherError`, `RateError`, `PageError`, `ResponseError`, `RetryError`
Legacy — `legacy_temperature`, `legacy_convert`, `legacy_walk`, `legacy_articles`, `LEGACY_POST`
Arithmetic — `divide_half_up`, `Decimal` parsing, integer cents and minor units
Paging — cursors, overlap detection, a stop rule that does not need an extra request
Reporting — `Observation.line`, `Conversion.line`, `Page.line`, `Outcome.line`, `Run.line`
Testing — negative controls per audit check, pinned demo output, byte-identical runs

---

# 🚀 Future Improvements

- A shared `--dry-run` that prints the parsed value without the summary
- A second body shape per project, so every field read is a strategy rather than a key
- A real `FastAPI` app behind the same `Server` interface, so the script becomes a test client
- A `Retry-After` reader, so a `429` comes back with a time instead of a guess
- A quote store keyed by date, so "today's rate" is a lookup rather than an assumption
- A cursor cache, so a resumed walk costs nothing
- One shared `audit` harness, so all five report the same way

---

# 🤝 Contributing

Contributions are welcome.

1. Fork the repository.
2. Create a feature branch.
3. Commit your changes with a clear message.
4. Push the branch.
5. Open a Pull Request.

---

# 👨‍💻 Author

**Devender J**

Python Developer | Data Analytics Enthusiast | AI & Machine Learning Learner

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found these projects useful, consider giving this repository a star.

</div>
