<div align="center">

# 📊 Log File Analyzer

### A Python command line application that analyzes log files, summarizes log levels, searches log entries, and exports the results to a CSV report.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Log File Analyzer is a Python application designed to read and analyze log files efficiently. It scans one or more log files, classifies log entries by severity level, performs keyword-based searches, and generates a CSV summary report.

This project demonstrates practical file handling, text processing, data analysis, reporting, and modular Python application development.

---

# ✨ Features

- Analyze multiple log files
- Support `.log` and `.txt` files
- Count INFO, WARNING, ERROR, and CRITICAL log entries
- Search logs using keywords
- Display formatted summary tables
- Generate CSV reports
- Application logging
- Modular project architecture
- Command line interface

---

# 📂 Project Structure

```text
Log_File_Analyzer/
│
├── .venv/
├── sample_logs/
├── reports/
├── logs/
├── tests/
│
├── src/
│   ├── analyzer.py
│   ├── config.py
│   ├── log_parser.py
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

cd 04_File_Handling/Log_File_Analyzer

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Running the Application

```bash
cd src

python main.py
```

---

# 📋 How It Works

1. Place log files inside the `sample_logs` folder.
2. Run the application.
3. All supported log files are loaded automatically.
4. Each log entry is analyzed and categorized.
5. A summary table is displayed.
6. Search logs using any keyword.
7. A CSV report is generated inside the `reports` folder.
8. Application logs are stored in the `logs` folder.

---

# 📄 Sample Output

```text
+-----------+-------+
| Level     | Count |
+-----------+-------+
| INFO      |   12  |
| WARNING   |    3  |
| ERROR     |    2  |
| CRITICAL  |    1  |
+-----------+-------+
```

---

# 📊 Generated Report

| Log Level | Count |
| --------- | ----: |
| INFO      |    12 |
| WARNING   |     3 |
| ERROR     |     2 |
| CRITICAL  |     1 |

---

# 🛠 Technologies Used

- Python 3
- pathlib
- csv
- logging
- tabulate
- colorama

---

# 📚 Concepts Covered

- File Handling
- Text Processing
- CSV Report Generation
- Data Analysis
- Dictionary and Counter
- Logging
- Exception Handling
- Object Oriented Programming
- Modular Programming

---

# 🎯 Learning Outcomes

- Parse and analyze log files
- Process structured text data
- Build reporting tools
- Generate CSV reports
- Organize Python projects professionally
- Develop reusable Python modules

---

# 🚀 Future Improvements

- Support JSON log files
- Filter logs by date range
- Visualize log statistics
- Export reports to Excel
- Interactive dashboard
- Regular expression search
- Real-time log monitoring
- Multi-threaded log processing

---

# 👨‍💻 Author

**Devender J**

GitHub: https://github.com/JDevender007

---

<div align="center">

⭐ If you found this project useful, consider giving it a star.

</div>
