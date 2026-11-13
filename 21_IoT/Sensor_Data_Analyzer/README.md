<div align="center">

# 📈 Sensor Data Analyzer

### Turn a multi-sensor telemetry export into answers — rolling z-score anomalies, missing-sample gaps, frozen-sensor flatlines, resampling and sensor correlation. pandas only, fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![pandas](https://img.shields.io/badge/pandas-150458?style=for-the-badge&logo=pandas&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

A telemetry export is a CSV nobody reads. The questions an operator actually asks are the five this project answers:

1. **What is normal?** Per-sensor count, mean, standard deviation, min and max.
2. **What is an outlier?** A rolling mean and rolling standard deviation per series, then any reading more than `z` sigma from its own recent mean. Because the window is per-sensor, a spike in one room is not washed out by the level of another.
3. **Where is data missing?** Consecutive timestamps further apart than the expected sample interval, with the number of missing samples computed rather than guessed.
4. **Where did a sensor freeze?** Runs of identical consecutive readings, which is what a stuck ADC or a cached value looks like.
5. **How do the sensors move together?** A Pearson correlation matrix over a timestamp pivot.

The bundled 355-row log contains four deliberate faults at known indices: a **+8 °C spike** in the living room at sample 40, a **−7 °C drop** in the bedroom at sample 70, a **5-sample gap** in the bathroom starting at sample 30, and a **7-sample flatline** in the living room at sample 90. The demo does not merely *print* detection counts — it asserts that the exact injected spike and drop rows are in the flag set, that the gap has exactly 5 missing samples, and that the longest flatline belongs to the living room with length 7. Change the detector and the demo fails.

One subtlety worth knowing: on pandas 2.3.3 + NumPy 2.5.2, `pd.Timedelta(seconds=N)` emits `DeprecationWarning: The 'generic' unit for NumPy timedelta is deprecated`. The whole analysis now uses `pd.to_timedelta(N, unit="s")`, and the test suite is run with `-W error::DeprecationWarning` to keep it that way.

No network, no database, no API keys: `data/readings.csv` ships with the project.

---

# ✨ Features

- Deterministic generator for the bundled log (regenerate it any time with `bundle_readings()`)
- Per-series rolling mean/std with a minimum-periods guard
- Rolling z-score anomaly detection with a configurable window and threshold
- Gap detection with an explicit missing-sample count
- Flatline detection with a configurable minimum run length
- Resampling to any pandas offset (`10min`, `30min`, ...) with row conservation
- Sensor summary and Pearson correlation matrix
- `--demo`, `--readings`, `--window`, `--z`, `--resample`, `--json`, `--quiet`
- Strict flag validation before the CSV is read
- 66 passing pytest tests, zero deprecation warnings

---

# 📂 Folder Structure

```text
Sensor_Data_Analyzer/
│
├── src/
│   ├── main.py      # CLI: --demo, --readings, --window, --z, --resample, --json
│   └── analysis.py  # generator, loading, rolling stats, detectors, report
│
├── tests/
│   └── test_analysis.py
│
├── data/
│   └── readings.csv   # 355 rows, 3 sensors, 4 injected faults
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 21_IoT/Sensor_Data_Analyzer

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: validate the data, detect every injected fault
python src/main.py --demo

# Analyse your own telemetry CSV
python src/main.py --readings data/readings.csv

# Tighter anomaly threshold and a longer window
python src/main.py --readings data/readings.csv --z 2.5 --window 21

# Add a resampled view and export the analysis
python src/main.py --readings data/readings.csv --resample living_room:10min \
                   --json report.json
```

**Input:** a CSV with columns `timestamp,sensor,metric,value` (ISO-8601 UTC timestamps, numeric values).

**Exit codes:** `0` = success · `2` = usage/validation/data error.

---

# 🧠 How It Works

```text
readings.csv ──► validate columns, numeric values, parse UTC timestamps
                        │
                        ▼
        group by (sensor, metric), sort by time
                        │
     ┌──────────────────┼───────────────────┬──────────────────┐
     ▼                  ▼                   ▼                  ▼
 rolling mean/std   timestamp diffs     value diffs        timestamp pivot
 (window W)         > max_gap_s?        run >= min_run?    per sensor
     │                  │                   │                  │
     ▼                  ▼                   ▼                  ▼
 |x - mean| > z*std  Gap(after, before,  Flatline(sensor,   Pearson
 → anomalies         missing samples)    length, value)     correlation
```

Resampling is a plain `resample(rule).agg(["mean", "count"])` with the empty trailing bins dropped, and the demo asserts that the counts sum back to the original row count — so a binning bug cannot hide.

---

# 🛠 Technologies

- Python 3
- pandas (`rolling`, `groupby.transform`, `resample`, `pivot_table`, `corr`)
- NumPy (`isfinite`, `allclose`, `diag`)
- Standard library (`math`, `dataclasses`, `argparse`, `json`)
- pytest

---

# 📚 Concepts Covered

- Rolling statistics and `min_periods` semantics
- Z-score anomaly detection on non-stationary series
- Detecting missing data by timestamp differencing
- Detecting frozen sensors by run-length analysis
- Time-based resampling and row conservation
- Wide-format pivoting for cross-series correlation
- Input validation at the boundary (numeric coercion, empty cells, timestamps)
- Deterministic synthetic data with known ground truth
- Keeping a test suite warning-free (`-W error::DeprecationWarning`)

---

# ✅ Testing

```bash
python -m pytest tests/ -q -W error::DeprecationWarning
```

**66 tests passed** covering generator determinism and shape, CSV loading (missing columns, non-numeric values, bad timestamps, empty cells, empty file), rolling columns and `NaN` warm-up, anomaly detection against both injected faults and clean series, threshold monotonicity, gap detection (count, timestamps, threshold sensitivity, JSON safety) and flatline detection (length, start time, multiple runs, minimum run), resampling bins and conservation, summaries and correlation bounds, report rendering, JSON export, demo idempotency, quiet mode, and every CLI error path.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
