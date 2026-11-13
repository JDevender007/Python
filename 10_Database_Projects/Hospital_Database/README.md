<div align="center">

# 🏥 Hospital Database

### A SQLite hospital management database covering patients, doctors, appointments, billing, and revenue reporting.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-3-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Hospital Database is a command line application that models the core operations of a small clinic: registering patients and doctors, booking and completing appointments, issuing and settling bills, and reporting revenue and doctor workload.

It is built entirely on Python's standard library `sqlite3` module with a normalised schema, foreign keys, constraints, indexes, and seeded sample data so it runs immediately after cloning.

---

# ✨ Features

- Normalised schema: doctors, patients, appointments, bills
- Patient registration with outstanding balance lookup
- Appointment booking, scheduling view, discharge and cancellation
- Bill issuing and payment tracking
- Revenue report by day with collected vs pending split
- Specialty workload report per doctor
- Case-insensitive patient search
- Interactive menu or one-shot `--demo` mode
- 10 passing pytest tests

---

# 📂 Folder Structure

```text
Hospital_Database/
│
├── src/
│   ├── main.py         # CLI entry point, menu and demo runner
│   ├── database.py     # connection, schema and seed data
│   └── queries.py      # CRUD operations and reporting queries
│
├── tests/
│   └── test_hospital_db.py
│
├── data/               # created automatically (hospital.db)
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 10_Database_Projects/Hospital_Database

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Scripted demo (no input required)
python src/main.py --demo

# Interactive menu
python src/main.py

# Use a custom database file
python src/main.py --db my_hospital.db
```

---

# 🗃️ Schema

- **doctors** — `id`, `license_no`, `full_name`, `specialty`, `phone`
- **patients** — `id`, `mrn`, `full_name`, `date_of_birth`, `gender`, `phone`, `blood_group`
- **appointments** — `id`, `patient_id`, `doctor_id`, `scheduled_on`, `slot`, `reason`, `status`
- **bills** — `id`, `appointment_id`, `patient_id`, `amount`, `paid`, `issued_on`

---

# 🛠 Technologies

- Python
- sqlite3
- argparse
- logging
- pytest

---

# 📚 Concepts Covered

- Relational database design
- Foreign keys and referential actions (CASCADE, SET NULL, RESTRICT)
- CHECK constraints and indexes
- SQL joins, grouping and conditional aggregates
- Appointment lifecycle management
- Billing and revenue reporting
- Modular programming
- Test-driven development

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**10 tests passed** covering schema, seeding, registration, booking, discharge, billing, search, scheduling, and reporting.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
