<div align="center">

# 🎨 Data Visualization Projects

### Five ways to turn a table into something a person can look at — and five different reasons the picture can be wrong. A chart that drops a category, a dashboard that needs a CDN, a statistic that does not survive its own quartile rule, an animation that peeks at the future, a report that mines its own insight.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Projects](https://img.shields.io/badge/Projects-5-success?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

Every project here starts from a bundled CSV, validates it by name, renders something, and then proves
its own output before it claims success. None of them touches the network: matplotlib runs on the
headless `Agg` backend, plotly is embedded inline in the HTML it writes, and the sample data ships in
`data/`.

The interesting part is not the rendering. It is that **a picture is an argument**, and each project
is built around a different way that argument fails quietly:

- a chart loses a category and still looks complete
- a dashboard needs a CDN and is therefore not offline at all
- a summary statistic is only as good as the rule used to compute it
- an animation reads the whole table at every frame, so week 1 already knows who wins
- a report invents a causal sentence from a percentage

**The lesson of each project is different, on purpose.** Five variations on "call `plt.plot`" would
teach nothing; five distinct ways a visual can be confidently wrong is the subject.

- **Animated_Chart_Player** — *a frame may only see its own past.* Replaying a completed score table
  frame by frame is not a race: the bar at week 1 is already final. The rebuild slices the frame with
  `week <= t` for every frame, so `scores_through(frame, t)` and `rankings_at(frame, t)` are pure
  functions of the prefix, and the demo renders **3 GIFs of 12 frames each** and asserts the
  leaderboard is sorted at every step — **leader Comets at 100.3**.
- **Chart_Gallery** — *a figure is a resource with a lifetime.* Ten chart functions that each open a
  figure and never close it leak memory until the process dies, and a registry without a contract
  lets one chart type quietly change signature. The rebuild gives all ten a uniform
  `frame -> Figure` contract, closes every figure in a `finally`, and verifies that no figure
  survives a render — **10 charts, figures closed, revenue 2,411,100** across the pivot and the
  summary table.
- **Interactive_Dashboard** — *"interactive" must not mean "online".* A dashboard that loads
  `plotly.js` from a CDN is a blank page on a plane, and a KPI typed into a template is a number
  nobody can check. The rebuild embeds the library inline, computes every headline from the frame it
  loaded, and cross-checks the KPI block against `groupby` results — **17 traces, a 3-button metric
  switcher, and a self-contained HTML file with no remote resources**.
- **Report_Generator** — *one summary model, two renderings, one source of truth.* If the Markdown
  and the HTML each aggregate the frame themselves, they drift; if the HTML interpolates text
  unescaped, a channel called `<b>` becomes markup. The rebuild summarises once, renders twice from
  the same `ReportSummary`, embeds four charts as base64 data URIs, and proves the channel rows
  **partition all 48 rows** with **no external references** in the output.
- **Statistical_Visualizer** — *a statistic is a rule, and the rule has to be stated.* Quartiles have
  several definitions, a t-interval needs a critical value, and a two-sample test must decide whether
  it assumes equal variance. The rebuild implements the incomplete beta function so the p-value is
  computed rather than approximated, uses Welch's t-test, and cross-checks that the groups
  **partition 120 rows**, the quartiles are ordered, and **p = 0.0000** lands in [0, 1] with six
  charts rendered and every figure closed.

**Every claim is checkable.** Each demo prints `Cross-checks OK: ...` with the numbers it verified,
then `Demo completed successfully.`; run it twice and the bytes match, run it with `--quiet` and it
writes nothing at all.

The libraries used are `matplotlib` (Agg), `plotly`, `pandas`/`numpy`, and Pillow for GIF frame
counting. Nothing reads a clock, opens a socket, or writes into the repository: rendered artifacts go
to `output/`, which is gitignored.

---

# 🎓 Learning Objectives

- Choose a chart type from the question being asked: trend, share, spread, relationship
- Render headlessly with the `Agg` backend so charts work on a server with no display
- Close every figure deterministically and prove that none leaked
- Give heterogeneous renderers one contract and register them in a lookup table
- Export a plotly figure to a single HTML file with the runtime embedded inline
- Compose subplots, range sliders and `updatemenus` visibility vectors
- Compute descriptive statistics and state the quartile convention being used
- Build a confidence interval from a t critical value instead of a normal approximation
- Run Welch's t-test and compute its p-value from the incomplete beta function
- Regress two variables and report r and r² from the same fit
- Animate with `FuncAnimation` and encode to GIF with `PillowWriter`
- Slice a data frame by time so a frame cannot see its own future
- Summarise a frame once and render it twice: Markdown and HTML from one model
- Escape interpolated text so data can never become markup
- Assert your own output in `--demo` instead of asserting it in a README

---

# 🗂️ Projects

No. | Project | Description | Tests | Status
--: | --- | --- | --: | :---:
01 | Animated_Chart_Player | Line, bar and area races over 12 weeks; prefix-only slicing, 3 GIFs, frame counting. | 52 | ✅
02 | Chart_Gallery | Ten chart types from one CSV, uniform registry, figure-lifecycle checks, JSON manifest. | 52 | ✅
03 | Interactive_Dashboard | 2×2 plotly dashboard with a metric switcher, KPIs re-derived from the frame, one HTML file. | 50 | ✅
04 | Report_Generator | One summary model rendered to Markdown and HTML with four base64 charts and escaped text. | 51 | ✅
05 | Statistical_Visualizer | Descriptive stats, t intervals, Welch's test, correlation and six statistical plots. | 66 | ✅

**Total: 271 tests.**

---

# 🧠 Concepts Covered

