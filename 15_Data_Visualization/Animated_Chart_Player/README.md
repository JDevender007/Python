<div align="center">

# 🎬 Animated Chart Player

### Animated GIF charts from a weekly score table — progressive line race, re-sorting bar race, and growing stacked area. matplotlib FuncAnimation + Pillow writer, fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![matplotlib](https://img.shields.io/badge/matplotlib-Animation-orange?style=for-the-badge&logo=matplotlib&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Animated Chart Player turns a CSV of weekly team scores into three kinds of animated GIF: a **line race** where every team's line grows week by week, a **bar race** where horizontal bars re-sort themselves as the leaderboard changes, and a **stacked area** that fills in over the timeline.

Everything runs headless: `FuncAnimation` frames are encoded by matplotlib's **Pillow writer** into a local `.gif` — no display, no browser, no ffmpeg, no network. Frame data (`scores_through`, `rankings_at`) lives in pure functions separate from the drawing code, so the animation logic is unit-testable without rendering anything.

The bundled **deterministic** sample (4 teams × 12 weeks) ships in `data/`. `--demo` renders all three GIFs, counts their frames with Pillow, and cross-checks rankings against the raw frame. **No network, no API keys.**

---

# ✨ Features

- Three animations: `line` (progressive race), `bar` (re-sorting leaderboard), `area` (stacked growth)
- Pure frame-data helpers: `weeks()`, `teams()`, `scores_through()`, `rankings_at()`
- Strict CSV validation: whole-number weeks, finite scores, unique (week, team), complete team×week grid
- Headless GIF rendering via PillowWriter (Agg backend, no ffmpeg)
- GIF frame counting via Pillow for verification
- `--anim` single animation, `--fps` speed control (1–30), `--out` folder
- Bundled deterministic sample: 48 rows (4 teams × 12 weeks)
- 52 passing pytest tests

---

# 📂 Folder Structure

```text
Animated_Chart_Player/
│
├── src/
│   ├── main.py    # CLI: --demo, --file, --anim, --list, --fps, --out
│   └── player.py  # loader, frame helpers, 3 animation builders, GIF writer, demo
│
├── tests/
│   └── test_player.py
│
├── data/
│   └── league_sample.csv   # 48 deterministic rows (4 teams x 12 weeks)
│
├── output/                  # rendered GIFs (created by --demo, gitignored)
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 15_Data_Visualization/Animated_Chart_Player

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: render all 3 GIFs from the bundled sample with cross-checks
python src/main.py --demo

# List available animations
python src/main.py --list

# One animation from your own data, faster playback
python src/main.py --file scores.csv --anim bar --fps 8 --out movies

# All animations from your own data
python src/main.py --file scores.csv
```

Input schema (header row required):

```csv
week,team,score
1,Comets,84.3
```

Every team must appear in every week (complete grid), weeks are whole numbers ≥ 1, scores finite.

**Exit codes:** `0` = success · `2` = usage/schema/fps/animation-name error.

---

# 🧠 How It Works

```text
CSV ──► validate (complete team x week grid) ──► pure frame helpers
                                                      ├─ scores_through(week)
                                                      └─ rankings_at(week)
                                                              │
                                              ┌───────────────┴───────────────┐
                                              ▼               ▼               ▼
                                      line builder      bar builder     area builder
                                      (update fn)       (update fn)     (update fn)
                                              └───────────────┬───────────────┘
                                                              ▼
                                             FuncAnimation(frames=weeks)
                                                              ▼
                                        PillowWriter ──► output/*.gif (local)
```

Each builder owns a figure plus an `update(week)` closure that redraws artists for that frame. `build_animation` wires it into `FuncAnimation` over the week list; `render_animation` encodes it with `PillowWriter(fps)` and closes the figure in a `finally` block so no figures leak.

The bar race re-sorts via `rankings_at()` — sorted by score descending with alphabetical tie-breaking — and moves both the bars and their value labels each frame.

---

# 🛠 Technologies

- Python
- matplotlib (`FuncAnimation`, `PillowWriter`, Agg backend)
- Pillow (GIF frame counting)
- pandas (loading, validation, pivot for the area chart)
- numpy (array helpers)
- argparse / logging
- pytest

---

# 📚 Concepts Covered

- The animation model: update functions, frames, interval
- Headless animation with the Agg backend + PillowWriter
- Why `update()` must return artists (and when blit matters)
- Progressive reveals: slicing a timeline per frame
- Ranking and tie-breaking as a pure function
- Complete-grid validation for time-series panels
- Deterministic GIF output and frame counting
- Figure lifecycle: closing animations to avoid leaks

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**52 tests passed** covering every validation rule (incomplete grids, duplicates, non-finite scores, single team/week), frame helpers (lengths, values, sorted rankings, tie-breaks), all three animations built and rendered (GIF > 5 KB, exactly 12 frames, no figure leaks), deterministic re-render, fps/animation-name errors, demo idempotency, and every CLI path — all offline. Additional cases pin the `scores_through()` prefix contract (empty before week 1, full series past the last week) and the sorted `teams()` helper.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
