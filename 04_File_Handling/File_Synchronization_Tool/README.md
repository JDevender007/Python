<div align="center">

# 🔄 File Synchronization Tool

### A Python application that synchronizes files between two folders while preserving the directory structure and generating synchronization reports.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

File Synchronization Tool is a Python command line application that keeps two folders synchronized. The application scans the source directory, compares files using SHA-256 hashing, copies new or modified files to the destination directory, and generates a synchronization report.

The project demonstrates practical file handling, hashing, recursive directory traversal, logging, and modular application design.

---

# ✨ Features

- Synchronize folders recursively
- Copy newly added files
- Update modified files
- Preserve folder structure
- Compare files using SHA-256
- Generate CSV synchronization reports
- Progress bar
- Activity logging
- Modular architecture
- Command line interface

---

# 📂 Project Structure

```text
File_Synchronization_Tool/
│
├── .venv/
├── source_folder/
├── destination_folder/
├── reports/
├── logs/
├── tests/
│
├── src/
│   ├── config.py
│   ├── file_utils.py
│   ├── logger.py
│   ├── synchronizer.py
│   ├── report.py
│   └── main.py
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 04_File_Handling/File_Synchronization_Tool

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

1. Place files inside the **source_folder**.
2. Run the application.
3. Files are scanned recursively.
4. Each file is compared with the destination using SHA-256 hashing.
5. New or modified files are copied.
6. Folder structure is preserved.
7. A synchronization report is generated.
8. Activity logs are saved automatically.

---

# 📄 Sample Report

| Source File | Destination File           |
| ----------- | -------------------------- |
| report.pdf  | destination/report.pdf     |
| photo.jpg   | destination/photo.jpg      |
| notes.txt   | destination/docs/notes.txt |

---

# 🛠 Technologies Used

- Python 3
- pathlib
- shutil
- hashlib
- csv
- logging
- tqdm
- Colorama

---

# 📚 Concepts Covered

- File Handling
- Directory Traversal
- Recursive Operations
- SHA-256 Hashing
- File Synchronization
- CSV Report Generation
- Logging
- Exception Handling
- Object Oriented Programming
- Modular Programming

---

# 🎯 Learning Outcomes

- Compare files using hashes
- Synchronize directories efficiently
- Preserve directory structures
- Generate reports
- Build scalable command line tools
- Improve Python file handling skills

---

# 🚀 Future Improvements

- Two-way synchronization
- Delete removed files automatically
- Schedule synchronization
- GUI version
- File filtering by extension
- Synchronization history
- Multi-threaded synchronization
- Real-time folder monitoring

---

# 👨‍💻 Author

**Devender J**

GitHub: https://github.com/JDevender007

---

<div align="center">

⭐ If you found this project useful, consider giving it a star.

</div>
