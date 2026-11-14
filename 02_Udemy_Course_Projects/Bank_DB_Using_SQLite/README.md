<div align="center">

# 🏦 Bank DB Using SQLite

### A bank where the balance is not stored — it is *derived*. Three tables, two-leg atomic transfers, and an audit that proves the money still adds up.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Standard%20Library-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Offline](https://img.shields.io/badge/Offline-No%20Network-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

The course version was three throwaway scripts: `create_db.py` built the tables, `insert_data.py` inserted rows with hard-coded `VALUES (...)`, and `queries.py` ran whatever SQL the lesson needed. Every script opened its own connection, and `accounts.balance` was a `REAL` column updated by hand.

That design has three problems that only show up once money actually moves.

**The balance is stored twice.** `accounts.balance` and the `transactions` rows both describe the same fact. A crash between the `UPDATE` and the `INSERT` leaves them disagreeing forever, and there is nothing in the schema that notices.

**`REAL` money drifts.** `0.1 + 0.2 != 0.3` in binary floating point. A bank that rounds per row accumulates error, and the error is invisible because each individual row looks fine.

**A transfer is two writes with nothing holding them together.** Debit the source, credit the destination — if the second write fails, the money has vanished. The legacy scripts had no transaction at all, so this was not a rare case, it was the normal case for a crash.

This version fixes all three with one structural change:

```text
balance(account) = opening + SUM(amount_cents)
```

The balance is a **query**, not a column. It cannot be stale because it is not stored. Money is `INTEGER` cents, so sums are exact. And a transfer is two ledger rows inside one `BEGIN IMMEDIATE` block, sharing one `ref` — so either both land or neither does.

```text
transfer(101 -> 102, 250.00)     one ref: TR-001

  trans_id  acc_id  kind           amount  ref
        5     101   transfer_out   -25000  TR-001
        6     102   transfer_in    +25000  TR-001
                                    ------
                                         0      nets to zero
```

**The schema enforces its own rules.** Six `CHECK` constraints reject a positive withdrawal, a negative deposit, an unknown kind and an unknown account type. `UNIQUE(email)` stops duplicate customers. `UNIQUE (ref, kind)` allows exactly one `transfer_out` and one `transfer_in` per ref — which is why `ref` cannot simply be `UNIQUE`, since both legs share it.

**The audit is the interesting part.** `audit()` reports every invariant that can be checked from the data alone: broken foreign keys, negative balances, a transfer with the wrong number of legs, a transfer that does not net to zero, a row whose sign contradicts its kind, and a transfer leg with no ref. A clean bank returns `[]`. The demo then plants a deliberately orphaned leg, shows the audit catching it by name, and removes it again.

**The negative controls are what make the demo worth reading.** An overdraft is refused and *no transaction row is written* — checked by counting rows before and after. An oversized transfer leaves both accounts untouched. A transfer to a missing account rolls the first leg back, so there is no orphan `transfer_out` with `ref IS NULL`. Each assertion would fail if the code regressed to the legacy behaviour.

**Everything is falsifiable.** The demo asserts the four seed balances in cents, the `7700.50` total, sub-cent and non-numeric amounts being refused, the two legs of `TR-001`, a ledger whose running total ends at the derived balance, a duplicate email and a positive withdrawal both rejected by constraints, a clean audit that catches a planted problem, and a file-backed database reopening with the same balances.

No network, no ORM, no third-party library — just `sqlite3` from the standard library.

---

# ✨ Features

- Three-table schema with `CHECK`, `UNIQUE`, `FOREIGN KEY` and two indexes
- `PRAGMA foreign_keys = ON` on every connection, enforced not assumed
- **Derived balances** — `opening + SUM(amount)`, no stored `balance` column
- Integer cents throughout, with sub-cent input refused rather than rounded
- `deposit` / `withdraw` with an overdraft guard that writes nothing on failure
- `transfer` — two legs, one ref, `BEGIN IMMEDIATE`, rollback on any error
- `next_ref` — the smallest unused `TR-nnn`, not a count that can collide
- `ledger` — one account's rows with a running balance
- `audit` — six independent invariant checks, each naming the rule it broke
- Idempotent seed (`INSERT OR IGNORE` for keys, empty-ledger guard for history)
- In-memory by default, file-backed with `--db`
- CLI: `--customers`, `--ledger`, `--audit`, `--deposit`, `--withdraw`, `--transfer`, `--json`, `--quiet`
- Exit `2` on a bank error; `--demo` always returns `0`
- 99 passing pytest tests

---

# 📂 Folder Structure

