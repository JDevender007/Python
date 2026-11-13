<div align="center">

# ☁️ S3 File Manager

### A clean boto3 wrapper for S3 with uploads, downloads, listings, presigned URLs — and a fully offline demo powered by botocore's Stubber.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![boto3](https://img.shields.io/badge/boto3-S3-orange?style=for-the-badge&logo=amazon-aws&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

S3 File Manager wraps the everyday S3 operations — create bucket, put, get, head/exists, list with pagination, delete, upload/download files, presigned GET URLs — behind a small `S3Manager` API with friendly `S3Error` messages instead of raw `ClientError` tracebacks.

The demo and test suite run **fully offline** using botocore's `Stubber`: every API call is scripted in-process with fake credentials, so no network, no AWS account, and no credentials are ever needed. For real usage, the manager accepts any boto3 client (AWS, MinIO, LocalStack, R2 via `--endpoint-url`).

---

# ✨ Features

- `put_bytes` / `get_bytes` / `exists` / `delete` / `list_objects` (paginated, sorted)
- `upload_file` / `download_file` for local paths
- `create_bucket` with correct region handling (`us-east-1` vs. others)
- Presigned GET URLs with validated expiry (signed locally, no network)
- Bucket-name and object-key validation with clear error messages
- ClientError → `S3Error` translation (404, NoSuchBucket, AccessDenied, ...)
- Fully offline demo driven by botocore `Stubber` (asserts every call was scripted)
- Custom endpoint support (`--endpoint-url`) for MinIO/LocalStack
- 32 passing pytest tests

---

# 📂 Folder Structure

```text
S3_File_Manager/
│
├── src/
│   ├── main.py         # CLI: demo, --list, --put, --get, --delete, --url
│   └── s3_manager.py   # S3Manager, validation, error mapping, Stubber demo
│
├── tests/
│   └── test_s3_manager.py
│
├── data/               # created by the demo (downloaded copy)
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 13_Cloud_Computing/S3_File_Manager

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Fully offline demo: full bucket lifecycle against a stubbed client
python src/main.py --demo

# Real operations (standard AWS credential chain)
export S3_BUCKET=my-bucket
python src/main.py --list
python src/main.py --put ./report.pdf --key reports/report.pdf
python src/main.py --get --key reports/report.pdf --out copy.pdf
python src/main.py --url --key reports/report.pdf --expires 900
python src/main.py --delete --key reports/report.pdf

# JSON listing for scripts
python src/main.py --list --prefix reports/ --json

# Local S3-compatible server (MinIO / LocalStack)
python src/main.py --list --bucket demo --endpoint-url http://127.0.0.1:9000
```

---

# ⚠️ Ethical Use

Only manage buckets you own or are explicitly authorized to access. Keep credentials in environment variables or IAM roles — never hard-code them. The demo uses fake credentials and a stubbed client; it never touches AWS.

---

# 🛠 Technologies

- Python
- boto3 / botocore (S3 client, Stubber, error types)
- argparse / json / logging
- pytest

---

# 📚 Concepts Covered

- S3 object model: buckets, keys, prefixes, ETags
- Paginated listing with continuation tokens
- botocore Stubber: scripted API testing without a network
- ClientError inspection: error codes → friendly messages
- Presigned URL generation (local SigV4 signing)
- Credential chains vs. explicit fake credentials
- Custom endpoints for S3-compatible storage
- Validation at the API boundary (bucket/key rules)

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**32 tests passed** covering validation, all object operations, pagination, error mapping (404/403), file transfers, presigned URLs, demo idempotency, and CLI paths — entirely offline via `Stubber`.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
