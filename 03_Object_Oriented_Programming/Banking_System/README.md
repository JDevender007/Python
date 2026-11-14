<div align="center">

# 🏦 Banking System

### The legacy project stored the balance in a `Float` column and then incremented it row by row — the same fact in two places, one of them drifting — and opened with `id="q2m4nl"`, a stray assignment that silently rebinds the builtin `id` in that module.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

The old version was SQLAlchemy over SQLite, with money as a float:

```python
balance = Column(Float, nullable=False, default=0.0)

account.balance += amount
transaction = Transaction(account_id=account.id, amount=amount)
```

Three things are wrong, and only the first is about float arithmetic.

**1 · Two places for one fact.** The balance is a column *and* a sum of transactions. Any bug that writes one without the other leaves a number that looks right and is not. Ten deposits of `0.10` land on `0.99999999999999989`, so even with no bug the column drifts.

**2 · A stray assignment.** The service file began with:

```python
id="q2m4nl"
```

That parses. It rebinds `id` in that module's namespace, so a later `id(...)` there raises `TypeError: 'str' object is not callable`. Nothing warns, because nothing is wrong with the statement — only with what it takes away.

**3 · The object was a record.** `Account` had columns and a `__repr__`; every rule lived in a `BankingService` method that fetched the row, did arithmetic and `print`ed. The classes were a schema, not a domain.

The replacement is three ideas:

**Money is a value object.** A frozen, ordered, hashable `Money` holding integer cents. It refuses a float at construction, so `Money(0.1)` is an error rather than a rounding event, and it implements `__radd__` so `sum([...])` works on a list of amounts.

**The balance is derived.**

```python
balance = opening + sum(entry.amount for entry in ledger)
```

`balance` is a read-only property; there is no attribute to assign. A stale balance is not a bug to avoid — it is a number that cannot exist. `len(account)` is its number of entries, iteration yields them, and `"TR-0004-001" in account` asks about references.

**Subclasses change the rule, not the method.** `withdraw` is one template method:

```python
def withdraw(self, amount, when, memo="", reference=None):
    self._check_withdrawal(amount, when)
    return self._post_withdrawal(amount, when, memo, reference)
```

`SavingsAccount` refuses to fall below a minimum balance and refuses a withdrawal past its monthly limit; `CurrentAccount` allows a negative balance down to an overdraft limit and posts a fee row beside every withdrawal. The same call means the same thing for both, and the difference is two overridden hooks — not an `if` on a type string.

**The demo proves all of it**, including the negative controls: a fabricated ledger row fails exactly one of the seven audit checks, and a refused transfer leaves both ledgers byte-identical.

Standard library only: no SQLAlchemy, no database file, no network.

---

# ✨ Features

- `Money` — integer cents, frozen, ordered, hashable, `__radd__` for `sum()`
- `Money.from_str` — `Rs 1,234.56`, `$5.00`, `-0.05`; refuses three decimals and floats
- `round_half_up` and `interest_on` — integer half-up rounding, not `round()`'s half-even
- `Transaction` — frozen, signed, kind-checked, strict ISO dates
- `Account` — opening balance plus an append-only ledger; derived read-only `balance`
- `SavingsAccount` — minimum balance, monthly withdrawal limit, interest credit
- `CurrentAccount` — overdraft limit, per-withdrawal fee as its own ledger row
- `Bank` — sequential numbering, lookup, search, atomic two-row transfers
- `Bank.audit` — seven named invariants, each reported pass or fail
- `load_bank` / `save_bank` — JSON round trip with unknown keys refused
- `data/bank.json` — 4 accounts, one transfer pair, one closed account, total 2,200.00
- CLI: `--list`, `--balance`, `--statement`, `--audit`, `--open`, `--deposit`, `--withdraw`, `--transfer`, `--legacy`, `--write`, `--json`, `--quiet`
- Exit `2` on a `BankingError`; `--demo` always returns `0`
- 244 passing pytest tests

---

# 📂 Folder Structure