```text
Bank_DB_Using_SQLite/
│
├── src/
│   ├── main.py      # CLI: accounts, customers, ledger, audit, mutations
│   └── bank.py      # schema, money, ledger, transfer, audit, demo
│
├── tests/
│   └── test_bank.py
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 02_Udemy_Course_Projects/Bank_DB_Using_SQLite

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: schema, balances, transfer, rollback, audit, reopen
python src/main.py --demo

# Accounts and derived balances (in-memory seed, discarded on exit)
python src/main.py

# One account's ledger with a running balance
python src/main.py --ledger 101

# Every invariant check
python src/main.py --audit

# Mutations, still in memory unless --db is given
python src/main.py --deposit 101 500.00
python src/main.py --withdraw 101 200.00
python src/main.py --transfer 101 102 250.00

# A real file, so the change survives the process
python src/main.py --db bank.db --transfer 101 102 250.00

# Machine-readable output
python src/main.py --json out.json --quiet
```

**Seed data** (opening balances and four history rows):

| acc | customer | type | opening | balance |
|-----|----------|------|---------|---------|
| 101 | Anil | Savings | 2500.00 | 3000.00 |
| 102 | Smith | Checking | 1200.50 | 900.50 |
| 103 | Ramesh | Savings | 1500.00 | 2300.00 |
| 104 | Khan | Checking | 1700.00 | 1500.00 |
| | | | **total** | **7700.50** |

**Exit codes:** `0` = the command ran · `2` = unknown account, overdraft, bad amount or database error.

---

# 🧠 How It Works

```text
accounts.opening ──┐
                   ├──► balance = opening + SUM(transactions.amount)
transactions ──────┘                    (integer cents)
```

**Why the balance is derived.** A stored balance is a cache of a query. Caches go stale; queries cannot. The cost is one `SUM` per read, which is what the `ix_transactions_acc` index is for.

**Why `UNIQUE (ref, kind)` and not `UNIQUE ref`.** Both legs of a transfer must share the ref so they can be paired, but only one leg of each kind may exist per ref. A plain `UNIQUE ref` makes the second insert fail — the constraint would forbid the very thing it was meant to protect. SQLite treats `NULL` refs as distinct, so ordinary deposits and withdrawals are unaffected.

**Why `BEGIN IMMEDIATE`.** It takes the write lock at the start of the transaction instead of on the first write. Under concurrency that converts a lock-upgrade deadlock into a clean wait, and it means the balance read inside the transfer is the balance the writes commit against.

**Why validation happens before `BEGIN`.** `balance()` and the destination `account_of()` lookup both run first. If either fails, no transaction was ever opened, so there is nothing to roll back — the failure modes stay simple.

**What the audit cannot check.** It verifies internal consistency, not external truth: it cannot know whether a deposit of 500.00 ever happened, only that if it is in the ledger then the balances still reconcile. That is stated plainly rather than implied.

**Determinism.** No timestamps, no random refs, no filesystem ordering. Two runs print byte-identical output, and two fresh in-memory banks produce identical account lists.

---

# 🛠 Technologies

- Python 3 standard library: `sqlite3`, `argparse`, `json`, `pathlib`, `tempfile`, `contextlib`
- pytest

No ORM, no server, no network access.

---

# 📚 Concepts Covered

- SQLite schema design: `CHECK`, `UNIQUE`, composite uniqueness, `FOREIGN KEY`
- `PRAGMA foreign_keys` per connection and `PRAGMA foreign_key_check`
- Derived state versus stored state, and why caches go stale
- Integer cents versus floating-point money
- Atomicity: `BEGIN IMMEDIATE`, commit, rollback
- Double-entry bookkeeping: two legs, one ref, net zero
- Referential integrity as a runtime guarantee, not a convention
- Idempotent seeding
- Invariant auditing as a first-class function
- Indexes on join and foreign-key columns
- Row factories and mapping-style row access
- Negative controls in a self-asserting demo

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**99 tests passed** covering cent conversion (eight cases, sub-cent, NaN, booleans, `None`, and the `0.1 + 0.2` float-noise identity); money formatting and round-tripping; schema creation, idempotency and three-table order; `PRAGMA foreign_keys`; seed counts, ordering and idempotency; derived balances per account, the total, and the `opening + SUM` identity; deposits and withdrawals including notes, non-positive amounts, a full-balance withdrawal and a refused overdraft that writes nothing; transfers with two legs, sequential refs, ref reuse, conserved totals, same-account refusal, oversized refusal touching neither account, missing-destination rollback and emptying an account; ledger running balances; eight constraint violations (duplicate email, unknown account type, negative opening, wrong signs, unknown kind, orphan account, orphan transaction, duplicate ref+kind, and multiple `NULL` refs); six audit findings including one on a hand-built schema without `CHECK` constraints, since the real schema makes that row unreachable; a file-backed database reopening with the same balances and a clean audit; demo determinism; and every CLI path including overdraft exit `2`.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
