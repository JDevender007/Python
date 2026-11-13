<div align="center">

# 📊 Data Analysis Projects

### A collection of Python projects covering sales, stock market, survey, web traffic, and census analysis — all runnable offline with `--demo`.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Projects](https://img.shields.io/badge/Projects-5-success?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

This category explores how to turn raw CSV files into decision-ready reports: sales orders analysed by period and segment, OHLCV prices turned into technical indicators and risk metrics, survey responses summarised with Likert distributions and NPS, access logs aggregated into traffic profiles, and census indicators weighted correctly by population.

Every project runs **fully offline** with `--demo` — bundled deterministic sample data ships with each project, loaders validate inputs strictly, and demos assert their own math. No network, no APIs, no API keys.

---

# 🎯 Learning Objectives

- Load and validate CSV data with precise, actionable errors
- Aggregate with pandas: resample, groupby, crosstab, corr, quantiles
- Compute and explain weighted vs unweighted averages
- Build time-series buckets (D/W/M/Q/Y) and growth rates
- Implement technical indicators: SMA, EMA, Wilder RSI, MACD, drawdown
- Measure survey sentiment: Likert top/bottom-box, Net Promoter Score
- Profile traffic: status classes, error rates, hourly/daily patterns
- Report design: text tables, ASCII bars, JSON export, PNG charts

---

# 📂 Projects

No. | Project | Description | Status
--: | --- | --- | :---:
01 | Sales Data Analyzer | Order CSV → totals, period trends, growth, segment shares, charts. | ✅
02 | Stock Market Analyzer | OHLCV CSV → SMA/EMA/RSI/MACD, risk metrics, correlations. | ✅
03 | Survey Data Analyzer | Responses → Likert distributions, NPS, group tables, crosstabs. | ✅
04 | Web Traffic Analyzer | Access log → status classes, error rate, hourly/daily profiles. | ✅
05 | Census Data Analyzer | Regional indicators → weighted averages, state splits, correlations. | ✅

---

# 💡 Concepts Covered

- Defensive CSV Loading and Schema Validation
- Resampled Time-Series Bucketing (D/W/M/Q/Y)
- Period-over-Period Growth Rates
- Groupby Aggregations and Revenue Share
- Moving Averages and Trend Smoothing
- OHLCV Bar Invariants and Price Validation
- Technical Indicators (SMA, EMA, RSI, MACD) and Max Drawdown
- Annualized Volatility, Sharpe Ratio, Return Correlation
- Likert Distributions and Top/Bottom-Box Analysis
- Net Promoter Score (Promoters − Detractors)
- Cross-Tabulations with Row Percentages
- Status-Class Partitioning and Error Rates
- Hourly/Daily Traffic Profiling
- Weighted vs Unweighted Averages
- Correlation Matrices and IQR Inequality Ratios

---

# 📁 Repository Structure

```text
14_Data_Analysis/
│
├── Sales_Data_Analyzer/
├── Stock_Market_Analyzer/
├── Survey_Data_Analyzer/
├── Web_Traffic_Analyzer/
├── Census_Data_Analyzer/
│
└── README.md
```

Each project contains:

```text
Project_Name/
├── src/              # main.py + library modules
├── tests/            # pytest test suite
├── data/             # bundled deterministic sample data
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠 Technologies

- Python 3
- pandas (loading, resample, groupby, crosstab, corr)
- matplotlib (optional PNG chart export, Agg backend)
- argparse / json / dataclasses / logging
- pytest

---

# 📈 Progress

| Project | Status |
| --- | :---: |
| Sales Data Analyzer | ✅ |
| Stock Market Analyzer | ✅ |
| Survey Data Analyzer | ✅ |
| Web Traffic Analyzer | ✅ |
| Census Data Analyzer | ✅ |

**Completed:** **5 / 5 Projects**

---

# ▶️ Quick Start

```bash
cd 14_Data_Analysis/Sales_Data_Analyzer

python src/main.py --demo     # offline demo
python -m pytest tests/ -q    # run the tests
```

---

# 📚 Skills Developed

- Exploratory data analysis with pandas
- Validation-first data engineering
- Statistical reporting (weighted means, correlations, distributions)
- Deterministic sample-data design (seeded generation)
- Modular Programming and Type Hints
- Automated Testing
- CI-Friendly CLI Design

---

# 🚀 Key Learning Outcomes

- Explain why population-weighted averages differ from naive means
- Compute and interpret RSI, drawdown, volatility, and Sharpe on price data
- Summarize survey sentiment with Likert boxes and NPS
- Turn access logs into capacity and reliability insights
- Build loaders that reject bad data before it corrupts a report

---

# 🔮 Future Enhancements

- Anomaly detection on sales/traffic time series
- Cohort retention analysis for survey respondents
- Multi-file joins (sales × products × customers)
- Interactive dashboards (plotly) over the same reports
- Forecasting baselines (moving average / exponential smoothing)
- Export to Excel with formatted tables

---

# 🤝 Contributions

Suggestions, improvements, and feedback are welcome. Feel free to open an issue or submit a pull request.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found these projects useful, consider giving this repository a star.

</div>
