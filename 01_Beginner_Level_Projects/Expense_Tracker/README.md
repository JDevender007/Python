<div align="center">

# 💰 Expense Tracker

A command line Expense Tracker built with Python, SQLite, and SQLAlchemy. This project helps users manage daily expenses, track spending, and generate simple financial reports while demonstrating database operations using an ORM.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-ORM-D71F00?style=for-the-badge)

</div>

---

# 📖 About

Expense Tracker is a beginner friendly database project developed using Python, SQLite, and SQLAlchemy.

The application allows users to record expenses, manage financial records, and generate spending reports through a simple command line interface. It demonstrates modular programming, CRUD operations, input validation, and ORM based database management.

---

# ✨ Features

- Add Expense
- View All Expenses
- Update Expense
- Delete Expense
- Search Expenses
- Category-wise Report
- Monthly Report
- Total Expense Calculation
- SQLite Database Storage
- SQLAlchemy ORM
- Input Validation
- Modular Project Structure

---

# 🛠 Technologies Used

- Python 3
- SQLite
- SQLAlchemy
- Standard Python Libraries

---

# 📚 Concepts Covered

- Python Functions
- Object Oriented Programming
- Modular Programming
- SQLite Database
- SQLAlchemy ORM
- CRUD Operations
- Exception Handling
- Input Validation
- Database Relationships
- Report Generation

---

# 📁 Project Structure

```text
ExpenseTracker/
│
├── src/
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── expense_service.py
│   ├── report_service.py
│   ├── validator.py
│   └── utils.py
│
├── database/
│   └── expenses.db
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🗄 Database Schema

## expenses

| Column       | Type    |
| ------------ | ------- |
| id           | Integer |
| title        | String  |
| category     | String  |
| amount       | Float   |
| expense_date | Date    |
| description  | String  |

---

# 🚀 Getting Started

## Clone Repository

```bash
git clone https://github.com/JDevender007/Python.git
```

---

## Navigate to Project

```bash
cd ExpenseTracker
```

---

## Create Virtual Environment

```bash
python -m venv .venv
```

---

## Activate Virtual Environment

### Windows

```bash
.venv\Scripts\activate
```

---

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Run the Application

```bash
python src/main.py
```

---

# 📋 Menu

```text
========================================
          EXPENSE TRACKER
========================================

1. Add Expense
2. View Expenses
3. Search Expense
4. Update Expense
5. Delete Expense
6. Total Expense
7. Category Report
8. Monthly Report
9. Exit
```

---

# 📌 Example

```text
Title       : Lunch
Category    : Food
Amount      : 250
Description : Office Lunch

Expense added successfully.
```

---

# 📈 Learning Outcomes

After completing this project, you will understand:

- SQLite Database Integration
- SQLAlchemy ORM
- Database CRUD Operations
- Python Project Structure
- Input Validation
- Service Layer Architecture
- Report Generation
- Modular Programming

---

# 📦 Requirements

```text
SQLAlchemy
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

# 🎯 Future Improvements

- Expense Categories Management
- Budget Tracking
- Export to CSV
- Export to Excel
- Expense Charts
- User Authentication
- Multiple User Support
- Dashboard Interface
- GUI Version
- REST API Integration

---

# 👨‍💻 Author

**Devender J**

Python Developer | Data Analytics Enthusiast | AI Learner | Networking Enthusiast

GitHub: https://github.com/JDevender007

---

<div align="center">

⭐ If you found this project useful, consider giving it a star.

</div>
