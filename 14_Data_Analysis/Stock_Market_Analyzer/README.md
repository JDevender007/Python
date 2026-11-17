<div align="center">

# 📈 Stock Market Analyzer

### Analyse a local OHLCV CSV — technical indicators (SMA/EMA/RSI/MACD), risk statistics, drawdowns, and cross-ticker correlations. Fully offline on bundled synthetic data.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![pandas](https://img.shields.io/badge/pandas-Data%20Analysis-orange?style=for-the-badge&logo=pandas&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Stock Market Analyzer turns a local OHLCV (open/high/low/close/volume) CSV into a full technical and risk report: total return, CAGR, annualized volatility, Sharpe ratio, max drawdown with its peak/trough dates, best/worst days, SMA/EMA trend position, Wilder RSI, MACD histogram, and a return-correlation matrix across tickers.

The loader validates bar consistency — `high` must sit above open/close/low, `low` below them, prices positive, no duplicate `(date, ticker)` rows — so a malformed file fails fast with a precise message instead of producing nonsense numbers.

Everything runs on local files. The bundled **deterministic** sample (3 synthetic tickers × 504 trading days) ships in `data/`, and `--demo` prints the full report with cross-checks. **No network, no market feeds, no API keys.** Synthetic data proves nothing about real markets — this is an analytics exercise, not investment advice.

---

# ✨ Features

- Strict OHLCV validation: bar consistency, positivity, duplicates, ticker normalization
- Indicators: SMA, EMA, Wilder RSI(14), MACD line/signal/histogram
- Risk metrics: annualized volatility, Sharpe (rf=0), CAGR, max drawdown with peak→trough dates
- Cross-ticker return-correlation matrix (symmetric, diagonal = 1)
- Per-ticker detail: trend vs SMA, best/worst day, drawdown window
- JSON report export and PNG price chart (matplotlib Agg, headless)
- Bundled deterministic sample: ALPHA / BETA / GAMMA, 504 days each (1,512 bars)
- 51 passing pytest tests

---

# 📂 Folder Structure

```text
Stock_Market_Analyzer/
│
├── src/
│   ├── main.py             # CLI: demo, --file, --ticker, --window, --json, --chart
│   └── stock_analyzer.py   # loading, indicators, stats, report, demo
│
├── tests/
│   └── test_stock_analyzer.py
│
├── data/
│   └── stocks_sample.csv   # 1,512 deterministic synthetic bars (3 tickers × 504 days)
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 14_Data_Analysis/Stock_Market_Analyzer

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: analyse the bundled sample with cross-checks
python src/main.py --demo

# Analyse your own OHLCV CSV
python src/main.py --file stocks.csv

# Single ticker, custom SMA window
python src/main.py --file stocks.csv --ticker ALPHA --window 50

# JSON report + price chart
python src/main.py --file stocks.csv --json report.json --chart prices.png
```

Input schema (header row required):

```csv
date,ticker,open,high,low,close,volume
2023-01-02,ALPHA,119.42,121.05,118.66,120.31,2841937
```

**Exit codes:** `0` = success · `2` = usage/schema/file error.

---

# 🧠 How It Works

```text
CSV ──► validate bars ──► per-ticker series
                              │
              ┌───────────────┼────────────────┐
              ▼               ▼                ▼
         indicators       risk metrics     correlation
        SMA/EMA/RSI     vol/Sharpe/CAGR    across tickers
           MACD          max drawdown
              └───────────────┼────────────────┘
                              ▼
                     MarketReport → text / JSON / PNG
```

`max_drawdown` walks the running peak and measures the worst decline from it, reporting the real calendar dates of the peak and trough. `rsi` uses Wilder's smoothing; a series with no down-moves returns exactly 100 (not 50).

---

# 🛠 Technologies

- Python
- pandas (loading, rolling/ewm indicators, pivot correlations)
- matplotlib (optional PNG export, Agg backend — headless)
- argparse / json / logging
- pytest

---

# 📚 Concepts Covered

- OHLCV bar invariants and defensive data loading
- Simple vs. exponential moving averages and lag behavior
- Wilder smoothing for RSI and its boundary cases (no losses → 100)
- MACD construction from fast/slow EMA spans
- Drawdown analysis: running peak, peak→trough windows
- Annualized volatility and Sharpe ratio from daily returns
- Return correlation via pivot + `pct_change`
- Deterministic synthetic market generation (GBM with fixed seeds)

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**51 tests passed** covering every validation rule (bar consistency, duplicates, positivity), indicator math against hand-computed series, drawdown date reporting, per-ticker and market-level analysis, correlation symmetry, rendering, demo idempotency, and every CLI path — all offline with bundled data.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
