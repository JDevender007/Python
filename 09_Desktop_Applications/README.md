# 09 - Desktop Applications

## Overview

Section 09 of the Python Placement Portfolio contains five complete desktop applications built with Python's Tkinter library. These applications demonstrate GUI development, file operations, system utilities, and multimedia handling - all production-ready and suitable for a professional Python portfolio.

## Projects

| # | Project | Main Technology |
|---|---------|-----------------|
| 01 | Calculator GUI | Tkinter |
| 02 | Text Editor | Tkinter |
| 03 | Image Viewer | Tkinter + Pillow |
| 04 | Music Player | Tkinter + pygame |
| 05 | File Explorer | Tkinter + pathlib |

## Section Learning Objectives

- Build complete desktop applications with graphical user interfaces
- Implement proper separation between UI and application logic
- Handle user input, file operations, and errors gracefully
- Use Python standard library (Tkinter) and minimal third-party dependencies
- Create clean, maintainable code with type hints and modular architecture
- Design professional-looking UI with ttk widgets and consistent styling
- Support keyboard shortcuts and responsive resizing

## Installation Overview

Each project is self-contained in its own subdirectory:

```bash
# Navigate to a specific project
cd Python/09_Desktop_Applications/01_Calculator_GUI

# Create a virtual environment (recommended)
python -m venv .venv

# Activate the virtual environment
# Windows:
.venv\Scripts\activate

# Linux/macOS:
source .venv/bin/activate

# Install dependencies (project-specific)
pip install -r requirements.txt
```

Recommended Python version: 3.12+

## Project Progression

The five projects in this section progress from simple utilities to more complex applications:

1. **Calculator GUI** - Basic arithmetic with keyboard support
2. **Text Editor** - Full-featured text editing with file operations
3. **Image Viewer** - Image viewing with zoom, rotate, flip
4. **Music Player** - Audio playback with playlist support
5. **File Explorer** - Filesystem navigation and file management

## Skills Demonstrated

- GUI development with Tkinter and ttk widgets
- Separation of concerns (model, view, controller pattern)
- File I/O operations with proper error handling
- Keyboard shortcuts and event binding
- Responsive UI design with proper layout management
- Type hints and modular code organization
- Cross-platform path handling with pathlib
- No unnecessary dependencies - only what each project requires