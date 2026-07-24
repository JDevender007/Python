# 01. Python Calculator CLI

A modular command-line calculator built with Python.

This project demonstrates clean code organization, modular programming, exception handling, input validation, file handling, and unit testing.

---

## Features

- Addition
- Subtraction
- Multiplication
- Division
- Modulus
- Power
- Input validation
- Division by zero handling
- Calculation history
- Unit tests with pytest
- Modular project structure

---

## Technologies Used

- Python 3
- Pytest
- Git
- GitHub

---

## Project Structure

```
python-calculator-cli/
│
├── calculator/
│   ├── operations.py
│   ├── validator.py
│   ├── history.py
│   └── __init__.py
│
├── tests/
│   └── test_operations.py
│
├── main.py
├── requirements.txt
└── README.md
```

---

## Installation

Clone the repository

```bash
git clone https://github.com/yourusername/python-calculator-cli.git
```

Move into the project directory

```bash
cd python-calculator-cli
```

Create a virtual environment

```bash
python -m venv venv
```

Activate the environment

Windows

```bash
venv\Scripts\activate
```

Linux/macOS

```bash
source venv/bin/activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

---

## Usage

Run the application

```bash
python main.py
```

Example

```
===============================
      PYTHON CLI CALCULATOR
===============================
1. Addition
2. Subtraction
3. Multiplication
4. Division
5. Modulus
6. Power
7. Show History
8. Exit

Enter your choice: 1

Enter first number: 25
Enter second number: 15

Result
-------------------------------
25.0 + 15.0 = 40.0
```

---

## Running Tests

```bash
pytest
```

Expected Output

```
====================
2 passed
====================
```

---

## Future Improvements

- Scientific calculator
- Square root
- Factorial
- Percentage calculations
- Memory functions
- Export history to CSV
- Colored terminal interface
- Command-line arguments
- Logging
- GitHub Actions CI

---

## Learning Outcomes

This project helped strengthen understanding of:

- Python functions
- Modular programming
- Exception handling
- File operations
- Input validation
- Unit testing
- Git version control
- GitHub project management

---

## Author

**Devender J**

Computer Science and Engineering Student

GitHub: https://github.com/JDevender007/Devender

LinkedIn: linkedin.com/in/devender-j

---

## License

This project is licensed under the MIT License.
