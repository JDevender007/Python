<div align="center">

# ☁️ Cloud Computing Projects

### A collection of Python projects covering object storage, cost estimation, load balancing, configuration management, and serverless event queues — all runnable offline with `--demo`.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Projects](https://img.shields.io/badge/Projects-5-success?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

This category explores the core building blocks of cloud systems: object storage through a boto3 wrapper, infrastructure cost modelling with bundled rate cards, load-balancing strategies with health checks and failover, configuration validation with drift detection, and SQS-style message queues for serverless workflows.

Every project runs **fully offline** with `--demo` — S3 calls are scripted with botocore's `Stubber`, the load balancer simulates backends in-process, and the queue runs on a fake clock. No AWS account, no credentials, no network.

---

# 🎯 Learning Objectives

- Use boto3/botocore safely with offline stubbed testing
- Model cloud costs: unit pricing, reserved-instance plans, budgets
- Implement load-balancing strategies and health-check state machines
- Validate and diff infrastructure-as-code configs with secret masking
- Reproduce queue semantics: visibility timeouts, DLQs, dedup windows
- Design deterministic simulations (seeded RNGs, fake clocks)
- Build CI-friendly CLIs with meaningful exit codes

---

# 📂 Projects

No. | Project | Description | Status
--: | --- | --- | :---:
01 | S3 File Manager | boto3 wrapper for buckets/objects/presigned URLs with an offline Stubber demo. | ✅
02 | Cloud Cost Calculator | JSON infra configs priced against bundled aws/gcp rate cards, plan comparison, savings tips. | ✅
03 | Load Balancer Simulator | Five strategies, health checks, failover, and distribution stats — in-process, seeded. | ✅
04 | Cloud Config Manager | YAML/JSON validation, deep-merge overlays, drift plans with secret masking, `--check`. | ✅
05 | Serverless Event Queue | SQS-style queue: visibility timeouts, dead-letter redrive, dedup, fake-clock demo. | ✅

---

# 💡 Concepts Covered

- S3 Object Model: Buckets, Keys, Prefixes, ETags
- botocore Stubber: Scripted API Tests Without a Network
- Presigned URLs and Local SigV4 Signing
- Unit Economics of Cloud Resources (per-hour, per-GB)
- Reserved-Instance Effective Rates and Plan Comparison
- Load-Balancing Algorithms (Round-Robin, Least-Connections, WRR, IP-Hash)
- Health-Check Thresholds and Failover Retry Semantics
- Schema Validation with JSON-Path Error Reporting
- Desired vs. Observed State: Drift Detection
- Secret Redaction in Diffs and Plans
- At-Least-Once Delivery and Visibility Timeouts
- Dead-Letter Queues and Poison-Message Containment
- Deterministic Simulation (Seeded RNG, Fake Clock)

---

# 📁 Repository Structure

```text
13_Cloud_Computing/
│
├── S3_File_Manager/
├── CloudCost_Calculator/
├── Load_Balancer_Simulator/
├── Cloud_Config_Manager/
├── Serverless_Event_Queue/
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
- boto3 / botocore (S3 client, Stubber)
- PyYAML (config loading/dumping)
- argparse / json / dataclasses / logging
- pytest

---

# 📈 Progress

| Project | Status |
| --- | :---: |
| S3 File Manager | ✅ |
| Cloud Cost Calculator | ✅ |
| Load Balancer Simulator | ✅ |
| Cloud Config Manager | ✅ |
| Serverless Event Queue | ✅ |

**Completed:** **5 / 5 Projects**

---

# ▶️ Quick Start

```bash
cd 13_Cloud_Computing/S3_File_Manager

python src/main.py --demo     # offline demo
python -m pytest tests/ -q    # run the tests
```

---

# 📚 Skills Developed

- Offline cloud development and testing strategies
- Deterministic simulation design
- Infrastructure-as-code validation thinking
- Message-queue semantics for serverless architectures
- Modular Programming and Type Hints
- Automated Testing
- CI-Friendly CLI Design

---

# 🚀 Key Learning Outcomes

- Test cloud code without an account using botocore's Stubber
- Estimate and compare infrastructure costs before deploying
- Explain when each load-balancing strategy wins
- Catch config drift before it becomes an outage
- Design consumers that survive crashes (visibility timeouts + DLQs)

---

# 🔮 Future Enhancements

- Terraform-state style plan/apply workflow
- Auto-scaling simulator driven by simulated metrics
- Multi-region failover planner with RTO/RPO estimates
- S3 lifecycle-policy rule engine
- Step-function style workflow orchestrator over the event queue
- Cost anomaly detection against a historical usage CSV

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
