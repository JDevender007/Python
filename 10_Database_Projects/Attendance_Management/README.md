<div align="center">

# 📋 Attendance Management

### A SQLite attendance system with daily marking, monthly percentage reports, defaulters tracking, and CSV import/export.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-3-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Attendance Management is a command line application for marking and reporting daily attendance for students or employees. Each person can be marked once per day using an upsert, so re-marking a day updates the record instead of creating a duplicate.

It demonstrates constraints-driven data modelling, upserts, percentage reporting, threshold-based defaulters, and round-trip CSV handling.

---

# ✨ Features

- People registry with codes and group names
- Mark attendance by code with four statuses: present, absent, late, leave
- One record per person per day (UNIQUE constraint + upsert)
- Daily sheet showing everyone including unmarked entries
- Monthly report with attendance percentage per person
- Defaulters report below a configurable threshold
- Status summaries per day or overall
- CSV export and import (round-trip safe)
- Interactive menu or one-shot `--demo` mode (re-runnable)
- 12 passing pytest tests

---

# 📂 Folder Structure

```text
Attendance_Management/
│
├── src/
│   ├── main.py         # CLI entry point, menu and demo runner
│   ├── database.py     # connection, schema and seed data
│   └── queries.py      # marking, reporting and CSV helpers
│
├── tests/
│   └── test_attendance.py
│
├── data/               # created automatically (attendance.db, exports)
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 10_Database_Projects/Attendance_Management

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
python src/main.py --db my_attendance.db
```

---

# 🗃️ Schema

- **people** — `id`, `code`, `full_name`, `group_name`
- **attendance** — `id`, `person_id`, `day`, `status`, `note` with `UNIQUE (person_id, day)`

---

# 🛠 Technologies

- Python
- sqlite3
- csv
- argparse
- logging
- pytest

---

# 📚 Concepts Covered

- Database constraints and upserts (`ON CONFLICT ... DO UPDATE`)
- Unique composite keys
- Left joins for "show everything, even unmarked" reports
- Percentage calculations with `NULLIF` to avoid divide-by-zero
- Threshold filtering in Python and SQL
- CSV import/export round trips
- Modular programming and type hints
- Test-driven development

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**12 tests passed** covering seeding, marking, upserts, validation, monthly percentages, defaulters, clearing days, search, and CSV round-trips.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
