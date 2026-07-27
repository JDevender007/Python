<div align="center">

# 📂 Duplicate File Finder

### A Python application that scans directories, detects duplicate files using SHA-256 hashing, and generates a detailed CSV report.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Duplicate File Finder is a Python command line application that recursively scans a directory, calculates the SHA-256 hash of every file, identifies duplicate files, and exports the results to a CSV report.

The project demonstrates practical file handling, hashing algorithms, logging, modular programming, and report generation while maintaining a clean and scalable project structure.

---

# ✨ Features

- Recursively scan folders
- Detect duplicate files using SHA-256 hashing
- Skip empty files
- Display duplicate file groups
- Generate CSV reports
- Activity logging
- Progress bar while scanning
- Modular architecture
- Simple command line interface

---

# 📂 Project Structure

```text
Duplicate_File_Finder/
│
├── .venv/
├── duplicate_files/
├── reports/
├── logs/
├── tests/
│
├── src/
│   ├── config.py
│   ├── duplicate_finder.py
│   ├── hash_utils.py
│   ├── logger.py
│   ├── main.py
│   └── report.py
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 04_File_Handling/Duplicate_File_Finder

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
cd src

python main.py
```

---

# 📋 How It Works

1. Place files inside the **duplicate_files** folder.
2. Run the application.
3. The program scans every file recursively.
4. A SHA-256 hash is generated for each file.
5. Files with matching hashes are identified as duplicates.
6. Duplicate groups are displayed in the terminal.
7. A CSV report is generated in the **reports** folder.
8. Activity logs are stored in the **logs** folder.

---

# 📄 Sample Report

| Original File | Duplicate File    |
| ------------- | ----------------- |
| image1.jpg    | image1_copy.jpg   |
| report.pdf    | report_backup.pdf |
| notes.txt     | notes_copy.txt    |

---

# 🛠 Technologies Used

- Python 3
- pathlib
- hashlib
- csv
- logging
- Colorama
- tqdm

---

# 📚 Concepts Covered

- File Handling
- Recursive Directory Traversal
- SHA-256 Hashing
- Dictionary Data Structures
- CSV Report Generation
- Logging
- Exception Handling
- Object Oriented Programming
- Modular Programming

---

# 🎯 Learning Outcomes

- Work with binary files
- Calculate file hashes
- Detect duplicate files efficiently
- Generate structured reports
- Build modular Python applications
- Implement logging and error handling

---

# 🚀 Future Improvements

- Delete duplicate files
- Move duplicates to a separate folder
- Compare files by size before hashing
- Export reports in Excel format
- GUI version using Tkinter or PySide6
- Drag and drop folder selection
- Multi-threaded scanning for faster performance

---

# 👨‍💻 Author

**Devender J**

GitHub: https://github.com/JDevender007

---

<div align="center">

⭐ If you found this project useful, consider giving it a star.

</div>
