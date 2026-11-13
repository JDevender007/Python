<div align="center">

# 🗄️ Database Projects

### A collection of Python projects focused on relational database design, CRUD operations, SQL reporting, and data-driven command line applications.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Projects](https://img.shields.io/badge/Projects-5-success?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

This repository contains Python projects that demonstrate practical database development using SQLite. The projects cover employee, hospital, inventory, attendance, and customer relationship data — each with a normalised schema, seeded sample data, full CRUD operations, business reports, and a command line interface.

Every project follows a modular architecture with clean code, logging, error handling, and automated tests.

---

# 🎯 Learning Objectives

- Design normalised relational schemas
- Write SQL with joins, grouping, and aggregates
- Enforce integrity with keys, constraints, and indexes
- Build CRUD applications with a clean data layer
- Generate business reports from raw data
- Handle upserts, cascades, and state transitions
- Practice modular programming and type hints
- Develop reusable, tested database utilities

---

# 📂 Projects

| No. | Project               | Description                                                                                      | Status |
| --: | --------------------- | ------------------------------------------------------------------------------------------------ | :----: |
|  01 | Employee Database     | Employee records with departments, salaries, search, and payroll reporting.                       |   ✅   |
|  02 | Hospital Database     | Patients, doctors, appointments, billing, and revenue reporting for a small clinic.               |   ✅   |
|  03 | Inventory Database    | Products, suppliers, and an append-only stock movement ledger with valuation reports.             |   ✅   |
|  04 | Attendance Management | Daily attendance marking, monthly percentages, defaulters, and CSV import/export.                 |   ✅   |
|  05 | CRM System            | Leads, conversions, interactions, deal pipeline, and KPI reporting.                               |   ✅   |

---

# 💡 Concepts Covered

- Relational Database Design
- SQL (JOIN, GROUP BY, Subqueries, Aggregates)
- CRUD Operations
- Foreign Keys and Referential Actions
- CHECK Constraints and Indexes
- Upserts and Conflict Handling
- Append-only Ledger Modelling
- State Machines in Data
- CSV Import / Export
- Object Oriented Programming
- Modular Programming
- Exception Handling
- Logging
- Test-driven Development

---

# 📁 Repository Structure

```text
10_Database_Projects/
│
├── Employee_Database/
├── Hospital_Database/
├── Inventory_Database/
├── Attendance_Management/
├── CRM_System/
│
└── README.md
```

Each project contains:

```text
Project_Name/
├── src/              # main.py, database.py, queries.py
├── tests/            # pytest test suite
├── data/             # created automatically at runtime
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠 Technologies

- Python 3
- sqlite3
- csv
- argparse
- logging
- pytest

---

# 📈 Progress

| Project               | Status |
| --------------------- | :----: |
| Employee Database     |   ✅   |
| Hospital Database     |   ✅   |
| Inventory Database    |   ✅   |
| Attendance Management |   ✅   |
| CRM System            |   ✅   |

**Completed:** **5 / 5 Projects**

---

# ▶️ Quick Start

```bash
cd 10_Database_Projects/Employee_Database

python src/main.py --demo     # scripted walkthrough
python src/main.py            # interactive menu
python -m pytest tests/ -q    # run the tests
```

---

# 📚 Skills Developed

- Database Schema Design
- SQL Query Writing
- Data Modelling
- Reporting and Analytics
- CSV Data Processing
- Business Logic Implementation
- Code Organization
- Object Oriented Programming
- Error Handling
- Command Line Application Development
- Automated Testing

---

# 🚀 Key Learning Outcomes

- Build SQLite-backed applications from scratch
- Derive state from historical data (ledgers)
- Report on business metrics with SQL
- Keep demos idempotent and re-runnable
- Design scalable Python applications
- Apply clean coding practices

---

# 🔮 Future Enhancements

- SQLAlchemy ORM versions
- Web interfaces with Flask or FastAPI
- Role-based access control
- Database migrations with Alembic
- Excel and PDF report export
- Multi-user support with connection pooling
- Backup and restore utilities
- Dashboard visualisations

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
