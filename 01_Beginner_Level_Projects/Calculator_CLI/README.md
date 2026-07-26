# 🧮 Calculator CLI

A command line calculator built with Python that performs basic arithmetic operations with input validation and calculation history. This project demonstrates modular programming by separating operations, validation, and history management into different modules.

## Features

- Addition
- Subtraction
- Multiplication
- Division
- Modulus
- Power
- Input validation
- Calculation history
- Simple command line interface
- Modular project structure

## Technologies Used

- Python 3
- File Handling
- Functions
- Dictionaries
- Exception Handling
- Modular Programming

## Project Structure

```text
CalculatorCLI/
│
├── calculator/
│   ├── __init__.py
│   ├── operations.py
│   ├── validator.py
│   └── history.py
│
├── history.txt
├── main.py
├── README.md
├── requirements.txt
└── .gitignore
```

## Installation

Clone the repository.

```bash
git clone https://github.com/JDevender007/Python.git
```

Navigate to the project.

```bash
cd Python/01_Beginner_Level_Projects/CalculatorCLI
```

Run the application.

```bash
python main.py
```

## Menu

```text
===================================
PYTHON CLI CALCULATOR
===================================
1. Addition
2. Subtraction
3. Multiplication
4. Division
5. Modulus
6. Power
7. Show History
8. Exit
===================================
```

## Example

```text
Enter your choice: 1

Enter first number: 25
Enter second number: 15

Result
-----------------------------------
25.0 + 15.0 = 40.0
```

## Project Modules

### `main.py`

Controls the application flow and user interaction.

### `operations.py`

Contains arithmetic functions including addition, subtraction, multiplication, division, modulus, and power.

### `validator.py`

Validates numeric user input before calculations.

### `history.py`

Stores calculations in a history file and displays previous calculations.

## Learning Outcomes

This project helped me practice:

- Python functions
- Conditional statements
- Dictionaries
- File handling
- Exception handling
- Input validation
- Modular programming
- Command line applications

## Future Improvements

- Square root
- Factorial
- Percentage calculations
- Scientific calculator mode
- Memory operations
- Colored terminal output
- Calculation export to CSV
- Graphical user interface using Tkinter

## Author

**Devender J**

GitHub: https://github.com/JDevender007
