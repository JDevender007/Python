<div align="center">

# 🔑 Password Strength Analyzer

### A local password strength tool with entropy calculation, pattern detection, and realistic crack-time estimates — nothing ever leaves your machine.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Password Strength Analyzer evaluates how strong a password is by combining several signals: guessing entropy (length × log2 of the charset), character-class variety, and pattern weaknesses such as common passwords, keyboard walks, numeric/letter sequences, repeated characters, and embedded years.

Results include a 0–100 score, a human label, a list of concrete issues, and estimated time-to-crack at five attack rates — from throttled online login to a big GPU rig. Everything runs **in memory, locally, with no network access**.

---

# ✨ Features

- Entropy-based scoring (0–100) with five strength labels
- Character-class detection: lowercase, uppercase, digits, symbols, unicode
- Pattern detection: common passwords, sequences, repeats, keyboard walks, years, low variety
- Crack-time estimates at five realistic attack rates
- Safe display: passwords are always masked in output
- JSON output for scripting, exit code 3 for weak passwords (CI-friendly)
- Fully offline demo with bundled sample passwords
- 38 passing pytest tests

---

# 📂 Folder Structure

```text
Password_Strength_Analyzer/
│
├── src/
│   ├── main.py         # CLI: demo, --password, --stdin, --json, --rate
│   └── analyzer.py     # entropy, patterns, scoring, crack-time estimates
│
├── tests/
│   └── test_analyzer.py
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 12_Cybersecurity/Password_Strength_Analyzer

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: analyse the bundled sample passwords
python src/main.py --demo

# Analyse one password (prefer --stdin so it stays out of shell history)
python src/main.py --password "Tr0ub4dor&3"

echo "my passphrase" | python src/main.py --stdin

# Machine-readable output
python src/main.py --stdin --json

# Custom attack rate (guesses per second)
python src/main.py --stdin --rate 1000000
```

**Exit codes:** `0` = fair or better · `3` = weak · `2` = usage error — so you can gate scripts on it.

---

# 🔒 Privacy

- The password is processed in memory and immediately discarded.
- Nothing is stored, logged, or transmitted — there is no network code in this project at all.
- Output always shows a masked form (`•••••••`), never the raw value.

---

# 🛠 Technologies

- Python
- math / re / string (standard library only)
- argparse
- json
- pytest

---

# 📚 Concepts Covered

- Password entropy and guessing-space calculations
- Character-set analysis
- Heuristic pattern detection
- Time-to-crack modelling across attack scenarios
- Exit-code conventions for scripting
- Sensitive-data handling (masking, no logging)
- Test-driven development

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**38 tests passed** covering class detection, entropy, pattern heuristics, scoring bands, crack-time formatting, masking, and every CLI path.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
