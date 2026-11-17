<div align="center">

# 📊 Data Analysis Projects

### Five CSV-in, report-out tools that each looked like "load the file and average a column" — and each one was really a question about *what the number is*. Is a poverty rate an average of rates or a rate over people? Is a "month" a row count or a resample? Is a return arithmetic or geometric? Is a Likert 1–5 an interval? Is a status code a number or a category? The rebuild keeps each mistake executable, then removes the reason it was possible.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Projects](https://img.shields.io/badge/Projects-5-success?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

Each project loads a bundled CSV, validates it strictly, aggregates it, and prints a report. None of
them needs a network: the sample data ships in `data/`, every loader refuses bad input by name, and
every demo asserts its own arithmetic before it prints a conclusion.

The failure in each is never a typo. It is a **definition**: of what a rate is, of what a period is,
of what a return is, of what an answer means, of what a request is.

**The lesson of each project is different, on purpose.** Five variations on "check the columns" would
teach nothing; five different ways a report can be confidently wrong is the subject.

- **Census_Data_Analyzer** — *a rate is weighted by the people it describes.* Averaging
  `poverty_rate` across 120 regions gives every region one vote, so a 12,000-person county and a
  4,000,000-person county count the same. The rebuild computes `sum(rate × population) /
  sum(population)` for every indicator, partitions the states so the parts add back to the whole,
  and reconciles `population_total`, `households_total` and `poverty_population` against the frame
  it loaded: **28,267,889 people**, ~**5,916,576** below the poverty line, weighted median income
  **$61,478**.
- **Sales_Data_Analyzer** — *a period is a resample, not a group of strings.* Bucketing on the raw
  date text splits one month across two keys the moment a row lands on a different day, and
  period-over-period growth then compares two halves of the same month. The rebuild resamples D/W/M/Q/Y
  with an explicit period code, recomputes stale revenue from `quantity × unit_price` instead of
  trusting the column, keeps revenue in floating dollars only at the display boundary, and proves the
  regions add up: **$173,702.73**.
- **Stock_Market_Analyzer** — *a return is a percentage change, and a drawdown has two dates.*
  `closes.diff()` is not a return, `mean(closes)` is not "the price", and a drawdown reported without
  its peak and trough cannot be checked. The rebuild derives daily returns by `pct_change`, computes
  SMA/EMA with their windows stated, Wilder's RSI with the zero-loss case decided explicitly,
  MACD's three series, and a max drawdown that names both endpoints — then verifies that the
  correlation matrix is symmetric with a unit diagonal, and that the best ticker is the best
  **total return**.
- **Survey_Data_Analyzer** — *a Likert scale is ordinal, so report its boxes and its spread.* A mean
  satisfaction of 3.4 hides whether the survey is polarised or unanimous, and a Net Promoter Score is
  not a percentage of anything you can average across groups. The rebuild reports the distribution,
  top-box and bottom-box percentages with their net, NPS as promoters minus detractors, and a
  cross-tab whose rows sum back to the response count — **distribution sums to 100%**, group weighted
  means agree, **NPS +2**.
- **Web_Traffic_Analyzer** — *a status code is a category, not a number.* `mean(status)` is
  meaningless and `status > 400` calls a `404` an error while missing a `500` series, and an access
  log's timestamps are not all in one offset. The rebuild parses each line into a record with a
  stated format, partitions requests by status class so the classes reconstruct the total, computes
  the error rate once from integers, ranks paths by both count and duration, and keeps hourly and
  daily buckets separate — **1,664 requests**, error rate **4.4%**.

**Every number is exact and every claim is checkable.** Counts and populations are integers; rates,
returns and shares are formatted at a stated precision; each project's `audit()` re-derives its own
result from the loaded frame instead of restating the summary it just printed, and every check has a
negative control that makes it fail.

The libraries used are `pandas` for the aggregation work and the standard library elsewhere. Nothing
in any demo touches the network, reads a clock, or writes into the repository.

---

# 🎓 Learning Objectives

- Weight a rate by the population it describes, and say why the unweighted mean differs
- Reconcile a report against its source frame: totals, partitions and shares must add up
- Choose a resample rule for a period and state the period code it maps to
- Recompute a derived column instead of trusting the copy that shipped in the file
- Distinguish a price series from its returns, and an arithmetic mean from a geometric one
- Compute a drawdown with both endpoints named, and annualise volatility at a stated frequency
- State the zero-loss case of an RSI instead of letting a division by zero decide it
- Report an ordinal scale as a distribution, a top box and a net, not as a bare mean
- Compute a Net Promoter Score as promoters minus detractors on a 1–10 scale
- Cross-tabulate two categories and prove the rows sum to the response count
- Treat a status code as a category and a status class as a partition of the total
- Rank by more than one key, and keep count-based and duration-based rankings apart
- Write an `audit()` whose every check fails when its argument is corrupted

---

# 🗂️ Projects

No. | Project | Description | Tests | Status
--: | --- | --- | --: | :---:
01 | Census_Data_Analyzer | Population-weighted indicators, state partitions that add back to the total, correlation and income-IQR ratios. | 50 | ✅
02 | Sales_Data_Analyzer | D/W/M/Q/Y resampling, rebuilt revenue, growth between true periods, segment partitions and a trend average. | 52 | ✅
03 | Stock_Market_Analyzer | Returns, SMA/EMA, Wilder RSI, MACD, max drawdown with both dates, annualised volatility and correlation. | 51 | ✅
04 | Survey_Data_Analyzer | Likert distribution, top/bottom box, NPS, age and tenure summaries, group tables and a cross-tab. | 50 | ✅
05 | Web_Traffic_Analyzer | Access-log parsing, status-class partitions, integer error rate, top and slowest paths, hourly buckets. | 53 | ✅