```text
Banking_System/
│
├── src/
│   ├── main.py     # CLI: list, statement, audit, open/deposit/withdraw/transfer
│   └── banking.py  # Money, Transaction, Account + 2 subclasses, Bank, audit
│
├── tests/
│   └── test_banking.py
│
├── data/
│   └── bank.json   # 4 accounts, 2,200.00 total
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 03_Object_Oriented_Programming/Banking_System

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo
python src/main.py --demo

# Every account, one line each
python src/main.py

# One ledger
python src/main.py --statement AC-0001

# The seven invariants
python src/main.py --audit

# Money movement
python src/main.py --deposit AC-0002:250.00
python src/main.py --withdraw AC-0003:100.00
python src/main.py --transfer AC-0001:AC-0003:250.00

# Open an account, and keep the change
python src/main.py --open "savings:New Person:1,000.00" --write out.json

# What the legacy file did
python src/main.py --legacy
```

**Exit codes:** `0` = the command ran · `2` = unknown account, a refused rule (minimum balance, monthly limit, overdraft, closure), a bad amount, a bad or missing data file.

---

# 🧠 How It Works

```text
 Money(cents)                     integer cents, frozen, ordered
   │
 Transaction(kind, amount, when)  signed, validated, immutable
   │
 Account                          opening + ledger -> balance
   ├── withdraw()  ──► _check_withdrawal()   (subclass hook)
   │                └► _post_withdrawal()    (subclass hook)
   ├── SavingsAccount   minimum, monthly limit, interest
   └── CurrentAccount   overdraft, fee row
        │
      Bank  ──► transfer(): both checks, then both rows
             └► audit(): 7 invariants over the ledgers
```

Details worth knowing:

- **The fee is a row, not an adjustment.** `CurrentAccount.withdraw` writes `withdrawal` and `fee` separately, so the ledger stays additive and the fee is visible in a statement. The check subtracts the fee up front, so an allowed withdrawal cannot push the account past its overdraft by charging it.
- **A transfer counts toward the savings limit.** Otherwise the monthly limit could be bypassed by sending money to a second account. `withdrawals_in` counts both `withdrawal` and `transfer_out`.
- **Transfers are validated on both sides first.** The two rows are written only after the source can pay and the destination can receive, so a refusal cannot leave half a transfer behind; the demo compares both ledgers before and after three refusals.
- **`audit` walks the prefixes, not the total.** A savings account that dipped below its minimum and recovered still fails, because the running balance is checked after every entry.
- **Money never touches a float**, and the rounding function is half-up in integers: `(n * 2 + d) // (2 * d)`. `round(0.5)` is `0` in Python, which is the wrong direction for interest.

---

# 🛠 Technologies

- Python 3 standard library: `decimal`, `dataclasses`, `datetime`, `json`, `pathlib`, `argparse`, `contextlib`, `tempfile`
- pytest 9.1.1

No ORM, no database server, no network.

---

# 📚 Concepts Covered

- Value objects versus records
- Derived state versus duplicated state
- Integer cents and why money is not a float
- Frozen dataclasses, ordering, hashing, `__radd__`
- The template method pattern and two overridden hooks
- Polymorphism through methods, not type strings
- Read-only properties and invariants by construction
- Append-only ledgers and prefix invariants
- Atomic multi-row operations with a rollback path
- Half-up rounding in integers
- Name shadowing of builtins, and why it is silent
- Strict ISO date validation with a render-and-compare round trip

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**244 tests passed** covering `Money` (construction, six refusals, immutability, hashing, ten parse shapes, nine refusals, arithmetic, ordering, `sum`, formatting, `to_json`), rounding (six pinned cases, negatives, a zero denominator, `round` versus half-up), interest (five pinned cases, negative balances, four refusals), date validation (strict ISO, seven refusals, `month_of`), `Transaction` (kinds, signs both ways, zero, non-Money, bad date, memo, reference, `line`, `to_dict`), the base `Account` (opening validation, deposit, withdrawal, refusal to overdraw, read-only balance, iteration, `in`, closure rules, statement, repr), `SavingsAccount` (minimum, monthly limit and its reset, interest, dict), `CurrentAccount` (overdraft, fee rows, the fee in the check, dict), `Bank` (numbering, lookup, search, containment, totals, duplicate refusal), transfers (balanced rows, five refusals, untouched ledgers, closed destinations, the savings limit), the audit (seven checks, six ways to fail one), persistence (round trip, seven refusals, save idempotence), the seeded file (four balances, matching reference, closed account), the demo, and every CLI mode including JSON and quiet.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
