<div align="center">

# 🕸️ Web Scraping

### Five projects that each look like "download a page and read the fields" — and each one turned out to be a question about *what a scraped value is*. Is `2.3k` a number or a measurement? Is `2h 15min` a duration or four characters? Is a link's host the site? Is an unreadable date the newest date? The rebuild keeps each defect executable, then removes the reason it was possible.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Projects](https://img.shields.io/badge/Projects-5-success?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

Each of these five projects began as a `requests` + `BeautifulSoup` scraper wrapped in a
`tkinter` window. None of them needs the network any more: every one runs on a bundled
page, reads it with `html.parser` or a plain text file, and reproduces the original defect
exactly — then shows what a value has to be for the defect to be impossible.

The failure in each is never a typo. It is a **definition**: of what the page printed, of
what the field means, of what "the same" means.

**The lesson of each project is different, on purpose.** Five variations on "parse the
HTML" would teach nothing; five different ways a scraper invents a value it never read
teach the subject.

- **Amazon_Price_Tracker** — *money is integer cents and a currency, not a float.*
  `re.sub(r"[^\d.]", "", value)` throws away the symbol, the thousands separator and the
  decimal comma, then calls `float()`: the shop's own euro formatting `1.299,00 EUR`
  becomes **1.299**, a thousand times too small, and nothing raises. A range
  `$1,299.00 - $1,399.00` becomes `0.0`, the same `0.0` a free item reports. And the
  parser took the **first** `.a-offscreen` on the page, which on a discounted page is the
  struck-through list price. The rebuild keeps `Money(cents, code)`, distinguishes a
  decimal separator from a grouping one by position and digit count, keeps a range a
  range, reports an unknown change as `unknown` rather than a zero, and reads the buy box
  by the name the page gives it.
- **GitHub_Repository_Scraper** — *a displayed count is a measurement, not a number.*
  `re.sub(r"[^\d]", "", "2.3k")` is `"23"`, and `1.2m` is `"12"`: the letters are the
  magnitude. `int(float("2.9"))` truncates **2.9k to 2,000**, losing 900 stars silently.
  And reading `2.3k` as exact invents precision the page never showed — it then reports a
  "difference" of 4 against a repository at 2,304 that the page could not distinguish at
  all. The rebuild keeps `Count(amount, step)`, prints the interval each display stands
  for, answers `indistinguishable` when two intervals overlap, and reports a gain over
  time as `+600 to +800` rather than a point.
- **IMDb_Movie_Scraper** — *a runtime is one quantity in one unit.* `"2h 15min"` with the
  units deleted is `"215"` — two hundred and fifteen minutes for a film that runs a
  hundred and thirty-five. The same length printed `"135 min"` then reads as a different
  film seventy minutes apart. `"2:15"` is refused here because it does not say which unit
  is which, `"2h 75min"` is refused because a minute field is below 60, and a series is
  a per-episode runtime **times** its episode count: 24 x 47 min = 1,128 min.
- **Job_Listing_Scraper** — *a link is a structure, resolved by its parts.* The legacy
  validator approved anything with a scheme and a `netloc`, so
  `jobs.example.com.evil.test` — a host that merely *contains* the site's name — was
  followed. `base + href` on `.../jobs/list.html` and `43` builds `.../list.html43`, a
  page that never existed. And a fragment was compared as part of the address, so
  `/jobs/42` and `/jobs/42#apply` were fetched twice. The rebuild resolves against the
  base's **directory**, confines a crawl with **host equality**, deduplicates on what the
  server sees, and keeps every refusal as a sentence.
- **News_Scraper** — *a timestamp is an instant, and "now" is not a fallback.* The legacy
  parser's `except` branch returned `datetime.now()`, so a date it could not read — a
  relative phrase, a prose date, an empty cell — was reported as **published just now**,
  and the freshest article in the feed was the one it understood least. A naive datetime
  subtracted from an aware one raised `TypeError`, which the legacy age turned into
  **0 seconds**: "just now" again. The rebuild keeps `Moment(epoch)` in UTC, requires a
  zone, resolves `3 hours ago` against a **supplied** reading time, orders the feed by the
  instant rather than the printed text, and keeps an unreadable timestamp as `None`.

**Every number is exact and every claim is checkable.** Cents, steps, minutes, hosts and
seconds are integers or byte strings, each demo prints the quantity it derived, and each
project's `audit()` re-derives the result from the data instead of restating the summary
it just printed.

Standard library only: no `requests`, no `beautifulsoup4`, no `lxml`, no `selenium`, no
`tkinter`, no browser, no network, no API keys, no downloads.

---

# 🎓 Learning Objectives

- Read money as integer cents, and tell a decimal separator from a grouping separator
- Refuse a range instead of collapsing it to zero, and keep both ends readable
- Report an unknown value as unknown, never as zero and never as "now"
- Read a rounded figure as an interval, and compare intervals honestly
- Convert a magnitude suffix instead of deleting it, and tell `int()` truncation from rounding
- Convert units by arithmetic, and refuse the shapes where the units are ambiguous
- Resolve a link against the page it was printed on, by the rules of the path
- Confine a crawl with host equality against containment and prefix matching
- Treat a fragment as browser state: not part of the address, not part of the identity
- Store a timestamp as seconds in UTC, and refuse a wall clock with no zone
- Resolve a relative phrase against a supplied reading time, so it can be tested
- Write an `audit()` that returns every check, then force each one to fail

---

# 📁 Projects