**Total: 256 tests.**

---

# 🧠 Concepts Covered

- Weighted versus unweighted means, and what the weights have to be
- Validation with named refusals: columns, dtypes, ranges, duplicates, invariants
- Resampling a time series into D/W/M/Q/Y buckets with an explicit code
- Period-over-period growth and a rolling average as a trend, not a forecast
- `groupby` aggregations that must partition their input
- Percentage change, cumulative return, CAGR, annualised volatility, Sharpe ratio
- Moving averages with stated windows and a defined warm-up region
- Wilder smoothing for RSI, and the zero-loss boundary
- Maximum drawdown as a peak-to-trough pair of dates, not a single number
- Ordinal data: distributions, boxes and nets instead of a bare mean
- Net Promoter Score on a 1–10 scale, and why it is not a percentage to average
- Cross-tabulation and row-sum reconciliation
- Log-line parsing with a stated field layout and a strict status vocabulary
- Integer error rates and status classes as a partition
- Audits that re-derive from the source frame, with a negative control per check

---

# 📁 Repository Structure

```text
14_Data_Analysis/
│
├── Census_Data_Analyzer/
│   ├── src/    census_analyzer.py, main.py
│   ├── tests/  test_census_analyzer.py
│   └── data/   census_sample.csv
│
├── Sales_Data_Analyzer/
│   ├── src/    sales_analyzer.py, main.py
│   ├── tests/  test_sales_analyzer.py
│   └── data/   sales_sample.csv
│
├── Stock_Market_Analyzer/
│   ├── src/    stock_analyzer.py, main.py
│   ├── tests/  test_stock_analyzer.py
│   └── data/   stocks_sample.csv
│
├── Survey_Data_Analyzer/
│   ├── src/    survey_analyzer.py, main.py
│   ├── tests/  test_survey_analyzer.py
│   └── data/   survey_sample.csv
│
└── Web_Traffic_Analyzer/
    ├── src/    traffic_analyzer.py, main.py
    ├── tests/  test_traffic_analyzer.py
    └── data/   traffic_sample.csv
```

Each project has the same shape: all logic in one library module, a thin `main.py` argparse CLI, a
`tests/` suite, deterministic data in `data/`, a pinned `requirements.txt`, a `.gitignore`, and a
`README.md` that states its own defect.

---

# ▶️ Run any project

```bash
cd 14_Data_Analysis/03_Stock_Market_Analyzer

python src/main.py --demo          # offline, deterministic, exit 0
python src/main.py --file data/stocks_sample.csv --json out.json
python src/main.py --audit         # every check with PASS/FAIL
python -m pytest tests -q          # the suite
```

Every project supports `--demo`, `--quiet` with `--demo` (prints nothing), `--audit`, `--json <path>`
and `--file <csv>`, plus flags of its own (`--top`, `--period`, `--segment`, `--chart`, `--window`,
`--ticker`, `--group`, `--since`, `--until`). Nothing opens a connection and no demo writes into the
repository: JSON and chart output go only where you point them.

---

# ✅ Verify the whole category

```powershell
Get-ChildItem -Directory | ForEach-Object {
    Push-Location $_
    python -m compileall -q src tests
    python -m pytest tests -q
    python src\main.py --demo
    python src\main.py --demo --quiet
    Pop-Location
}
```

The gates each project must pass, and does:

1. `compileall` on `src` and `tests` exits 0
2. `pytest` passes with no skips, 50+ tests
3. `--demo` exits 0, prints `Cross-checks OK: ...` and `Demo completed successfully.`
4. `--demo` twice produces byte-identical output, and `--demo --quiet` prints nothing at all
5. no non-ASCII byte in `src/`, `tests/` or the text data files

---

# 🎯 Learning Outcomes

This category helps you understand:

- Why an average of rates is not the rate of the whole
- Why a report that cannot be reconciled against its input is not evidence
- Why a date string is not a period, and a resample rule is a decision
- Why a shipped derived column is a claim you should recompute
- Why a mean price is not a return, and a drawdown needs two dates
- Why an RSI needs its zero-loss case stated
- Why ordinal answers belong in a distribution, not a mean
- Why NPS is a difference of percentages, not an average
- Why a status code must never be averaged
- How to write an audit whose every check has a negative control
- How to make a demonstration reproducible byte for byte

---

# 🧩 Patterns Included

Parsing — `load_census`, `load_sales`, `load_prices`, `load_survey`, `parse_log_line`
Values — `CensusReport`, `SalesReport`, `MarketReport`, `TickerStats`, `SurveyReport`, `TrafficReport`
Aggregation — `resample`, `groupby`, `crosstab`, `corr`, `quantile`, `value_counts`
Comparison — weighted versus unweighted means, segment partitions, row sums, partitions of a total
Refusal — `CensusError`, `SalesError`, `StockError`, `SurveyError`, `TrafficError`
Rendering — `render_report`, `to_dict`, `--json`, ASCII charts in the sales demo
Arithmetic — `pct_change`, `sma`, `ema`, `rsi`, `macd`, `max_drawdown`, `nps_scores`
Reporting — period tables, growth lines, top-N rankings, hourly and daily buckets
Testing — exact pinned numbers, validation refusals, negative controls per audit check

---

# 🚀 Future Improvements

- A shared `--batch` runner that executes all five demos and compares their output hashes
- Integer-cent arithmetic for the sales path, so no dollar amount is ever a float
- Seasonality-aware growth in the sales analysis, instead of period-over-period only
- Bootstrap confidence intervals for the survey percentages
- Log parsing for a second, documented format, to show the format is a parameter
- A single `audit` harness for the category, so all five report in the same shape
- Chart output to a static SVG, so the reports are reviewable in a diff

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
