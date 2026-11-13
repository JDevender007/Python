<div align="center">

# 📦 Inventory Database

### A SQLite inventory management system with suppliers, products, stock movements, low-stock alerts, and valuation reports.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-3-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Inventory Database is a command line application for tracking products, suppliers, and stock movements. Every stock change is recorded as an append-only movement (in, out, or adjustment), so current quantities and valuation are always derived from history rather than a mutable counter.

It demonstrates relational design, ledger-style data modelling, stock validation, and reporting with SQL aggregates.

---

# ✨ Features

- Suppliers and products with foreign key integrity
- Append-only stock movement ledger (in / out / adjustment)
- Insufficient-stock guard on outbound movements
- Automatic on-hand calculation from movement history
- Low-stock alerts against per-product reorder levels
- Stock valuation report and category summary
- Case-insensitive search across SKU, name, category, supplier
- Interactive menu or one-shot `--demo` mode (re-runnable)
- 11 passing pytest tests

---

# 📂 Folder Structure

```text
Inventory_Database/
│
├── src/
│   ├── main.py         # CLI entry point, menu and demo runner
│   ├── database.py     # connection, schema and seed data
│   └── queries.py      # CRUD operations and reporting queries
│
├── tests/
│   └── test_inventory_db.py
│
├── data/               # created automatically (inventory.db)
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 10_Database_Projects/Inventory_Database

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
python src/main.py --db my_inventory.db
```

---

# 🗃️ Schema

- **suppliers** — `id`, `name`, `contact`, `email`, `city`
- **products** — `id`, `sku`, `name`, `category`, `unit_price`, `reorder_level`, `supplier_id`
- **stock_movements** — `id`, `product_id`, `movement`, `quantity`, `note`, `created_on`

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
- Ledger / append-only data modelling
- Derived state (on-hand computed from movements)
- CHECK constraints and indexes
- Business rule validation in the data layer
- SQL grouping and conditional aggregates
- Inventory valuation
- Modular programming and type hints
- Test-driven development

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**11 tests passed** covering stock in/out, insufficient-stock guard, low-stock alerts, valuation, search, history, and category summaries.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
