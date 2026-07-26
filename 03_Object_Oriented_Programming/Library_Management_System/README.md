<div align="center">

# 📚 Library Management System

A command line Library Management System built with Python, SQLite, and SQLAlchemy. This project demonstrates Object Oriented Programming principles while managing books through a database-driven application.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-ORM-D71F00?style=for-the-badge)

</div>

---

# 📖 About

Library Management System is an Object Oriented Programming project developed using Python, SQLite, and SQLAlchemy.

The application allows users to manage library books by adding, searching, updating, deleting, issuing, and returning books through a command line interface. It demonstrates OOP concepts, database management, CRUD operations, and modular software architecture.

---

# ✨ Features

- Add Book
- View Books
- Search Book
- Update Book
- Delete Book
- Issue Book
- Return Book
- View Issued Books
- Count Total Books
- SQLite Database Storage
- SQLAlchemy ORM
- Modular Project Structure

---

# 🛠 Technologies Used

- Python 3
- SQLite
- SQLAlchemy

---

# 📚 Concepts Covered

- Object Oriented Programming
- Classes and Objects
- Encapsulation
- Modular Programming
- SQLite Database
- SQLAlchemy ORM
- CRUD Operations
- Input Validation
- Exception Handling

---

# 📁 Project Structure

```text
Library_Management_System/
│
├── src/
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── library_service.py
│   ├── validator.py
│   └── utils.py
│
├── database/
│   └── library.db
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🗄 Database Schema

## books

| Column    | Type    |
| --------- | ------- |
| id        | Integer |
| title     | String  |
| author    | String  |
| isbn      | String  |
| quantity  | Integer |
| available | Integer |
| issued    | Boolean |

---

# 🚀 Getting Started

## Clone Repository

```bash
git clone https://github.com/JDevender007/Python.git
```

## Navigate to Project

```bash
cd 03_Object_Oriented_Programming/01_Library_Management_System
```

## Create Virtual Environment

```bash
python -m venv .venv
```

## Activate Virtual Environment

### Windows

```bash
.venv\Scripts\activate
```

## Install Dependencies

```bash
pip install -r requirements.txt
```

## Run the Application

```bash
python src/main.py
```

---

# 📋 Menu

```text
==================================================
        LIBRARY MANAGEMENT SYSTEM
==================================================

1. Add Book
2. View Books
3. Search Book
4. Update Book
5. Delete Book
6. Issue Book
7. Return Book
8. View Issued Books
9. Total Books
10. Exit
```

---

# 📌 Example

```text
Title     : Python Programming
Author    : John Smith
ISBN      : 9780135166307
Quantity  : 10

Book added successfully.
```

---

# 📈 Learning Outcomes

After completing this project, you will understand:

- Object Oriented Programming
- SQLAlchemy ORM
- SQLite Database
- CRUD Operations
- Database Queries
- Modular Programming
- Service Layer Architecture
- Python Project Structure

---

# 📦 Requirements

```
SQLAlchemy
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

# 🎯 Future Improvements

- Student Management
- Book Categories
- Fine Calculation
- Borrowing History
- Multi User Login
- Dashboard
- Export Reports
- Barcode Support
- Email Notifications
- GUI Version

---

# 👨‍💻 Author

**Devender J**

Python Developer | Data Analytics Enthusiast | AI Learner | Networking Enthusiast

GitHub: https://github.com/JDevender007

---

<div align="center">

⭐ If you found this project useful, consider giving it a star.

</div>
