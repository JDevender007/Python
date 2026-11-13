<div align="center">

# 📁 FTP Client

### A clean ftplib-based FTP client with upload, download, listing, directory management, and a fully offline in-memory demo.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

FTP Client is a command line wrapper around Python's standard library `ftplib` that handles the everyday FTP operations: listing directories, uploading and downloading files, creating folders, renaming, and deleting.

The project ships with an **offline demo backend** (`LocalFTP`) — an in-memory stand-in that speaks the same call surface as a real server — so the demo and test suite run with no network, no credentials, and no listening ports. For real transfers, point the client at an FTP server you own or are authorized to use.

---

# ✨ Features

- Connect, login, and clean quit with friendly error wrapping
- Directory listing with size detection and directories-first ordering
- Upload and download with byte counts and content verification
- Remote mkdir, rename, and delete
- Typed `FTPError` exceptions with actionable messages
- Offline in-memory demo backend (`LocalFTP`) for zero-network runs
- 15 passing pytest tests

---

# 📂 Folder Structure

```text
FTP_Client/
│
├── src/
│   ├── main.py         # CLI entry point (demo, list, upload, download...)
│   └── ftp_client.py   # FTPClient, RemoteEntry, LocalFTP demo backend
│
├── tests/
│   └── test_ftp_client.py
│
├── data/               # created automatically by the demo
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 11_Networking/FTP_Client

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Fully offline demo (in-memory server, no network needed)
python src/main.py --demo

# List a remote directory
python src/main.py --host 127.0.0.1 --user me --password pw --list

# Upload / download
python src/main.py --host 127.0.0.1 --upload local.txt
python src/main.py --host 127.0.0.1 --download remote.txt
```

---

# ⚠️ Ethical Use

Only connect to FTP servers you own or have explicit permission to use. Credentials passed on the command line are visible to other local processes — prefer environment variables or a config file for real work.

---

# 🛠 Technologies

- Python
- ftplib
- pathlib
- argparse
- logging
- pytest

---

# 📚 Concepts Covered

- FTP protocol commands (NLST, STOR, RETR, MKD, RNFR/RNTO, DELE)
- Binary vs line-oriented transfers
- Exception normalization across a library boundary
- Offline test doubles that mimic a network service
- Context-managed file I/O
- CLI design with argparse
- Test-driven development

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**15 tests passed** covering upload/download round-trips, listing and ordering, directory operations, error paths for missing files and unreachable servers, and CLI modes.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
