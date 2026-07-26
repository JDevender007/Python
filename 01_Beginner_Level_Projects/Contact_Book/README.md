<div align="center">

# 📒 Contact Book

A command line Contact Book application built with Python, SQLite, and SQLAlchemy. This project allows users to manage contacts efficiently using CRUD operations while demonstrating database management with SQLAlchemy ORM.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-ORM-D71F00?style=for-the-badge)

</div>

---

# 📖 About

Contact Book is a beginner level Python project developed using SQLite and SQLAlchemy.

The application allows users to store and manage personal contacts through a simple command line interface. It demonstrates CRUD operations, database management, modular programming, input validation, and object oriented design using SQLAlchemy ORM.

---

# ✨ Features

- Add Contact
- View All Contacts
- Search Contact
- Update Contact
- Delete Contact
- Count Total Contacts
- SQLite Database Storage
- SQLAlchemy ORM
- Input Validation
- Modular Project Structure

---

# 🛠 Technologies Used

- Python 3
- SQLite
- SQLAlchemy

---

# 📚 Concepts Covered

- Python Functions
- Object Oriented Programming
- Modular Programming
- SQLite Database
- SQLAlchemy ORM
- CRUD Operations
- Input Validation
- Exception Handling
- Database Queries

---

# 📁 Project Structure

```text
Contact_Book/
│
├── src/
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── contact_service.py
│   ├── validator.py
│   └── utils.py
│
├── database/
│   └── contacts.db
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🗄 Database Schema

## contacts

| Column     | Type     |
| ---------- | -------- |
| id         | Integer  |
| first_name | String   |
| last_name  | String   |
| phone      | String   |
| email      | String   |
| address    | String   |
| created_at | DateTime |

---

# 🚀 Getting Started

## Clone Repository

```bash
git clone https://github.com/JDevender007/Python.git
```

---

## Navigate to Project

```bash
cd Contact_Book
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
==================================================
                CONTACT BOOK
==================================================

1. Add Contact
2. View Contacts
3. Search Contact
4. Update Contact
5. Delete Contact
6. Total Contacts
7. Exit
```

---

# 📌 Example

```text
First Name : John
Last Name  : Doe
Phone      : 9876543210
Email      : john@example.com
Address    : Chennai

Contact added successfully.
```

---

# 📈 Learning Outcomes

After completing this project, you will understand:

- SQLite Database Integration
- SQLAlchemy ORM
- CRUD Operations
- Database Queries
- Input Validation
- Modular Programming
- Service Layer Architecture
- Python Project Structure

---

# 📦 Requirements

```
SQLAlchemy
```

Install dependencies using:

```bash
pip install -r requirements.txt
```

---

# 🎯 Future Improvements

- Contact Groups
- Favorite Contacts
- Import Contacts from CSV
- Export Contacts to CSV
- Contact Photo Support
- Birthday Reminder
- Search Filters
- GUI Version
- REST API Integration
- Multi User Support

---

# 👨‍💻 Author

**Devender J**

Python Developer | Data Analytics Enthusiast | AI Learner | Networking Enthusiast

GitHub: https://github.com/JDevender007

---

<div align="center">

⭐ If you found this project useful, consider giving it a star.

</div>
