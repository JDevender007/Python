# File Explorer

## Overview

A lightweight Windows-friendly file explorer built with Python's Tkinter library
and pathlib for filesystem operations. Features directory navigation, file management,
search, and safety mechanisms.

## Features

### Navigation
- **Directory tree** on the left pane
- **File list** on the right pane
- **Path bar** for entering custom paths
- **Up** button to go to parent directory
- **Home** button to go to user home
- **Root** button to go to drive root
- **Back** and **Forward** navigation (via history)
- **Refresh** to reload current directory

### File Operations
- **New Folder**: Create a new directory
- **Rename**: Rename selected file or folder
- **Delete**: Move to confirmation before deletion
- **Copy/Cut and Paste**: Standard clipboard operations
- **Open**: Open file with default application
- **Properties**: Display file information

### Safety Mechanisms
- **Confirmation dialog** before deleting files
- **No permanent deletion** without explicit confirmation
- **Permission error** handling with user feedback
- **Invalid path** validation
- **Drive access error** handling

### View Modes
- **Directory tree** browse mode
- **File list** with details (name, size, type)
- **Breadcrumbs** for quick navigation
- **Search** functionality

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Up` / `Backspace` | Go to parent directory |
| `Home` | Go to user home directory |
| `F2` | Rename selected item |
| `Return` / `Double-click` | Open selected item |
| `F5` | Refresh current directory |
| `Ctrl+L` | Focus path bar |
| `Ctrl+N` | Create new folder |

### Drive Support
- Works with different Windows drives (C:, D:, etc.)
- Compatible with different Linux/Mac filesystem roots
- No hardcoded absolute paths (e.g., `C:\Users\...`)

## Technologies

- Python 3.12+
- Tkinter (standard GUI library)
- pathlib (filesystem paths)
- os (where required for system operations)
- No third-party dependencies

## Project Structure

```
05_File_Explorer/
├── README.md
├── requirements.txt
├── .gitignore
├── src/
│   ├── __init__.py
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

# Navigate to the file explorer project
cd Python/09_Desktop_Applications/05_File_Explorer

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

### Basic Navigation

- The **directory tree** on the left shows the folder hierarchy
- The **file list** on the right shows files and folders in the current directory
- The **path bar** at the top shows the current location
- Use **Up** or **Backspace** to go to the parent folder
- Use **Home** to go to your user home directory
- Use **Root** to go to the drive root (C:\), Linux root (/), etc.

### File Operations

- **Select** a file or folder by clicking it
- **Double-click** or press **Enter** to open the selected item
- **Right-click** for context menu (basic operations)
- **New Folder** creates a directory in the current location
- **Rename** changes the name of the selected item
- **Delete** shows a confirmation dialog before removing
- **Copy/Cut and Paste** via clipboard (basic implementation)

### Navigation History

- The explorer maintains a **history** of visited directories
- Use the **Up** button or **Backspace** to go back
- There is no separate "Forward" button in this implementation

### Search

- Use the **Search** button in the toolbar to enter a search term
- Basic implementation - searches folder names

### Safety

- Before deleting any file, a **confirmation dialog** appears
- The application does not permanently delete without explicit confirmation
- Handles **permission denied** errors gracefully
- Validates all paths before operations

## Error Handling

- **Permission denied**: Shows error message if access is denied
- **Missing file/folder**: Informs user if selected item no longer exists
- **Invalid path**: Validates all paths before operations
- **Drive access errors**: Handles inaccessible drives gracefully
- **Empty directories**: Manages gracefully with appropriate display

## Future Improvements

- Drag-and-drop file copying/moving
- Advanced search with file content indexing
- File preview thumbnail generation
- Bookmarked directories
- Split view (dual panes)
- Multi-select file operations
- Cloud storage integration (Google Drive, Dropbox)
- File compression/decompression
- Advanced filtering and sorting

## Screenshots

![File Explorer](docs/screenshots/placeholder.png)

*Placeholder screenshot - add actual screenshots to `docs/screenshots/` directory*