No. | Project | Description | Tests | Status
--: | --- | --- | --: | :---:
01 | Amazon_Price_Tracker | Money in cents, both decimal conventions, a range stayed a range, the buy box read by name, `unknown` instead of `0.0`. | 171 | ✅
02 | GitHub_Repository_Scraper | `Count(amount, step)`, intervals that overlap are `indistinguishable`, `2.3k` → 2,300 where the legacy said 23. | 144 | ✅
03 | IMDb_Movie_Scraper | One unit in minutes, `2h 15min` == `135 min`, a series as episodes x runtime, a marathon that never overspends. | 131 | ✅
04 | Job_Listing_Scraper | Directory-relative resolution, host equality, a canonical key without the fragment, nine anchors → six unique pages. | 170 | ✅
05 | News_Scraper | `Moment(epoch)` in UTC, zones required, relative phrases read against a supplied now, feed ordered by instant. | 127 | ✅

**Total: 743 tests.**

---

# 🧠 Concepts Covered

- Money as integer cents and a currency code; half-up rounding written out
- Decimal commas, grouping dots, and the rule that reads both conventions
- Intervals and overlap: why two rounded figures cannot be called "different"
- Magnitude suffixes (`k`, `m`, `b`) and the resolution they imply
- Quantities in one unit, unit conversion by arithmetic, and field ranges
- URL parts, directory-relative resolution, `..`, protocol-relative links, fragments
- Crawl confinement by host equality, canonical keys, first-seen deduplication
- Instants in UTC, naive versus aware datetimes, and the `TypeError` an `except` can hide
- Relative time as an offset from a reading time, and determinism as a design choice
- `html.parser` and a minimal `Element` tree instead of a parser dependency
- Text files as pages: `href<TAB>label`, `id<TAB>title<TAB>timestamp`, line-numbered errors
- Failure as a sentence: `PriceError`, `CountError`, `DurationError`, `UrlError`, `TimeError`
- Audits whose negative controls plant the defect where the check actually looks

---

# 🗂️ Repository Structure

```text
07_Web_Scraping/

├── Amazon_Price_Tracker/
│   ├── src/    prices.py, main.py
│   ├── tests/  test_prices.py
│   └── data/   offer.html, watch.txt
│
├── GitHub_Repository_Scraper/
│   ├── src/    counts.py, main.py
│   ├── tests/  test_counts.py
│   └── data/   repos.html, history.txt
│
├── IMDb_Movie_Scraper/
│   ├── src/    durations.py, main.py
│   ├── tests/  test_durations.py
│   └── data/   titles.html
│
├── Job_Listing_Scraper/
│   ├── src/    urls.py, main.py
│   ├── tests/  test_urls.py
│   └── data/   links.txt
│
└── News_Scraper/
    ├── src/    timestamps.py, main.py
    ├── tests/  test_timestamps.py
    └── data/   feed.txt
```

Each project has the same shape: all logic in one library module, a thin `main.py`
argparse CLI, a `tests/` suite, deterministic data in `data/`, a pinned
`requirements.txt`, a `.gitignore`, and a `README.md` that states its own defect.

---

# ▶️ Run any project

```bash
cd 07_Web_Scraping/Amazon_Price_Tracker

python src/main.py --demo          # offline, deterministic, exit 0
python src/main.py                 # the same work, printed as a reading
python src/main.py --audit         # every check with PASS/FAIL
python -m pytest tests -q          # the suite
```

Every project supports `--demo`, `--quiet` with `--demo` (prints nothing), `--audit`,
`--json <path>`, and flags of its own (`--page`, `--watch`, `--price`, `--range`,
`--target`, `--listing`, `--history`, `--count`, `--compare`, `--runtime`, `--budget`,
`--links`, `--base`, `--resolve`, `--feed`, `--at`, `--timestamp`). Nothing touches the
network, no API key is read, and no page is downloaded: each demo runs on the bundled
data, writes nothing into the repository, and finishes in under two seconds.

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

- Why a value read from a page is a claim about the page, with a resolution and a unit
- Why deleting characters from a number is not parsing it
- What "the same value printed two ways" has to mean for a comparison to be honest
- Why zero is a reading and `None` is the absence of one
- Why a host that contains the site's name is a different site
- Why a relative link is resolved against a directory rather than a string
- Why a fragment is not part of the address, and what deduplication must key on
- Why `datetime.now()` in an `except` branch is a wrong answer, not a safe one
- Why a relative time needs the moment the page was read, as an argument
- How to read HTML with `html.parser` and three lookup methods
- How to write an audit whose every check has a negative control
- How to make a demonstration reproducible byte for byte

---

# 🧰 Patterns Included

Parsing — `parse_price`, `parse_count`, `parse_duration`, `resolve`, `parse_timestamp`
Values — `Money`, `Count`, `Duration`, `Url`, `Moment` (validated at construction)
Comparison — `relation`, `gain`, `same_site`, `dedupe`, `age_text`
Refusal — `PriceError`, `CountError`, `DurationError`, `UrlError`, `TimeError`
Legacy — `legacy_clean_price`, `legacy_clean_number`, `legacy_minutes`, `legacy_valid`, `legacy_fallback`
DOM — `html.parser`, `Element`, `parse_html`, class and tag lookup
Reporting — `Offer.line`, `Repo.star_line`, `Film.minutes_line`, `Link.line`, `Article.line`
Testing — negative controls per audit check, pinned demo output, byte-identical runs

---

# 🚀 Future Improvements

- A shared `--dry-run` that prints the parsed value without the summary
- A second page shape per project, so every lookup is a strategy rather than a name
- A locale table, so a shop that writes `1 299,00` is read without a rule
- Time zones by name (`Europe/Berlin`), so DST is handled rather than assumed
- A crawl frontier and a politeness delay, on top of the same URL parts
- A `robots.txt` reader, reusing the resolution rules
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
