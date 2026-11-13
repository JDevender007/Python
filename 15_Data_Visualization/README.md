<div align="center">

# 🎨 Data Visualization Projects

### A collection of Python projects covering chart galleries, interactive dashboards, statistical plots, animations, and report generation — all runnable offline with `--demo`.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Projects](https://img.shields.io/badge/Projects-5-success?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

This category explores how to turn numbers into things people can see: a gallery of ten chart types from one dataset, a self-contained interactive dashboard (plotly.js embedded inline), statistical charts with inference computed from scratch, animated GIF races from a weekly score table, and publishable HTML/Markdown reports with base64-embedded charts.

Every project runs **fully offline** with `--demo` — bundled deterministic sample data ships with each project, headless rendering (Agg) works without a display, and demos assert their own output. No network, no CDN, no API keys.

---

# 🎯 Learning Objectives

- Choose chart types by question: trend, share, spread, relationship
- Render headlessly with matplotlib's Agg backend (servers, CI, no display)
- Manage figure lifecycles: close figures, never leak plots
- Build self-contained HTML: embedded plotly.js, base64 PNG data URIs, no CDN
- Compose plotly subplots, range sliders, and metric-switcher buttons
- Compute and visualize statistics: quartiles, t-intervals, t-tests, regression
- Animate with `FuncAnimation` + PillowWriter (GIF without ffmpeg)
- Generate reports from a single summary model in multiple formats
- Prove output correctness with demo cross-checks

---

# 📂 Projects

No. | Project | Description | Status
--: | --- | --- | :---:
01 | Chart_Gallery | Ten chart types (line → heatmap) rendered from one CSV to PNGs. | ✅
02 | Interactive_Dashboard | 2×2 plotly dashboard with metric switcher → single offline HTML. | ✅
03 | Statistical_Visualizer | Descriptive stats, Welch t-test, CI + six statistical charts. | ✅
04 | Animated_Chart_Player | Line/bar/area races animated to GIFs with FuncAnimation. | ✅
05 | Report_Generator | HTML + Markdown reports with base64 charts and auto insights. | ✅

---

# 💡 Concepts Covered

- The matplotlib Object Model (figures, axes, legends, colorbars)
- The Agg Backend and Headless Rendering
- Figure Lifecycle Management (why and how to close)
- Pivot Tables for Multi-Series Plotting
- Chart Selection by Analytical Question
- Registries for Pluggable Rendering (`name → function`)
- Self-Contained HTML (inline plotly.js, base64 PNG data URIs)
- Plotly Subplots, Range Sliders, and `updatemenus` Visibility Vectors
- Descriptive Statistics (quartiles, IQR, skewness, SEM)
- t Intervals, Welch's t-test, and p-values from the Incomplete Beta
- Q-Q Plots and the Inverse Normal CDF
- Least-Squares Regression and Correlation Matrices
- `FuncAnimation` Update Functions and Frame Slicing
- PillowWriter GIF Encoding without ffmpeg
- Single-Summary Report Models (HTML + Markdown from one source)

---

# 📁 Repository Structure

```text
15_Data_Visualization/
│
├── Chart_Gallery/
├── Interactive_Dashboard/
├── Statistical_Visualizer/
├── Animated_Chart_Player/
├── Report_Generator/
│
└── README.md
```

Each project contains:

```text
Project_Name/
├── src/              # main.py + library modules
├── tests/            # pytest test suite
├── data/             # bundled deterministic sample data
├── output/           # rendered artifacts (gitignored)
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠 Technologies

- Python 3
- matplotlib (Agg backend, FuncAnimation, PillowWriter)
- plotly (subplots, updatemenus, self-contained HTML export)
- numpy / pandas (aggregations, pivot, validation)
- Pillow (GIF frame counting)
- argparse / json / base64 / dataclasses
- pytest

---

# 📈 Progress

| Project | Status |
| --- | :---: |
| Chart Gallery | ✅ |
| Interactive Dashboard | ✅ |
| Statistical Visualizer | ✅ |
| Animated Chart Player | ✅ |
| Report Generator | ✅ |

**Completed:** **5 / 5 Projects**

---

# ▶️ Quick Start

```bash
cd 15_Data_Visualization/Chart_Gallery

python src/main.py --demo     # offline demo
python -m pytest tests/ -q    # run the tests
```

---

# 📚 Skills Developed

- Data visualization design and chart selection
- Headless/CI-safe rendering pipelines
- Interactive artifact generation (offline HTML)
- Statistical communication (CIs, tests, Q-Q plots)
- Animation authoring without display or ffmpeg
- Templated report generation with escaping
- Deterministic output design and demo self-verification
- Modular Programming and Type Hints
- Automated Testing

---

# 🚀 Key Learning Outcomes

- Render any matplotlib chart without a display (Agg) and prove no figures leak
- Ship a dashboard that opens in any browser with zero network access
- Explain a t-interval and a Welch t-test, and compute both from scratch
- Encode an animation to GIF using only matplotlib + Pillow
- Build a report whose HTML carries its images as base64 data URIs

---

# 🔮 Future Enhancements

- Export animations to MP4 (ffmpeg) when available
- Interactive HTML tables with sorting (no-JS fallback)
- Plotly figure export as standalone `.html` with embedded data
- Chart accessibility pass: colorblind-safe palettes, alt text
- Template themes (light/dark) for generated reports
- PDF report output via headless HTML conversion

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
