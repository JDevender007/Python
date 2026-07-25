# 🎯 Number Guessing Game

A command line Number Guessing Game built with Python. The player selects a difficulty level and tries to guess a randomly generated number within the specified range. The game tracks the best score and stores the history of completed games.

---

## Features

- Three difficulty levels
- Random number generation
- Input validation
- Best score tracking
- Game history with timestamps
- Clean command line interface
- Modular project structure
- Beginner friendly code

---

## Technologies Used

- Python 3.13+
- random
- pathlib
- datetime
- os

---

## Project Structure

```text
NumberGuessingGame/
│
├── src/
│   ├── main.py
│   ├── game.py
│   ├── validator.py
│   ├── score.py
│   ├── statistics.py
│   └── utils.py
│
├── data/
│   ├── best_score.txt
│   └── game_history.txt
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

## Installation

### Clone the repository

```bash
git clone https://github.com/JDevender007/Python.git
```

### Navigate to the project

```bash
cd Python/01_Beginner_Level_Projects/NumberGuessingGame
```

### Create a virtual environment

```bash
python -m venv .venv
```

### Activate the virtual environment

PowerShell

```bash
.venv\Scripts\Activate.ps1
```

Command Prompt

```bash
.venv\Scripts\activate
```

---

## Usage

Run the application.

```bash
python src/main.py
```

---

## Example Output

```text
==================================================
            NUMBER GUESSING GAME
==================================================

Select Difficulty

1. Easy
2. Medium
3. Hard

Choice: 2

Enter your guess (1-100): 50

[INFO] Too High!

Enter your guess (1-100): 25

[INFO] Too Low!

Enter your guess (1-100): 37

[SUCCESS] Correct!

You guessed the number in 3 attempts.

[SUCCESS] New Best Score!
```

---

## Difficulty Levels

|  Level | Range    |
| -----: | -------- |
|   Easy | 1 to 50  |
| Medium | 1 to 100 |
|   Hard | 1 to 500 |

---

## Project Modules

| File            | Description                               |
| --------------- | ----------------------------------------- |
| `main.py`       | Controls the game flow                    |
| `game.py`       | Generates and validates the secret number |
| `validator.py`  | Validates user input                      |
| `score.py`      | Saves and loads the best score            |
| `statistics.py` | Stores game history                       |
| `utils.py`      | Contains reusable console utilities       |

---

## Data Files

### Best Score

The lowest number of attempts is stored in:

```text
data/best_score.txt
```

Example:

```text
3
```

### Game History

Every completed game is recorded in:

```text
data/game_history.txt
```

Example:

```text
[2026-07-25 14:30:12] Easy | Attempts: 4 | Number: 21
[2026-07-25 14:35:48] Medium | Attempts: 6 | Number: 72
```

---

## Requirements

This project uses only Python's standard library.

No additional packages are required.

---

## Learning Outcomes

This project demonstrates:

- Random number generation
- Loops
- Conditional statements
- Functions
- Classes and Objects
- Input validation
- File handling
- Exception handling
- Modular programming
- Command line applications

---

## Future Improvements

- Hint system
- Limited attempts mode
- Multiplayer mode
- Difficulty customization
- Score leaderboard
- Colored terminal output
- Graphical user interface using Tkinter
- Sound effects
- Timed game mode
- Statistics dashboard

---

## Author

**Devender J**

GitHub: https://github.com/JDevender007
