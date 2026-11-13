<div align="center">

# 👥 Customer Segmentation

### k-means clustering with a silhouette sweep, ranked value profiles, and new-customer assignment — fully offline on bundled data.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-Clustering-FF7A00?style=for-the-badge&logo=scikitlearn&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Customer Segmentation turns a customer table (purchase frequency, average spend, tenure) into actionable groups. It **standardises** the features, sweeps **k = 2..8** with silhouette scores to pick a cluster count automatically, fits `KMeans`, and builds **value profiles**: each cluster's size, share, mean behaviour, and a `value_index` (monthly spend per customer) ranked from most to least valuable.

The loader validates every column: unique non-empty customer IDs, finite numerics inside plausible ranges, at least 10 customers, and at least two distinct values per feature (a constant feature makes clustering meaningless). The fitted scaler and model travel together in a `SegmentationResult`, so `assign()` clusters brand-new customers consistently with training.

Everything runs on local files: the bundled **deterministic** sample (360 customers, 3 latent groups) ships in `data/`, and `--demo` clusters it, prints the k-sweep and profiles, and cross-checks its own output. **No network, no dataset downloads.**

---

# ✨ Features

- Automatic k selection: silhouette sweep over k = 2..8 (or force `--k`)
- `StandardScaler` + `KMeans` (10 inits, seeded) in one reproducible flow
- Ranked cluster profiles: size, share, freq/spend/tenure means, value index
- `assign()` for new customers using the fitted scaler + model
- Strict validation: unique IDs, finite ranges, no constant features, ≥ 10 rows
- JSON export of the sweep and all cluster profiles
- Deterministic: identical labels across runs
- Bundled deterministic sample: 360 customers, 3 latent groups
- 45 passing pytest tests

---

# 📂 Folder Structure

```text
Customer_Segmentation/
│
├── src/
│   ├── main.py     # CLI: --demo, --file, --k, --json, --quiet
│   └── segment.py  # loading, sweep, k-means, profiles, report, demo
│
├── tests/
│   └── test_segment.py
│
├── data/
│   └── customers.csv   # 360 deterministic rows (3 latent groups)
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 16_Machine_Learning/Customer_Segmentation

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: auto-k clustering + profiles + cross-checks
python src/main.py --demo

# Your own data (k chosen by silhouette)
python src/main.py --file customers.csv

# Force 4 clusters and dump JSON
python src/main.py --file customers.csv --k 4 --json segments.json
```

Input schema (header row required):

```csv
customer_id,freq_per_month,avg_spend,tenure_months
C0001,7.0,55.0,24.0
```

**Exit codes:** `0` = success · `2` = usage/schema/k error.

---

# 🧠 How It Works

```text
CSV ──► validate ──► StandardScaler ──► silhouette sweep (k = 2..8)
                                              │
                                              ▼  argmax silhouette
                                     KMeans(k*) fit ──► labels
                                              │
                                              ▼
                          profiles (size, means, value_index, rank)
                                              │
                        ┌─────────────────────┴─────────────────────┐
                        ▼                                           ▼
                 report + JSON                              assign(new rows)
```

- **Why standardise?** k-means uses distance; `avg_spend` in dollars would dwarf `freq_per_month` and own the clusters. `StandardScaler` puts every feature on equal footing.
- **Why silhouette?** It measures how similar each point is to its own cluster vs the nearest other one (−1 … 1). Sweeping k avoids the classic "k-means always needs to be told k" problem — here the data itself says **k = 3** (score 0.704), matching the three latent groups it was generated from.
- **Ranking**: clusters are sorted by `value_index = mean(freq × spend)` — the revenue a typical member generates per month — so rank 1 is always the segment worth marketing to first.

---

# 🛠 Technologies

- Python
- scikit-learn (`StandardScaler`, `KMeans`, `silhouette_score`)
- pandas / numpy (loading, validation, groupby profiles)
- argparse / json / logging
- pytest

---

# 📚 Concepts Covered

- Feature scaling and why distance-based models need it
- The k-means algorithm: centroids, convergence, `n_init` restarts
- Silhouette analysis and choosing k automatically
- Cluster profiling and value ranking
- Reproducible clustering with fixed `random_state`
- Consistent train/assign pipelines (scaler + model as one unit)
- Validating clustering inputs (constant features, minimum n)
- Deterministic demo design with self-asserting cross-checks

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**45 tests passed** covering every validation rule (IDs, ranges, constants, row counts), silhouette sweep bounds and determinism, k selection and forced k, label partitioning, profile math (sizes sum to n, shares to 100%, ranks 1..k, cluster means recomputed from raw rows), `assign()` reproducing training labels and routing new customers to the right tier, demo idempotency, and every CLI path — all offline.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
