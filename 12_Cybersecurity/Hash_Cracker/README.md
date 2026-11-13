<div align="center">

# 🔓 Hash Cracker

### An offline educational hash cracker with dictionary, mutation, and bounded brute-force attacks — local wordlist, no network.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Hash Cracker recovers the plaintext behind MD5, SHA-1, and SHA-256 digests using three attack modes: a bundled dictionary wordlist with password mutations (case flips, suffixes, leet speak), a bounded brute-force search over configurable character sets, and a hybrid of both.

It is a **defensive/educational tool**: use it to understand why weak hashes fall, to recover a hash of your own forgotten password, or in CTF-style labs. Everything runs locally — there is no network code in this project.

---

# ✨ Features

- MD5, SHA-1, and SHA-256 support with known-answer tests
- Dictionary attack with 100+ bundled words and smart mutations
- Bounded brute-force (character sets, min/max length, hard cap at 8, time budget)
- Hybrid mode: dictionary first, brute force second
- Attempt counts, elapsed time, and candidates/second statistics
- `--hash-text` and `--verify` helper modes for scripting
- JSON output; exit code 1 when nothing is found
- Fully offline demo that cracks four hidden secrets
- 37 passing pytest tests

---

# 📂 Folder Structure

```text
Hash_Cracker/
│
├── src/
│   ├── main.py         # CLI: demo, crack, --hash-text, --verify, --json
│   └── cracker.py      # hashing, mutations, brute force, crack orchestration
│
├── tests/
│   └── test_cracker.py
│
├── data/
│   └── wordlist.txt    # bundled offline wordlist (common passwords + words)
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 12_Cybersecurity/Hash_Cracker

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: four hidden secrets are hashed and recovered
python src/main.py --demo

# Dictionary attack against your own digest
python src/main.py --hash <hex> --algo sha256 --mode dictionary

# Bounded brute force over digits, up to 4 characters
python src/main.py --hash <hex> --algo sha1 --mode bruteforce --charset digits --max-len 4

# Your own wordlist, no mutations
python src/main.py --hash <hex> --wordlist mine.txt --no-mutations

# Helpers
python src/main.py --hash-text "abc" --algo md5
python src/main.py --verify "abc" 900150983cd24fb0d6963f7d28e17f72
```

---

# ⚠️ Ethical Use

Only crack digests you own or have explicit authorization to test (your own forgotten passwords, lab exercises, CTF challenges). Unauthorized access to others' data is illegal. Brute force is deliberately capped (max length 8, time budget) to keep searches bounded.

---

# 🛠 Technologies

- Python
- hashlib / hmac (standard library only)
- itertools
- argparse / json
- pytest

---

# 📚 Concepts Covered

- Cryptographic hash functions and hex digests
- Dictionary attacks and password mutation rules
- Leet-speak and case permutation search spaces
- Exhaustive search with bounded keyspace
- Time budgets and progress statistics
- Constant-time digest comparison
- Test-driven development

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**37 tests passed** covering known hash vectors, wordlist parsing, mutation generation, brute-force enumeration, all three attack modes, error paths, and every CLI mode.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
