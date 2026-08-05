<div align="center">

# 📝 Bulk File Renamer

### A professional Python desktop application for batch renaming files with customizable naming rules, live preview, and an intuitive graphical interface.

![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Tkinter](https://img.shields.io/badge/Tkinter-GUI-success?style=for-the-badge)
![Automation](https://img.shields.io/badge/File-Automation-blue?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

Bulk File Renamer is a desktop application built with Python and Tkinter that simplifies batch file renaming. It enables users to rename multiple files simultaneously using custom prefixes, suffixes, sequential numbering, text replacement, and case conversion while previewing the results before applying changes.

The application follows a modular architecture with object-oriented programming principles, making it suitable for learning desktop application development, file system automation, and Python project organization.

---

# ✨ Features

## File Management

- Select Folder
- Load All Files
- Refresh File List
- Preview Original File Names
- Preview New File Names
- Rename Selected Files
- Rename All Files
- Undo Last Rename

## Rename Options

- Sequential Numbering
- Add Prefix
- Add Suffix
- Replace Text
- Remove Text
- Convert to Uppercase
- Convert to Lowercase
- Convert to Title Case
- Preserve File Extensions

## User Interface

- Modern Desktop Interface
- Responsive Layout
- Dark Theme
- Progress Updates
- Status Information
- Fullscreen Support
- Keyboard Shortcuts

---

# 🛠 Technologies Used

- Python 3.13
- Tkinter
- pathlib
- shutil
- logging

---

# 📂 Project Structure

```text
Bulk_File_Renamer/
│
├── src/
│   ├── __init__.py
│   ├── app.py
│   ├── colors.py
│   ├── config.py
│   ├── controls.py
│   ├── file_handler.py
│   ├── logger.py
│   ├── preview.py
│   ├── renamer.py
│   └── utils.py
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🚀 Installation

Clone the repository.

```bash
git clone https://github.com/JDevender007/Bulk_File_Renamer.git
```

Navigate to the project directory.

```bash
cd Bulk_File_Renamer
```

Create a virtual environment.

```bash
python -m venv .venv
```

Activate the virtual environment.

### Windows

```bash
.venv\Scripts\activate
```

### Linux / macOS

```bash
source .venv/bin/activate
```

Install dependencies.

```bash
pip install -r requirements.txt
```

---

# ▶️ Run

```bash
python -m src.app
```

---

# ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl + O | Select Folder |
| Ctrl + R | Rename Files |
| Ctrl + Z | Undo Rename |
| Ctrl + L | Refresh File List |
| Delete | Clear File List |
| F11 | Toggle Fullscreen |
| Escape | Exit Fullscreen |

---

# 📦 Dependencies

- tkinter

---

# 🎯 Learning Outcomes

- File System Automation
- Batch File Processing
- Desktop GUI Development
- Object-Oriented Programming
- Modular Software Architecture
- Exception Handling
- Logging
- Python Project Organization

---

# 📈 Future Improvements

- Drag and Drop Support
- Regular Expression Renaming
- Rename Templates
- Metadata-Based Renaming
- Image EXIF Renaming
- Duplicate File Detection
- Multi-threading
- Theme Switching
- Rename History
- Configuration Persistence

---

# 👨‍💻 Author

**Devender J**

Data Analyst | Python Developer | AI & Machine Learning Enthusiast

GitHub: https://github.com/JDevender007

---

<div align="center">

⭐ If you found this project useful, consider giving it a star.

</div>