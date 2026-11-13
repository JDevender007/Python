<div align="center">

# 🔐 SSH Automation Tool

### Run remote commands and transfer files over SSH with a clean Python API — plus a fully offline in-memory demo backend.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Paramiko](https://img.shields.io/badge/paramiko-5.x-2D2D2D?style=for-the-badge&logo=python&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

SSH Automation Tool executes commands and copies files on remote machines over SSH, using `paramiko` under the hood. It exposes a small `SSHSession` API (`run`, `run_all`, `upload`, `download`, `close`) that works as a context manager and returns structured `CommandResult` objects with exit status, stdout, and stderr.

The session is backend-driven: point it at a real host with paramiko, or inject the bundled **`LocalShell`** — an in-memory stand-in implementing the same interface — and everything runs with **no network, no credentials, and no listening ports**. The demo and the entire test suite use that offline path.

---

# ✨ Features

- Run one command or a batch and get structured results (exit code, stdout, stderr)
- Upload and download files over SFTP with byte counts
- Password or private-key authentication, connection timeout handling
- Context-manager sessions with idempotent close
- `--script` files: one command per line, `#` comments skipped
- JSON export of command results
- Fully offline demo backend (`LocalShell`) with a tiny shell (`echo`, `pwd`, `whoami`, `ls`, `cat`, `uname`)
- 25 passing pytest tests

---

# 📂 Folder Structure

```text
SSH_Automation_Tool/
│
├── src/
│   ├── main.py         # CLI: demo, run commands, upload/download, JSON export
│   └── ssh_tool.py     # SSHSession, ParamikoBackend, LocalShell, run_demo
│
├── tests/
│   └── test_ssh_tool.py
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

cd 11_Networking/SSH_Automation_Tool

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Fully offline demo (in-memory backend, no network needed)
python src/main.py --demo

# Run commands on a host you control
python src/main.py --host 127.0.0.1 --user me --password pw --cmd "uname -a" --cmd "whoami"

# Batch mode from a script file, with key auth
python src/main.py --host 127.0.0.1 --user me --key ~/.ssh/id_ed25519 --script commands.txt

# File transfer
python src/main.py --host 127.0.0.1 --upload local.txt --remote /tmp/local.txt
python src/main.py --host 127.0.0.1 --download /var/log/app.log --remote app.log
```

Example `commands.txt`:

```text
# maintenance script
whoami
uname -a
echo "all good"
```

---

# ⚠️ Ethical Use

Only SSH into machines you own or have explicit, written authorization to manage. Unauthorized access to computer systems is illegal in most jurisdictions. The tool defaults to `127.0.0.1`; use strong keys, never commit credentials, and prefer key-based authentication over passwords on the command line.

---

# 🛠 Technologies

- Python
- paramiko (SSH client + SFTP)
- argparse
- getpass
- json
- logging
- pytest

---

# 📚 Concepts Covered

- SSH protocol fundamentals (channels, exec, SFTP subsystem)
- Transport abstraction: swapping a real backend for an offline test double
- Structured command results and exit-code propagation
- Private key generation and round-trip loading with paramiko
- Context managers for connection lifecycle
- Script files and batch execution
- Error normalization (`SSHError`) across a library boundary
- Test-driven development without a live server

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**25 tests passed** covering command execution, file transfer round-trips, missing-file and refused-connection error paths, session lifecycle, paramiko key round-trips, and CLI modes — all offline.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
