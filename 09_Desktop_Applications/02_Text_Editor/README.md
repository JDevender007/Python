# Text Editor

## Overview

A lightweight desktop text editor built with Python's Tkinter library, featuring
full file operations, editing tools, and keyboard shortcuts. Designed as part of
the Python Placement Portfolio - Section 09 Desktop Applications.

## Features

### File Operations
- New file (Ctrl+N)
- Open file (Ctrl+O)
- Save (Ctrl+S)
- Save As (Ctrl+Shift+S)
- Close
- Exit

### Editing Tools
- Undo (Ctrl+Z) and Redo (Ctrl+Y)
- Cut (Ctrl+X), Copy (Ctrl+V), Paste (Ctrl+V)
- Select All (Ctrl+A)
- Find (Ctrl+F) and Replace (Ctrl+H)
- Go to Line

### Document Management
- Word wrap toggle
- Font size controls
- Recent files list
- Modified-file detection with warnings

### Status Display
- Line and column position
- Word count and character count
- File name display

### Interface
- Menu bar (File, Edit, Search, View, Help)
- Toolbar with common buttons
- Scrollable text area
- Real-time status bar

## Technologies

- Python 3.12+
- Tkinter (standard library, no third-party dependencies)
- Native tkinter Text widget with undo support

## Project Structure

```
02_Text_Editor/
├── README.md
├── requirements.txt
├── .gitignore
├── src/
│   ├── main.py
│   ├── model.py
│   ├── controller.py
│   └── ui/
│       └── view.py
├── assets/
└── docs/
    └── screenshots/
```

## Installation

```bash
# Clone the repository
git clone https://github.com/JDevender007/Python.git

# Navigate to the text editor project
cd Python/09_Desktop_Applications/02_Text_Editor

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

### File Operations

- **New (Ctrl+N)**: Creates a new empty document, prompting to save current if modified
- **Open (Ctrl+O)**: Opens a file dialog to select and load a text file
- **Save (Ctrl+S)**: Saves the current document to its existing file path
- **Save As (Ctrl+Shift+S)**: Saves the current document to a new location/name
- **Close (Ctrl+W)**: Closes the current document (prompts to save if modified)
- **Exit (Alt+F4)**: Closes the application after confirming unsaved changes

### Editing

- **Undo (Ctrl+Z)**: Reverses the last text change
- **Redo (Ctrl+Y)**: Re-applies the last undone change
- **Cut (Ctrl+X)**: Removes selected text and places it on the clipboard
- **Copy (Ctrl+C)**: Copies selected text to the clipboard
- **Paste (Ctrl+V)**: Inserts clipboard content at cursor position
- **Select All (Ctrl+A)**: Selects all text in the document
- **Find (Ctrl+F)**: Opens find dialog (functionality coming soon)
- **Replace (Ctrl+H)**: Opens replace dialog (functionality coming soon)

### View

- **Word Wrap**: Toggles word wrapping on/off
- **Font Size**: Adjustable via the view menu
- **Status Bar**: Shows line number, column position, word count, and character count

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+N` | New file |
| `Ctrl+O` | Open file |
| `Ctrl+S` | Save file |
| `Ctrl+Shift+S` | Save As |
| `Ctrl+Z` | Undo |
| `Ctrl+Y` | Redo |
| `Ctrl+X` | Cut |
| `Ctrl+C` | Copy |
| `Ctrl+V` | Paste |
| `Ctrl+A` | Select All |
| `Ctrl+F` | Find |
| `Ctrl+H` | Replace |
| `F3` | Find Next |
| `Shift+F3` | Find Previous |
| `Ctrl+F3` | Not used |
| `Alt+F4` | Exit |
| `Ctrl+W` | Close |

### Status Bar

- **Line**: Shows current line number where cursor is positioned
- **Col**: Shows current column number where cursor is positioned
- **Words**: Shows total word count in the document
- **Chars**: Shows total character count in the document

## Error Handling

- **File not found**: Shows error message if selected file doesn't exist
- **Permission denied**: Informs user if file cannot be accessed
- **Unsupported encoding**: Attempts to read with fallback encodings
- **Unsaved changes**: Prompts user before closing or opening new file
- **Invalid paths**: Validates all file paths before operations

## Future Improvements

- Rich text formatting (bold, italic, underline)
- Font selection dialog
- Multiple document interface (MDI)
- Split view editing
- Plugin system for extensions
- Syntax highlighting for various languages
- Regular expression search and replace
- Autosave functionality
- Cloud storage integration

## Screenshots

![Text Editor](docs/screenshots/placeholder.png)

*Placeholder screenshot - add actual screenshots to `docs/screenshots/` directory*