- The matplotlib object model: figures, axes, legends, colorbars, subplots
- Headless rendering with the Agg backend, and why a display is not required
- Figure lifecycle management and leak detection via `plt.get_fignums()`
- Pivot tables as the multi-series input to a chart function
- Chart selection by analytical question, and what each chart type hides
- Registries mapping a name to a callable plus a description
- Self-contained HTML: inline plotly.js, base64 PNG data URIs, no CDN
- Plotly subplots, range sliders, and `updatemenus` visibility vectors
- Descriptive statistics: mean, median, quartiles, IQR, z-scores, outlier fences, skewness
- t critical values and confidence intervals at a stated confidence
- Welch's t-test and a p-value from the regularised incomplete beta function
- Pearson correlation and least-squares regression from the same data
- Q-Q plots and the inverse normal CDF
- `FuncAnimation` update functions, frame slicing, and `PillowWriter` GIF encoding
- Prefix-only slicing so an animation cannot see the future
- Single-summary report models, Markdown and HTML rendering, and HTML escaping
- Deterministic rendering: fixed seeds, fixed sample data, byte-identical re-runs

---

# 📁 Repository Structure

```text
15_Data_Visualization/
│
├── Animated_Chart_Player/
│   ├── src/    player.py, main.py
│   ├── tests/  test_player.py
│   ├── data/   weekly_scores.csv
│   └── output/ *.gif            (gitignored)
│
├── Chart_Gallery/
│   ├── src/    gallery.py, main.py
│   ├── tests/  test_gallery.py
│   ├── data/   gallery_sample.csv
│   └── output/ *.png            (gitignored)
│
├── Interactive_Dashboard/
│   ├── src/    dashboard.py, main.py
│   ├── tests/  test_dashboard.py
│   ├── data/   dashboard_sample.csv
│   └── output/ dashboard.html   (gitignored)
│
├── Report_Generator/
│   ├── src/    report.py, main.py
│   ├── tests/  test_report.py
│   ├── data/   report_sample.csv
│   └── output/ report.md, report.html  (gitignored)
│
└── Statistical_Visualizer/
    ├── src/    stats_viz.py, main.py
    ├── tests/  test_stats_viz.py
    ├── data/   measurements.csv
    └── output/ *.png            (gitignored)
```

Each project has the same shape: all logic in one library module, a thin `main.py` argparse CLI, a
`tests/` suite, deterministic data in `data/`, a pinned `requirements.txt`, a `.gitignore`, and a
`README.md` that states its own defect.

---

# ▶️ Run any project

```bash
cd 15_Data_Visualization/Chart_Gallery

python src/main.py --demo                  # offline, deterministic, exit 0
python src/main.py --demo --quiet          # prints nothing at all
python src/main.py --list                  # the chart catalogue
python src/main.py --chart heatmap --manifest out/manifest.json
python -m pytest tests -q                  # the suite
```

Every project supports `--demo` (plus `--quiet`), `--file <csv>`, `--out <path>` and its own flags
(`--chart`, `--manifest`, `--list`, `--fps`, `--animation`, `--kpis`, `--json`, `--title`). Nothing
opens a connection, and no demo writes into the repository: images, GIFs, JSON and HTML go only where
you point them (or into the gitignored `output/`).

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
3. `--demo` exits 0 and ends with `Cross-checks OK: ...` then `Demo completed successfully.`
4. `--demo` twice produces byte-identical output, and `--demo --quiet` prints nothing at all
5. no non-ASCII byte in `src/`, `tests/` or the text data files

---

# 🎯 Learning Outcomes

This category helps you understand:

- Why a chart type is a claim about your data, not a style choice
- Why an animation must be built from prefixes of a table, never the whole table
- Why "figure closed" is a testable property, not a habit
- Why a dashboard that needs a CDN is not offline
- Why a KPI that is not re-derived from the frame is decoration
- Why quartiles and p-values need their conventions written down
- Why equal-variance is an assumption you choose, not a default you inherit
- Why one summary rendered twice beats two summaries rendered once each
- Why interpolated text must be escaped before it reaches HTML
- How to make a visual demonstration reproducible byte for byte

---

# 🧩 Patterns Included

Parsing — `load_scores`, `load_sample`, `load_data`, `load_measurements`
Values — `ReportSummary`, `StatsReport`
Rendering — `CHART_TYPES`, `render_chart`, `build_dashboard`, `figure_to_html`, `save_report`
Charts — `chart_line`, `chart_area`, `chart_bar`, `chart_histogram`, `chart_box`, `chart_qq`,
`chart_means`, `chart_regression`, `chart_correlation`
Animation — `build_animation`, `render_animation`, `gif_frame_count`, `FuncAnimation`
Statistics — `describe`, `outlier_bounds`, `z_scores`, `t_critical`, `confidence_interval`,
`welch_t_test`, `correlation`, `_regularized_beta`
Reporting — `summarize`, `render_markdown`, `render_html`, `_to_data_uri`, `--json`, `--manifest`
Refusal — `PlayerError`, `GalleryError`, `DashboardError`, `ReportError`, `StatsError`
Testing — headless rendering, figure-leak checks, pinned arithmetic, CLI paths, quiet-mode silence

---

# 🚀 Future Improvements

- A `--batch` runner that renders all five demos and compares their output hashes
- Colour-blind-safe palettes and alt text for every generated chart
- SVG output alongside PNG, so a chart is reviewable in a diff
- PDF reports through a headless HTML-to-PDF step
- MP4 export for the animations when ffmpeg is present, GIF otherwise
- A shared statistical kernel, so the t-test and the correlation share one implementation
- Interactive HTML tables with a no-JavaScript fallback
- A single `audit` harness for the category, so all five report in the same shape

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
