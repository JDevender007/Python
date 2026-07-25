# 🔐 Password Generator

A secure password generator built with Python. This application generates strong random passwords using Python's `secrets` module, evaluates password strength, copies passwords to the clipboard, and stores generated passwords in a history file.

## Features

- Generate secure random passwords
- Custom password length
- Uses Python's `secrets` module
- Password strength analysis
- Automatic clipboard copy
- Password history with timestamps
- Input validation
- Modular project structure
- Beginner friendly code

## Technologies Used

- Python 3.13+
- secrets
- string
- datetime
- pathlib
- os
- pyperclip

## Project Structure

```text
PasswordGenerator/
│
├── src/
│   ├── main.py
│   ├── generator.py
│   ├── validator.py
│   ├── strength.py
│   ├── clipboard.py
│   ├── history.py
│   └── utils.py
│
├── data/
│   └── password_history.txt
│
├── README.md
├── requirements.txt
└── .gitignore
```

## Installation

### Clone the repository

```bash
git clone https://github.com/JDevender007/PasswordGenerator.git
```

### Navigate to the project

```bash
cd PasswordGenerator
```

### Create a virtual environment

```bash
python -m venv .venv
```

### Activate the virtual environment

**PowerShell**

```bash
.venv\Scripts\Activate.ps1
```

**Command Prompt**

```bash
.venv\Scripts\activate
```

### Install dependencies

```bash
pip install -r requirements.txt
```

## Usage

Run the application:

```bash
python src/main.py
```

Example:

```text
==================================================
                PASSWORD GENERATOR
==================================================

Password Length (4-64): 16

==================================================
Generated Password : @A7m!kL2#Px9Q$rW
Password Length    : 16
Strength Score     : 6/6
Strength Rating    : Very Strong
==================================================

[SUCCESS] Password copied to clipboard.
```

## Password Strength Levels

|  Score | Rating      |
| -----: | ----------- |
| 0 to 2 | Weak        |
| 3 to 4 | Medium      |
|      5 | Strong      |
|      6 | Very Strong |

## Project Modules

| File           | Description                        |
| -------------- | ---------------------------------- |
| `main.py`      | Entry point of the application     |
| `generator.py` | Generates secure random passwords  |
| `validator.py` | Validates user input               |
| `strength.py`  | Evaluates password strength        |
| `clipboard.py` | Copies passwords to the clipboard  |
| `history.py`   | Saves generated passwords          |
| `utils.py`     | Contains reusable helper functions |

## Password History

Generated passwords are automatically stored in:

```text
data/password_history.txt
```

Example:

```text
[2026-07-25 10:15:34] Ab#7Lm2!Pq
[2026-07-25 10:17:11] X9@rT8#vQm
```

## Requirements

- Python 3.13 or later
- pyperclip

Install dependencies:

```bash
pip install -r requirements.txt
```

## Learning Outcomes

This project demonstrates:

- Python modules
- Object oriented programming
- Secure password generation
- File handling
- Input validation
- Exception handling
- Clipboard integration
- Modular project design
- Git and GitHub workflow

## Future Improvements

- Password entropy calculation
- Password export to CSV
- Password manager integration
- Graphical user interface with Tkinter
- FastAPI version
- Password breach detection
- Password expiration reminders

## Author

**Devender J**

Computer Science and Engineering Student

GitHub: https://github.com/JDevender007
