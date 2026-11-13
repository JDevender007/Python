<div align="center">

# 🗄️ Employee Database

### A SQLite-backed employee records system with full CRUD, powerful reporting queries, and a friendly command line interface.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-3-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Employee Database is a command line application that manages departments and employees using Python's built-in `sqlite3` module. It ships with a normalised schema, sample data, full CRUD operations, and business reports such as department salary summaries, top earners, and total payroll cost.

The project demonstrates database design, SQL joins and aggregates, modular programming, type hints, and test-driven development with pytest.

---

# ✨ Features

- Automatic schema creation with foreign keys and indexes
- Seeded sample data (4 departments, 8 employees)
- Create, read, update, soft-delete and hard-delete employees
- Case-insensitive search across name, email, code and designation
- Department salary report with head count, totals and averages
- Top earners and payroll cost summaries
- Interactive numbered menu or one-shot `--demo` mode
- 8 passing pytest tests

---

# 📂 Folder Structure

```text
Employee_Database/
│
├── src/
│   ├── main.py         # CLI entry point, menu and demo runner
│   ├── database.py     # connection, schema and seed data
│   └── queries.py      # CRUD operations and reporting queries
│
├── tests/
│   └── test_employee_db.py
│
├── data/               # created automatically (employees.db)
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 10_Database_Projects/Employee_Database

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
python src/main.py --db my_employees.db
```

---

# 🗃️ Schema

- **departments** — `id`, `name`, `location`
- **employees** — `id`, `employee_code`, `full_name`, `email`, `department_id`, `designation`, `salary`, `joined_on`, `is_active`

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
- SQL (JOIN, GROUP BY, aggregates, constraints)
- CRUD operations
- Foreign keys and indexes
- Soft deletes
- Modular programming
- Type hints and docstrings
- Exception handling
- Test-driven development

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**8 tests passed** covering schema creation, seeding, CRUD, duplicate detection, search, and reporting queries.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
