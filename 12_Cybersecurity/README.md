<div align="center">

# 🔐 Cybersecurity Projects

### A collection of Python projects covering password security, hash cracking, vulnerability scanning, packet analysis, and file encryption — all offline-capable and safe by default.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Projects](https://img.shields.io/badge/Projects-5-success?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

This category contains defensive and educational security tools: analysing password strength with entropy models, recovering your own hashes with dictionary and brute-force attacks, auditing hosts for risky services and missing security headers, understanding traffic from pcap files, and encrypting files with authenticated encryption.

Every tool defaults to `127.0.0.1` (or pure local computation), runs fully offline with `--demo`, and ships with an ethical-use notice — these are for **authorized testing and education only**.

---

# 🎯 Learning Objectives

- Model password strength with entropy, patterns, and crack-time estimates
- Understand hash functions, dictionary attacks, and bounded brute force
- Audit TCP services and HTTP security headers with raw sockets
- Dissect packet captures: protocols, talkers, ports, timelines
- Use authenticated encryption (AES-GCM) and memory-hard KDFs (scrypt)
- Design fail-closed security code (wrong password vs. tampered data)
- Build safe-by-default CLIs (loopback gates, masked output, no secrets in logs)
- Test security tooling offline with synthetic inputs

---

# 📂 Projects

No. | Project | Description | Status
--: | --- | --- | :---:
01 | Password Strength Analyzer | Entropy, pattern detection, and crack-time estimates — local only, masked output. | ✅
02 | Hash Cracker | Offline dictionary/mutation/bounded brute-force recovery of MD5/SHA-1/SHA-256. | ✅
03 | Vulnerability Scanner | Port probing, service risk rules, and HTTP security-header audit (loopback by default). | ✅
04 | Network Packet Analyzer | scapy-based pcap analysis: protocol stats, top talkers, ports, timelines. | ✅
05 | File Encryption Tool | AES-256-GCM + scrypt file encryption with tamper detection and `--info` metadata. | ✅

---

# ⚠️ Ethical Use

These projects are for **authorized testing and education only**:

- Scan, probe, and test only systems you own or have explicit permission to test.
- Crack only hashes you own (your own forgotten passwords, lab exercises, CTFs).
- Capture only traffic on networks you are authorized to monitor.
- Never use these techniques against other people's accounts, systems, or data — unauthorized access is illegal in most jurisdictions.
- Defaults are `127.0.0.1` and local computation — keep them that way unless you know what you are doing.

---

# 💡 Concepts Covered

- Password Entropy and Crack-Time Modelling
- Cryptographic Hash Functions (MD5, SHA-1, SHA-256)
- Dictionary Attacks and Password Mutation Rules
- Bounded Brute-Force Search
- TCP Connect Scanning and Banner Grabbing
- HTTP Security Headers (CSP, X-Frame-Options, nosniff, HSTS)
- Severity Ranking and Remediation Reporting
- pcap Format and Packet Dissection
- Authenticated Encryption (AES-256-GCM)
- Memory-Hard Key Derivation (scrypt)
- GCM Tag Verification: Wrong Password vs. Tampering
- Safe-by-Default CLI Design
- Test-driven Development

---

# 📁 Repository Structure

```text
12_Cybersecurity/
│
├── Password_Strength_Analyzer/
├── Hash_Cracker/
├── Vulnerability_Scanner/
├── Network_Packet_Analyzer/
├── File_Encryption_Tool/
│
└── README.md
```

Each project contains:

```text
Project_Name/
├── src/              # main.py + library modules
├── tests/            # pytest test suite
├── data/             # bundled/generated sample data where relevant
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠 Technologies

- Python 3
- socket / http.server (raw TCP and HTTP auditing)
- scapy (packet construction, pcap I/O)
- cryptography (AESGCM, scrypt)
- hashlib / hmac
- argparse / json / logging
- pytest

---

# 📈 Progress

| Project | Status |
| --- | :---: |
| Password Strength Analyzer | ✅ |
| Hash Cracker | ✅ |
| Vulnerability Scanner | ✅ |
| Network Packet Analyzer | ✅ |
| File Encryption Tool | ✅ |

**Completed:** **5 / 5 Projects**

---

# ▶️ Quick Start

```bash
cd 12_Cybersecurity/Password_Strength_Analyzer

python src/main.py --demo     # offline demo
python -m pytest tests/ -q    # run the tests
```

---

# 📚 Skills Developed

- Threat modelling for small tools
- Offline security testing strategies
- Raw-socket network programming
- Binary format design and parsing
- Fail-closed error handling
- Secret handling (masking, pass-files, no logging)
- Modular Programming and Type Hints
- Automated Testing

---

# 🚀 Key Learning Outcomes

- Explain why authenticated encryption beats plain encryption
- Quantify password strength instead of guessing with rules alone
- Audit a web service's headers and interpret the risk of each miss
- Analyse captures without touching the network
- Keep offensive-capable tools safe by default (localhost gates, bounded searches)

---

# 🔮 Future Enhancements

- Steganography tool (LSB image hiding)
- Certificate/TLScipher audit tool
- Credential-strength corpus tester with rockyou-style rules
- Suricata/Snort-style rule matcher for pcaps
- Key-derivation benchmark harness (scrypt vs. argon2)
- Encrypted container with key files in addition to passwords
- Security-header monitoring with trend history

---

# 🤝 Contributions

Suggestions, improvements, and feedback are welcome. Feel free to open an issue or submit a pull request.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found these projects useful, consider giving this repository a star.

</div>
