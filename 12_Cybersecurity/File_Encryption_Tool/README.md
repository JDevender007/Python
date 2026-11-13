<div align="center">

# 🔒 File Encryption Tool

### Authenticated file encryption with AES-256-GCM and scrypt — tamper-evident, wrong-password-rejecting, fully local.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![cryptography](https://img.shields.io/badge/cryptography-AES--256--GCM-orange?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

File Encryption Tool encrypts files with **AES-256-GCM**, an authenticated cipher that both confidentiality and integrity — if the file is tampered with or the password is wrong, decryption fails loudly instead of writing garbage. The key is derived from your password with **scrypt** (memory-hard, `log_n=14`) and a fresh random salt for every file.

Container format (version 1):

```text
magic (8) │ version (1) │ salt (16) │ nonce (12) │ ciphertext + GCM tag (N + 16)
```

The salt and nonce are stored in the file so each encryption is unique; the password is never stored or transmitted. `--info` shows container metadata without needing the password. Everything runs **locally with no network code**.

---

# ✨ Features

- AES-256-GCM authenticated encryption (confidentiality + integrity)
- scrypt key derivation with per-file random salt (memory-hard KDF)
- Versioned container with magic bytes — safe format evolution
- Wrong password **and** tampering both rejected via GCM tag verification
- `--info`: inspect version/salt/nonce/size without the password (text or JSON)
- Password sources: `--pass-file` (preferred), `--password`, or getpass prompt
- Binary-safe: any file content round-trips byte-for-byte
- Idempotent offline demo: encrypt → verify → decrypt → reject wrong password → detect tampering
- 39 passing pytest tests

---

# 📂 Folder Structure

```text
File_Encryption_Tool/
│
├── src/
│   ├── main.py          # CLI: demo, --encrypt, --decrypt, --info, password sources
│   └── crypto_tool.py   # format, KDF, AESGCM, file ops, run_demo
│
├── tests/
│   └── test_crypto_tool.py
│
├── data/                # created by the demo (sample + ciphertext + restore)
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 12_Cybersecurity/File_Encryption_Tool

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: encrypt, verify, decrypt, reject bad password, detect tampering
python src/main.py --demo

# Encrypt / decrypt (prompts for the password securely)
python src/main.py --encrypt secret.pdf
python src/main.py --decrypt secret.pdf.enc --out secret.pdf

# Password file (no shell-history exposure)
python src/main.py --encrypt notes.txt --pass-file pw.txt

# Container metadata, no password needed
python src/main.py --info secret.pdf.enc
python src/main.py --info secret.pdf.enc --json
```

**Exit codes:** `0` = success · `1` = wrong password / tampered file · `2` = usage or file error.

---

# ⚠️ Safe Use

- There is **no password recovery**: lose the password and the data is gone by design. Back up passwords/passphrases.
- Prefer `--pass-file` or the interactive prompt; `--password` shows up in shell history and process lists.
- The demo password is intentionally trivial — never reuse it.
- GCM nonces are random per file; never encrypt the same plaintext with the same key+nonce (the format guarantees a fresh salt/nonce each run).

---

# 🛠 Technologies

- Python
- cryptography (AESGCM, scrypt)
- argparse / json / getpass / logging
- pytest

---

# 📚 Concepts Covered

- Authenticated encryption: why MAC/tag verification matters
- Nonce/salt uniqueness and its role in GCM safety
- Memory-hard key derivation (scrypt) vs. plain hashing
- Binary container formats: magic bytes, versions, header parsing
- Fail-closed error handling (wrong password vs. corrupt file)
- Constant-safe comparison via cryptography's InvalidTag path
- Binary-safe file I/O
- Test-driven development for security code (round-trips, tamper tests)

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**39 tests passed** covering round-trips (bytes and files), key derivation determinism, container layout, header/version/magic errors, wrong-password and tamper rejection, truncation, binary content, demo idempotency, and every CLI path — all offline.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
