<div align="center">

# 🤝 CRM System

### A SQLite customer relationship management system with leads, conversions, interactions, deal pipeline, and KPI reporting.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-3-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

CRM System is a command line application that models a small sales operation: capturing leads, moving them through a funnel, converting them into customers, logging interactions, and managing a deal pipeline through to won or lost.

It demonstrates state machines encoded as CHECK constraints, transactional lead conversion, funnel and pipeline analytics, and a clean separation between data access and presentation.

---

# ✨ Features

- Customer registry with open-pipeline and won-value lookups
- Lead funnel: new → contacted → qualified → converted / lost
- One-step lead conversion that creates and links a customer
- Interaction log (call, email, meeting, note) per customer
- Deal pipeline with stage transitions and close dates
- Follow-ups report for deals closing within N days
- Pipeline summary, lead funnel, and headline KPI report
- Top customers ranking and full-text-ish search
- Interactive menu or one-shot `--demo` mode (re-runnable)
- 12 passing pytest tests

---

# 📂 Folder Structure

```text
CRM_System/
│
├── src/
│   ├── main.py         # CLI entry point, menu and demo runner
│   ├── database.py     # connection, schema and seed data
│   └── queries.py      # CRUD, conversion, pipeline and KPI queries
│
├── tests/
│   └── test_crm.py
│
├── data/               # created automatically (crm.db)
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 10_Database_Projects/CRM_System

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Scripted demo (no input required, safe to run repeatedly)
python src/main.py --demo

# Interactive menu
python src/main.py

# Use a custom database file
python src/main.py --db my_crm.db
```

---

# 🗃️ Schema

- **customers** — `id`, `name`, `email`, `phone`, `company`, `created_on`
- **leads** — `id`, `customer_id`, `name`, `email`, `source`, `status`, `score`, `created_on`
- **interactions** — `id`, `customer_id`, `kind`, `summary`, `created_on`
- **deals** — `id`, `customer_id`, `title`, `value`, `stage`, `close_on`

---

# 🛠 Technologies

- Python
- sqlite3
- argparse
- logging
- pytest

---

# 📚 Concepts Covered

- State machines via CHECK constraints
- Lead-to-customer conversion (multi-table writes)
- Cascade and set-null foreign keys
- Correlated subqueries for per-row metrics
- Funnel and pipeline aggregation
- Date window queries for follow-ups
- Modular programming and type hints
- Test-driven development

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**12 tests passed** covering seeding, CRUD, validation, conversion, interactions, pipeline moves, follow-ups, funnel, and KPIs.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
