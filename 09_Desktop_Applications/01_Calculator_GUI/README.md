# Calculator GUI

## Overview

A complete desktop calculator application built with Python's Tkinter library.
Performs basic arithmetic operations with a clean, professional interface designed
for the Python placement portfolio.

## Features

- Number buttons 0-9
- Mathematical operators: +, -, ×, ÷
- Decimal numbers
- Percentage calculation
- Clear (C) and Backspace (⌫) functions
- Positive/Negative toggle (±)
- Equals (=) function
- Operator precedence support
- Calculation history
- Error handling for division by zero
- Invalid expression handling
- Keyboard input support
- Keyboard shortcuts

## Technologies

- Python 3.12+
- Tkinter (standard library, no third-party dependencies)
- Python `decimal` module for precision

## Project Structure

```
01_Calculator_GUI/
├── README.md
├── requirements.txt
├── .gitignore
├── src/
│   ├── main.py
│   ├── model.py
│   ├── ui/
│   │   └── view.py
│   ├── services/
│   │   └── controller.py
│   └── utils/
├── assets/
└── docs/
    └── screenshots/
```

## Installation

```bash
# Clone the repository
git clone https://github.com/JDevender007/Python.git

# Navigate to the calculator project
cd Python/09_Desktop_Applications/01_Calculator_GUI

# Create a virtual environment (recommended)
python -m venv .venv

# Activate the virtual environment
# Windows:
.venv\Scripts\activate

# Linux/macOS:
source .venv/bin/activate

# Install dependencies (none required for this project)
pip install -r requirements.txt
```

## Running the Application

```bash
# From the project directory
python src/main.py
```

Or, if the virtual environment is active:

```bash
# Windows
.venv\Scripts\python src/main.py

# Linux/macOS
.venv/bin/python src/main.py
```

## Usage

### Mouse Operations

- Click number buttons (0-9) to enter digits
- Click operator buttons (+, -, ×, ÷) to select an operation
- Click equals (=) to calculate the result
- Click Clear (C) to reset the calculator
- Click Backspace (⌫) to remove the last digit
- Click Percentage (%) to calculate a percentage
- Click Positive/Negative (±) to toggle the sign of the current value

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `0-9` | Enter digits |
| `+` | Add operator |
| `-` | Subtract operator |
| `*` | Multiply operator (press `Shift` + `8`) or use `x` key |
| `/` | Divide operator |
| `.` | Enter decimal point |
| `=` or `Enter` | Calculate result |
| `Backspace` | Remove last digit |
| `Escape` | Clear calculator |
| `%` | Calculate percentage |

## Error Handling

- **Division by zero**: Shows an error message box and resets the calculator
- **Invalid expression**: Shows an error message box and resets the calculator
- **Non-numeric input**: Automatically filtered and ignored
- **Overflow**: Display shows "Error" and resets after user acknowledgement

## Future Improvements

- Memory functions (M+, M-, MR, MC)
- Scientific functions (sin, cos, tan, √, x², 1/x)
- History panel with recall capability
- Keyboard customization
- Theme support (light/dark)
- Expression history log
- Saved preferences

## Screenshots

![Calculator GUI](docs/screenshots/placeholder.png)

*Placeholder screenshot - add actual screenshots to `docs/screenshots/` directory*