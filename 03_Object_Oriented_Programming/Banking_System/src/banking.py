"""A bank whose balance is a fact about its ledger, not a column.

The legacy project in this folder stored money in a ``Float`` column:

    balance = Column(Float, nullable=False, default=0.0)

    account.balance += amount
    transaction = Transaction(account_id=account.id, amount=amount)

so the same fact lived in two places, and the place that was a float drifted.
Its ``banking_service.py`` also opened with a stray line that was never code:

    id="q2m4nl"

That is a valid assignment. It rebinds the builtin ``id`` in that module, so
any later ``id(...)`` call in the same file raises ``TypeError``, and nothing
warns. ``LEGACY_HEAD`` below keeps the pattern so the demo can prove both
halves.

Three ideas replace the float column:

**1. Money is a value object holding integer cents.** ``Money`` refuses a
float at construction, because ``0.1 + 0.2`` is not ``0.3`` and a bank that
rounds per row drifts. It is frozen, ordered, and hashable, so it can be
summed with ``sum()`` (via ``__radd__``), sorted, and used as a dictionary key.

**2. The balance is derived.** An account stores an opening balance and a
ledger of signed entries:

    balance = opening + sum(entry.amount for entry in ledger)

There is no ``balance`` attribute to assign, only a read-only property, so a
stale balance is not a bug to avoid -- it is a number that cannot exist.

**3. Subclasses change the rule, not the method.** ``withdraw`` is one
template method in the base class; it calls ``_check_withdrawal`` and then
``_post_withdrawal``, and those are the two hooks:

    SavingsAccount   refuses to fall below a minimum balance, and refuses a
                     fourth withdrawal in the same month
    CurrentAccount   allows a negative balance down to an overdraft limit,
                     and posts a fee row beside every withdrawal

So ``account.withdraw(amount, when)`` means the same thing for both, and the
difference is a method the subclass overrides -- polymorphism, not an ``if``
on a type string.

Standard library only: no SQLAlchemy, no database file, no network.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "bank.json"

#: The stray assignment the legacy files carried on their first line.
LEGACY_HEAD = 'id="q2m4nl"'

#: Every kind of ledger row this bank writes.
KINDS = ("opening", "deposit", "withdrawal", "fee", "interest",
         "transfer_in", "transfer_out")

#: Kinds that move money out of an account.
DEBITS = ("withdrawal", "fee", "transfer_out")

ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


class BankingError(ValueError):
    """A bank rule, a money value or a data file that cannot be accepted."""


class MoneyError(BankingError):
    """A money value that is not an exact number of cents."""


class AccountNotFound(BankingError):
    """No account with that number."""


class AccountClosed(BankingError):
    """The account was closed and accepts no further entries."""


class InsufficientFunds(BankingError):
    """A rule in a subclass says no."""


class DataError(BankingError):
    """A JSON document that does not describe a bank."""


# --------------------------------------------------------------------------- #
# Dates
# --------------------------------------------------------------------------- #
def check_date(value) -> str:
    """A strict ``YYYY-MM-DD`` date, returned unchanged.

    ``date.fromisoformat`` accepts ``2026-3-4``, so the value is rendered back
    and compared: an unpadded month is refused rather than silently widened.
    """
    if not isinstance(value, str):
        raise DataError(f"a date must be text, got {type(value).__name__}")
    if not ISO_DATE.fullmatch(value):
        raise DataError(f"{value!r} is not YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise DataError(f"{value!r} is not a real date: {exc}") from None
    if parsed.isoformat() != value:
        raise DataError(f"{value!r} is not in canonical form")
    return value


def month_of(value: str) -> str:
    """``2026-02-10`` -> ``2026-02``; used for monthly limits."""
    return check_date(value)[:7]


# --------------------------------------------------------------------------- #
# Money
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Money:
    """An exact amount of money, held as integer cents."""

    cents: int

    def __post_init__(self) -> None:
        if isinstance(self.cents, bool) or not isinstance(self.cents, int):
            raise MoneyError(
                f"money is an integer number of cents, got "
                f"{type(self.cents).__name__}; a float would drift")
        if abs(self.cents) > 10 ** 15:
            raise MoneyError("that amount is outside the supported range")

    # -- construction ------------------------------------------------------ #
    @classmethod
    def zero(cls) -> "Money":
        return cls(0)

    @classmethod
    def from_str(cls, text: str) -> "Money":
        """Parse ``12.34``, ``Rs 1,234.56`` or ``-0.05`` exactly."""
        if not isinstance(text, str):
            raise MoneyError("an amount must be text")
        cleaned = text.strip().replace(",", "").replace("_", "")
        for symbol in ("Rs", "rs", "RS", "$", "\u20b9"):
            if cleaned.startswith(symbol):
                cleaned = cleaned[len(symbol):].strip()
                break
        if cleaned.startswith("+"):
            cleaned = cleaned[1:]
        if not cleaned:
            raise MoneyError("the amount is empty")
        try:
            value = Decimal(cleaned)
        except InvalidOperation:
            raise MoneyError(f"{text!r} is not a number") from None
        if not value.is_finite():
            raise MoneyError(f"{text!r} is not a finite number")
        if -value.as_tuple().exponent > 2:
            raise MoneyError(f"{text!r} has more than two decimal places")
        return cls(int((value * 100).to_integral_value()))

    # -- arithmetic -------------------------------------------------------- #
    def __add__(self, other):
        if not isinstance(other, Money):
            return NotImplemented
        return Money(self.cents + other.cents)

    def __sub__(self, other):
        if not isinstance(other, Money):
            return NotImplemented
        return Money(self.cents - other.cents)

    def __neg__(self) -> "Money":
        return Money(-self.cents)

    def __abs__(self) -> "Money":
        return Money(abs(self.cents))

    def __mul__(self, factor):
        if isinstance(factor, bool) or not isinstance(factor, int):
            return NotImplemented
        return Money(self.cents * factor)

    __rmul__ = __mul__

    def __radd__(self, other):
        """``sum([...])`` starts at ``0``, which is the additive identity."""
        if other == 0 and not isinstance(other, Money):
            return self
        if isinstance(other, Money):
            return Money(other.cents + self.cents)
        return NotImplemented

    # -- comparison and display -------------------------------------------- #
    def __lt__(self, other):
        if not isinstance(other, Money):
            return NotImplemented
        return self.cents < other.cents

    def __le__(self, other):
        if not isinstance(other, Money):
            return NotImplemented
        return self.cents <= other.cents

    def __gt__(self, other):
        if not isinstance(other, Money):
            return NotImplemented
        return self.cents > other.cents

    def __ge__(self, other):
        if not isinstance(other, Money):
            return NotImplemented
        return self.cents >= other.cents

    @property
    def is_negative(self) -> bool:
        return self.cents < 0

    @property
    def is_zero(self) -> bool:
        return self.cents == 0

    def format(self) -> str:
        sign = "-" if self.cents < 0 else ""
        whole, fraction = divmod(abs(self.cents), 100)
        return f"{sign}Rs {whole:,}.{fraction:02d}"

    def __str__(self) -> str:
        return self.format()

    def to_json(self) -> int:
        return self.cents


def round_half_up(numerator: int, denominator: int) -> int:
    """Half-up division for non-negative integers, without floats.

    ``round(0.5)`` is ``0`` because Python rounds half to even, which is the
    wrong direction for a till or an interest credit.
    """
    if denominator <= 0:
        raise BankingError("the denominator must be positive")
    if numerator < 0:
        return -(((-numerator) * 2 + denominator) // (2 * denominator))
    return (numerator * 2 + denominator) // (2 * denominator)


def interest_on(amount: Money, basis_points: int) -> Money:
    """``amount * bp / 10000`` rounded half-up to the cent."""
    if isinstance(basis_points, bool) or not isinstance(basis_points, int):
        raise MoneyError("a rate is an integer number of basis points")
    if not 0 <= basis_points <= 100000:
        raise MoneyError("a rate must be between 0 and 100000 basis points")
    raw = amount.cents * basis_points
    sign = -1 if raw < 0 else 1
    return Money(sign * round_half_up(abs(raw), 10000))


# --------------------------------------------------------------------------- #
# Ledger entries
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Transaction:
    """One signed row in an account's ledger."""

    kind: str
    amount: Money
    when: str
    memo: str = ""
    reference: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise DataError(f"{self.kind!r} is not a ledger kind")
        if not isinstance(self.amount, Money):
            raise DataError("a transaction amount must be Money")
        if self.amount.is_zero:
            raise DataError("a transaction of zero says nothing")
        check_date(self.when)
        if not isinstance(self.memo, str):
            raise DataError("a memo must be text")
        if self.reference is not None and not isinstance(self.reference, str):
            raise DataError("a reference must be text or None")
        if self.kind in DEBITS and not self.amount.is_negative:
            raise DataError(f"a {self.kind} must be negative")
        if self.kind in ("deposit", "interest", "transfer_in") \
                and self.amount.is_negative:
            raise DataError(f"a {self.kind} must be positive")

    @property
    def is_credit(self) -> bool:
        return not self.amount.is_negative

    def line(self) -> str:
        return (f"{self.when}  {self.kind:<12} {str(self.amount):>14}  "
                f"{self.memo}")

    def to_dict(self) -> dict:
        payload = {"kind": self.kind, "cents": self.amount.cents,
                   "when": self.when, "memo": self.memo}
        if self.reference is not None:
            payload["reference"] = self.reference
        return payload


def rows_of(account) -> list[Transaction]:
    """The rows of an account that are actually transactions.

    Used by ``Bank.audit`` so that a fabricated object in a ledger fails the
    well-formed check by itself instead of crashing the checks after it.
    """
    return [entry for entry in account.ledger
            if isinstance(entry, Transaction)]


# --------------------------------------------------------------------------- #
# Accounts
# --------------------------------------------------------------------------- #
class Account:
    """An account with an opening balance and an append-only ledger.

    ``withdraw`` is a template method: it validates, asks the subclass
    ``_check_withdrawal``, then lets ``_post_withdrawal`` decide which rows to
    write. The base class supplies both hooks.
    """

    KIND = "basic"

    def __init__(self, number, holder, opened, opening=Money.zero()):
        if not isinstance(number, str) or not number.strip():
            raise DataError("an account number must not be empty")
        if not isinstance(holder, str) or not holder.strip():
            raise DataError("a holder must not be empty")
        if not isinstance(opening, Money):
            raise DataError("an opening balance must be Money")
        if opening.is_negative:
            raise DataError("an opening balance must not be negative")
        self.number = number
        self.holder = holder.strip()
        self.opened = check_date(opened)
        self.opening = opening
        self.closed_on: str | None = None
        self._ledger: list[Transaction] = []

    # -- ledger ------------------------------------------------------------ #
    @property
    def ledger(self) -> tuple[Transaction, ...]:
        return tuple(self._ledger)

    @property
    def balance(self) -> Money:
        """Derived: the opening balance plus every ledger entry."""
        return self.opening + sum((entry.amount for entry in self._ledger),
                                  Money.zero())

    @property
    def is_open(self) -> bool:
        return self.closed_on is None

    def __len__(self) -> int:
        return len(self._ledger)

    def __iter__(self):
        return iter(self._ledger)

    def __contains__(self, reference) -> bool:
        return any(entry.reference == reference for entry in self._ledger)

    def __repr__(self) -> str:
        return (f"<{type(self).__name__} {self.number} {self.holder!r} "
                f"{self.balance.format()}>")

    # -- hooks ------------------------------------------------------------- #
    def _check_deposit(self, amount: Money) -> None:
        if not self.is_open:
            raise AccountClosed(f"{self.number} was closed on {self.closed_on}")
        if amount.is_negative or amount.is_zero:
            raise BankingError("a deposit must be positive")

    def _check_withdrawal(self, amount: Money, when: str) -> None:
        if not self.is_open:
            raise AccountClosed(f"{self.number} was closed on {self.closed_on}")
        if amount.is_negative or amount.is_zero:
            raise BankingError("a withdrawal must be positive")
        if self.balance - amount < Money.zero():
            raise InsufficientFunds(
                f"{self.number} holds {self.balance.format()}, "
                f"cannot withdraw {amount.format()}")

    def _post_withdrawal(self, amount: Money, when: str, memo: str,
                         reference: str | None) -> list[Transaction]:
        return [self._post("withdrawal", -amount, when, memo, reference)]

    # -- operations -------------------------------------------------------- #
    def _post(self, kind, amount, when, memo="", reference=None):
        entry = Transaction(kind=kind, amount=amount, when=when, memo=memo,
                            reference=reference)
        self._ledger.append(entry)
        return entry

    def deposit(self, amount: Money, when: str, memo: str = "") -> Transaction:
        self._check_deposit(amount)
        return self._post("deposit", amount, when, memo)

    def withdraw(self, amount: Money, when: str, memo: str = "",
                 reference: str | None = None) -> list[Transaction]:
        self._check_withdrawal(amount, when)
        return self._post_withdrawal(amount, when, memo, reference)

    def close(self, when: str) -> None:
        if not self.is_open:
            raise AccountClosed(f"{self.number} is already closed")
        if not self.balance.is_zero:
            raise BankingError(
                f"{self.number} still holds {self.balance.format()}; "
                f"a closed account must hold nothing")
        self.closed_on = check_date(when)

    def statement(self) -> list[str]:
        lines = [f"{self.number}  {self.holder}  ({self.KIND})",
                 f"  opened   {self.opened}",
                 f"  opening  {self.opening.format()}"]
        for entry in self._ledger:
            lines.append("  " + entry.line())
        lines.append(f"  balance  {self.balance.format()}")
        if self.closed_on is not None:
            lines.append(f"  closed   {self.closed_on}")
        return lines

    def to_dict(self) -> dict:
        payload = {"number": self.number, "kind": self.KIND,
                   "holder": self.holder, "opened": self.opened,
                   "opening_cents": self.opening.cents,
                   "ledger": [entry.to_dict() for entry in self._ledger]}
        if self.closed_on is not None:
            payload["closed_on"] = self.closed_on
        payload.update(self._params())
        return payload

    def _params(self) -> dict:
        return {}


class SavingsAccount(Account):
    """A minimum balance and a monthly withdrawal limit."""

    KIND = "savings"

    def __init__(self, number, holder, opened, opening=Money.zero(),
                 minimum=None, monthly_withdrawal_limit=3):
        super().__init__(number, holder, opened, opening)
        self.minimum = Money.zero() if minimum is None else minimum
        if not isinstance(self.minimum, Money):
            raise DataError("a minimum balance must be Money")
        if self.minimum.is_negative:
            raise DataError("a minimum balance must not be negative")
        if isinstance(monthly_withdrawal_limit, bool) \
                or not isinstance(monthly_withdrawal_limit, int):
            raise DataError("a monthly limit is a whole number")
        if monthly_withdrawal_limit < 0:
            raise DataError("a monthly limit must not be negative")
        self.monthly_withdrawal_limit = monthly_withdrawal_limit

    def withdrawals_in(self, when: str) -> int:
        """Withdrawals that leave the account in ``when``'s month.

        A transfer out leaves the account exactly like a withdrawal does, so
        it counts; otherwise the monthly limit could be bypassed by sending
        the money to a second account.
        """
        month = month_of(when)
        return sum(1 for entry in self._ledger
                   if entry.kind in ("withdrawal", "transfer_out")
                   and month_of(entry.when) == month)

    def _check_withdrawal(self, amount: Money, when: str) -> None:
        super()._check_withdrawal(amount, when)
        if self.balance - amount < self.minimum:
            raise InsufficientFunds(
                f"{self.number} must keep {self.minimum.format()}; "
                f"{self.balance.format()} - {amount.format()} is below that")
        already = self.withdrawals_in(when)
        if already >= self.monthly_withdrawal_limit:
            raise InsufficientFunds(
                f"{self.number} already has {already} withdrawal(s) in "
                f"{month_of(when)}; the limit is "
                f"{self.monthly_withdrawal_limit}")

    def apply_interest(self, basis_points: int, when: str,
                       memo: str = "interest credit") -> Transaction:
        if not self.is_open:
            raise AccountClosed(f"{self.number} was closed on {self.closed_on}")
        credited = interest_on(self.balance, basis_points)
        if credited.is_zero:
            raise BankingError("that rate credits nothing at this balance")
        return self._post("interest", credited, when, memo)

    def _params(self) -> dict:
        return {"minimum_cents": self.minimum.cents,
                "monthly_withdrawal_limit": self.monthly_withdrawal_limit}


class CurrentAccount(Account):
    """An overdraft limit and a fee for every withdrawal."""

    KIND = "current"

    def __init__(self, number, holder, opened, opening=Money.zero(),
                 overdraft=None, fee=None):
        super().__init__(number, holder, opened, opening)
        self.overdraft = Money.zero() if overdraft is None else overdraft
        self.fee = Money.zero() if fee is None else fee
        for name in ("overdraft", "fee"):
            if not isinstance(getattr(self, name), Money):
                raise DataError(f"an {name} must be Money")
            if getattr(self, name).is_negative:
                raise DataError(f"an {name} must not be negative")

    def _check_withdrawal(self, amount: Money, when: str) -> None:
        if not self.is_open:
            raise AccountClosed(f"{self.number} was closed on {self.closed_on}")
        if amount.is_negative or amount.is_zero:
            raise BankingError("a withdrawal must be positive")
        after = self.balance - amount - self.fee
        if after < -self.overdraft:
            raise InsufficientFunds(
                f"{self.number} can reach -{self.overdraft.format()} with its "
                f"fee; {self.balance.format()} - {amount.format()} - "
                f"{self.fee.format()} is further out")

    def _post_withdrawal(self, amount, when, memo, reference):
        rows = [self._post("withdrawal", -amount, when, memo, reference)]
        if not self.fee.is_zero:
            rows.append(self._post("fee", -self.fee, when,
                                   memo or "withdrawal fee", reference))
        return rows

    def _params(self) -> dict:
        return {"overdraft_cents": self.overdraft.cents,
                "fee_cents": self.fee.cents}


# --------------------------------------------------------------------------- #
# The bank
# --------------------------------------------------------------------------- #
class Bank:
    """A named collection of accounts, and the operations that span two."""

    def __init__(self, name: str = "Ledger Bank"):
        if not isinstance(name, str) or not name.strip():
            raise DataError("the bank needs a name")
        self.name = name.strip()
        self._accounts: dict[str, Account] = {}
        self._sequence = 0

    # -- collection protocol ----------------------------------------------- #
    def __len__(self) -> int:
        return len(self._accounts)

    def __iter__(self):
        return iter(self.accounts)

    def __contains__(self, other) -> bool:
        if isinstance(other, Account):
            return self._accounts.get(other.number) is other
        return other in self._accounts

    def __getitem__(self, number) -> Account:
        return self.get(number)

    def __repr__(self) -> str:
        return f"<Bank {self.name!r} with {len(self)} accounts>"

    @property
    def accounts(self) -> tuple[Account, ...]:
        return tuple(self._accounts[key] for key in sorted(self._accounts))

    @property
    def total(self) -> Money:
        return sum((account.balance for account in self._accounts.values()),
                   Money.zero())

    # -- opening ----------------------------------------------------------- #
    def next_number(self) -> str:
        self._sequence += 1
        return f"AC-{self._sequence:04d}"

    def open(self, kind, holder, opened, opening=Money.zero(), **params):
        builders = {"savings": SavingsAccount, "current": CurrentAccount}
        if kind not in builders:
            raise DataError(f"{kind!r} is not an account kind; "
                            f"choose one of {sorted(builders)}")
        number = self.next_number()
        account = builders[kind](number, holder, opened, opening, **params)
        self._accounts[number] = account
        return account

    def add(self, account: Account) -> Account:
        if not isinstance(account, Account):
            raise DataError("only an Account can be added to a bank")
        if account.number in self._accounts:
            raise DataError(f"{account.number} already exists in this bank")
        self._accounts[account.number] = account
        return account

    def get(self, number) -> Account:
        try:
            return self._accounts[number]
        except KeyError:
            raise AccountNotFound(f"no account {number!r}") from None

    def find(self, text: str) -> list[Account]:
        needle = text.strip().casefold()
        if not needle:
            raise BankingError("a search needs something to look for")
        return [account for account in self.accounts
                if needle in account.number.casefold()
                or needle in account.holder.casefold()]

    # -- moving money ------------------------------------------------------ #
    def transfer(self, source_number, destination_number, amount: Money,
                 when: str, memo: str = "") -> tuple[Transaction, Transaction]:
        """Two ledger rows, or none at all.

        Every rule on both accounts is checked before the first row is
        written, so a refused transfer cannot leave half of itself behind.
        """
        if not isinstance(amount, Money):
            raise DataError("a transfer amount must be Money")
        if amount.is_zero or amount.is_negative:
            raise BankingError("a transfer must be positive")
        check_date(when)
        if source_number == destination_number:
            raise BankingError("a transfer needs two different accounts")
        source = self.get(source_number)
        destination = self.get(destination_number)
        source._check_withdrawal(amount, when)
        destination._check_deposit(amount)
        # validated on both sides first, so the two rows are written together
        reference = f"TR-{self._sequence:04d}-{len(source) + 1:03d}"
        out = source._post("transfer_out", -amount, when, memo, reference)
        try:
            incoming = destination._post("transfer_in", amount, when, memo,
                                         reference)
        except Exception:
            source._ledger.pop()
            raise
        return out, incoming

    def close(self, number, when: str) -> None:
        self.get(number).close(when)

    # -- audit ------------------------------------------------------------- #
    def audit(self) -> list[tuple[str, bool]]:
        """Seven invariants, each reported by name and verdict."""
        checks = []

        numbers = [account.number for account in self.accounts]
        checks.append(("account numbers are unique",
                       len(numbers) == len(set(numbers))))

        well_formed = True
        for account in self.accounts:
            for entry in account.ledger:
                if not isinstance(entry, Transaction):
                    well_formed = False
                    continue
                if not isinstance(entry.amount, Money) or entry.amount.is_zero:
                    well_formed = False
                if entry.kind not in KINDS:
                    well_formed = False
                if entry.kind in DEBITS and entry.amount.cents >= 0:
                    well_formed = False
        checks.append(("every ledger entry is a signed, non-zero amount",
                       well_formed))

        savings_ok = True
        for account in self.accounts:
            if not isinstance(account, SavingsAccount):
                continue
            running = account.opening
            if running < account.minimum:
                savings_ok = False
            for entry in rows_of(account):
                running = running + entry.amount
                if running < account.minimum:
                    savings_ok = False
        checks.append(("savings accounts never fell below their minimum",
                       savings_ok))

        current_ok = True
        for account in self.accounts:
            if not isinstance(account, CurrentAccount):
                continue
            running = account.opening
            for entry in rows_of(account):
                running = running + entry.amount
                if running < -account.overdraft:
                    current_ok = False
        checks.append(("current accounts never passed their overdraft",
                       current_ok))

        pairs: dict[str, int] = {}
        for account in self.accounts:
            for entry in rows_of(account):
                if entry.kind in ("transfer_in", "transfer_out"):
                    pairs[entry.reference] = \
                        pairs.get(entry.reference, 0) + entry.amount.cents
        checks.append(("every transfer balances to zero",
                       all(total == 0 for total in pairs.values())))

        closed_ok = all(account.balance.is_zero
                        for account in self.accounts if not account.is_open)
        checks.append(("closed accounts hold nothing", closed_ok))

        openings_ok = all(not account.opening.is_negative
                          for account in self.accounts)
        checks.append(("no account opens with a negative balance", openings_ok))
        return checks

    def problems(self) -> list[str]:
        return [name for name, passed in self.audit() if not passed]

    # -- persistence ------------------------------------------------------- #
    def to_dict(self) -> dict:
        return {"name": self.name, "sequence": self._sequence,
                "accounts": [account.to_dict() for account in self.accounts]}

    @classmethod
    def from_dict(cls, payload) -> "Bank":
        if not isinstance(payload, dict):
            raise DataError("a bank document must be an object")
        unknown = set(payload) - {"name", "sequence", "accounts"}
        if unknown:
            raise DataError(f"unknown bank keys: {sorted(unknown)}")
        for key in ("name", "accounts"):
            if key not in payload:
                raise DataError(f"the bank document is missing {key!r}")
        bank = cls(payload["name"])
        if not isinstance(payload["accounts"], list):
            raise DataError("'accounts' must be a list")
        for row in payload["accounts"]:
            bank.add(account_from_dict(row))
        sequence = payload.get("sequence", 0)
        if isinstance(sequence, bool) or not isinstance(sequence, int):
            raise DataError("'sequence' must be a whole number")
        if sequence < len(bank):
            raise DataError("'sequence' cannot be smaller than the number "
                            "of accounts")
        bank._sequence = sequence
        return bank


def account_from_dict(row) -> Account:
    """Build one account from a JSON object, refusing anything unknown."""
    if not isinstance(row, dict):
        raise DataError("an account must be an object")
    allowed = {"number", "kind", "holder", "opened", "opening_cents",
               "ledger", "closed_on", "minimum_cents",
               "monthly_withdrawal_limit", "overdraft_cents", "fee_cents"}
    unknown = set(row) - allowed
    if unknown:
        raise DataError(f"unknown account keys: {sorted(unknown)}")
    for key in ("number", "kind", "holder", "opened", "opening_cents"):
        if key not in row:
            raise DataError(f"an account is missing {key!r}")
    opening = row["opening_cents"]
    if isinstance(opening, bool) or not isinstance(opening, int):
        raise DataError("'opening_cents' must be a whole number")
    params: dict = {}
    if row["kind"] == "savings":
        params["minimum"] = Money(row.get("minimum_cents", 0))
        params["monthly_withdrawal_limit"] = row.get(
            "monthly_withdrawal_limit", 3)
    elif row["kind"] == "current":
        params["overdraft"] = Money(row.get("overdraft_cents", 0))
        params["fee"] = Money(row.get("fee_cents", 0))
    builders = {"savings": SavingsAccount, "current": CurrentAccount}
    if row["kind"] not in builders:
        raise DataError(f"{row['kind']!r} is not an account kind")
    account = builders[row["kind"]](row["number"], row["holder"],
                                    row["opened"], Money(opening), **params)
    for entry in row.get("ledger", []):
        if not isinstance(entry, dict):
            raise DataError("a ledger entry must be an object")
        unknown = set(entry) - {"kind", "cents", "when", "memo", "reference"}
        if unknown:
            raise DataError(f"unknown ledger keys: {sorted(unknown)}")
        for key in ("kind", "cents", "when"):
            if key not in entry:
                raise DataError(f"a ledger entry is missing {key!r}")
        account._post(entry["kind"], Money(entry["cents"]), entry["when"],
                      entry.get("memo", ""), entry.get("reference"))
    if row.get("closed_on") is not None:
        account.closed_on = check_date(row["closed_on"])
    return account


def load_bank(path=DATA_FILE) -> Bank:
    path = Path(path)
    if not path.exists():
        raise DataError(f"bank file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DataError(f"{path.name} is not valid JSON: {exc}") from None
    return Bank.from_dict(payload)


def save_bank(path, bank: Bank) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(bank.to_dict(), indent=2, sort_keys=False) + "\n"
    path.write_text(text, encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def _legacy_float_balance(deposits: int) -> tuple[float, int]:
    """The legacy pattern: a float column, incremented row by row."""
    balance = 0.0
    for _ in range(deposits):
        balance += 0.10
    return balance, deposits * 10


def run_demo() -> int:
    print("=" * 74)
    print(" BANKING - a float balance, a stray 'id', and a ledger that adds up")
    print("=" * 74)

    # 1. the legacy float column drifts, integer cents do not
    drifted, exact = _legacy_float_balance(10)
    assert drifted != 1.0
    assert f"{drifted:.17g}" == "0.99999999999999989", f"{drifted:.17g}"
    assert exact == 100 and Money(exact).format() == "Rs 1.00"
    print(f"  10 deposits of 0.10 in a float column: {drifted:.17g}")
    print(f"  the same ten deposits in cents:        {exact} cents "
          f"= {Money(exact).format()}")

    # 2. the stray assignment shadows the builtin
    namespace: dict = {}
    exec(LEGACY_HEAD, namespace)                       # noqa: S102
    assert namespace["id"] == "q2m4nl"
    try:
        namespace["id"](object())
    except TypeError as exc:
        shadow = str(exc)
    else:
        raise AssertionError("the shadowed id was callable")
    assert "not callable" in shadow
    assert callable(id) and id(object()) > 0
    print(f"  {LEGACY_HEAD} rebinds 'id' -> calling it raises "
          f"TypeError: {shadow}")

    # 3. Money is exact, frozen and ordered
    assert Money.from_str("Rs 1,234.56") == Money(123456)
    assert Money.from_str("-0.05") == Money(-5)
    assert sum([Money(100), Money(250), Money(-50)]) == Money(300)
    assert sorted([Money(250), Money(100)])[0] == Money(100)
    refused = 0
    for bad in (0.1, "1.234", "abc", "", True):
        try:
            Money.from_str(bad) if isinstance(bad, str) else Money(bad)
        except MoneyError:
            refused += 1
        else:
            raise AssertionError(f"{bad!r} should have been refused")
    try:
        Money(100).cents = 200
    except Exception:
        frozen = True
    else:
        frozen = False
    assert frozen
    print(f"  Money: exact cents, ordered, hashable, frozen; "
          f"{refused} bad values refused (0.1, '1.234', 'abc', '', True)")

    # 4. the balance is derived, so it cannot go stale
    account = SavingsAccount("AC-9001", "Test Holder", "2026-01-01",
                             Money(50000), minimum=Money(10000))
    assert account.balance == Money(50000)
    try:
        account.balance = Money(999999)                # type: ignore[misc]
    except AttributeError:
        read_only = True
    else:
        read_only = False
    assert read_only
    account.deposit(Money(2500), "2026-01-02", "cash")
    assert account.balance == Money(52500)
    before = account.balance
    account._ledger.pop()
    assert account.balance == before - Money(2500)
    account._ledger.append(Transaction("deposit", Money(2500), "2026-01-02",
                                       "cash"))
    assert account.balance == before
    print(f"  balance is a read-only property: after a 25.00 deposit "
          f"{before.format()}; removing the row takes it back, "
          f"re-adding it restores it")

    # 5. one call, three rules: polymorphism through the hooks
    savings = SavingsAccount("AC-9002", "Savings", "2026-01-01",
                             Money(120000), minimum=Money(50000),
                             monthly_withdrawal_limit=2)
    current = CurrentAccount("AC-9003", "Current", "2026-01-01",
                             Money(10000), overdraft=Money(50000),
                             fee=Money(2500))
    savings.withdraw(Money(60000), "2026-02-03", "rent")
    assert savings.balance == Money(60000)
    refused_below_minimum = 0
    try:
        savings.withdraw(Money(20000), "2026-02-04", "more rent")
    except InsufficientFunds:
        refused_below_minimum = 1
    assert refused_below_minimum == 1
    assert savings.balance == Money(60000)
    savings.withdraw(Money(5000), "2026-02-05", "second")
    try:
        savings.withdraw(Money(1000), "2026-02-06", "third")
    except InsufficientFunds as exc:
        limit_message = str(exc)
    else:
        raise AssertionError("the monthly limit was not enforced")
    assert "limit is 2" in limit_message
    assert savings.withdrawals_in("2026-02-20") == 2
    assert savings.withdrawals_in("2026-03-01") == 0
    rows = current.withdraw(Money(50000), "2026-02-07", "supplier")
    assert len(rows) == 2
    assert current.balance == Money(-42500)
    try:
        current.withdraw(Money(10000), "2026-02-08", "more supplier")
    except InsufficientFunds:
        overdraft_refused = True
    else:
        overdraft_refused = False
    assert overdraft_refused and current.balance == Money(-42500)
    print(f"  withdraw() on savings: refused below the 500.00 minimum, "
          f"and at the 2/month limit")
    print(f"  withdraw() on current: allowed to -{current.overdraft.format()}, "
          f"posts {len(rows)} rows (withdrawal + fee), now "
          f"{current.balance.format()}")

    # 6. a refused transfer leaves both ledgers untouched
    bank = Bank("Demo Bank")
    left = bank.open("savings", "Asha Rao", "2026-01-05", Money(120000),
                     minimum=Money(50000), monthly_withdrawal_limit=3)
    right = bank.open("current", "Bilal Khan", "2026-01-12", Money(10000),
                      overdraft=Money(0), fee=Money(0))
    before = (left.ledger, right.ledger, left.balance, right.balance)
    for amount in (Money(80000), Money(0), Money(-100)):
        try:
            bank.transfer(left.number, right.number, amount, "2026-02-01")
        except BankingError:
            pass
        else:
            raise AssertionError(f"{amount} should have been refused")
    assert (left.ledger, right.ledger, left.balance, right.balance) == before
    out, incoming = bank.transfer(left.number, right.number, Money(25000),
                                  "2026-02-02", "invoice 41")
    assert out.amount == Money(-25000) and incoming.amount == Money(25000)
    assert out.reference == incoming.reference
    assert left.balance == Money(95000) and right.balance == Money(35000)
    assert bank.total == left.balance + right.balance
    print(f"  transfer refused 3 times (below minimum, zero, negative) and "
          f"both ledgers were unchanged")
    print(f"  transfer of 250.00: rows {out.amount.format()} / "
          f"{incoming.amount.format()}, reference {out.reference}, "
          f"bank total {bank.total.format()}")

    # 7. interest is rounded half-up, not half-even
    assert interest_on(Money(100000), 350) == Money(3500)
    assert interest_on(Money(25), 350) == Money(1)          # 0.875 -> 1
    assert round(0.5) == 0 and round_half_up(1, 2) == 1
    credited = left.apply_interest(350, "2026-02-28")
    assert credited.amount == Money(3325)                   # 3.5% of 95000
    print(f"  3.5% of 1000.00 = {Money(3500).format()}, of 0.25 = "
          f"{Money(1).format()} (round() would give 0), "
          f"credited {credited.amount.format()} on {left.balance.format()}")

    # 8. the audit names what it checked, and fails when a rule is broken
    checks = bank.audit()
    assert len(checks) == 7
    assert all(passed for _, passed in checks), bank.problems()
    names = [name for name, _ in checks]
    broken = Bank.from_dict(bank.to_dict())
    broken.get(left.number)._ledger.append(
        Transaction("withdrawal", Money(-100000), "2026-02-03", "fabricated"))
    failed = [name for name, passed in broken.audit() if not passed]
    assert failed == ["savings accounts never fell below their minimum"], failed
    print(f"  audit: {len(checks)} checks, all passing; a fabricated "
          f"withdrawal makes exactly 1 fail ({failed[0]})")

    # 9. two closed accounts, and the rule that stops a wrong one
    empty = bank.open("savings", "Chen Wei", "2026-01-20", Money(0),
                      minimum=Money(0), monthly_withdrawal_limit=1)
    empty.close("2026-02-28")
    assert not empty.is_open and empty in bank
    try:
        left.close("2026-02-28")
    except BankingError as exc:
        closing_message = str(exc)
    else:
        raise AssertionError("a funded account was closed")
    assert "still holds" in closing_message
    print(f"  an empty account closes; a funded one is refused: "
          f"{closing_message}")

    # 10. the bundled file round-trips
    seeded = load_bank()
    assert len(seeded) == 4
    assert all(passed for _, passed in seeded.audit()), seeded.problems()
    assert seeded.total == Money(220000)
    import tempfile
    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder) / "copy.json"
        save_bank(target, seeded)
        first = target.read_bytes()
        save_bank(target, load_bank(target))
        assert target.read_bytes() == first
        assert load_bank(target).to_dict() == seeded.to_dict()
        assert [path.name for path in Path(folder).iterdir()] == ["copy.json"]
    print(f"  seeded file: {len(seeded)} accounts totalling "
          f"{seeded.total.format()}, all 7 checks pass, saved and reloaded "
          f"byte for byte")

    print()
    print("Cross-checks OK: ten float deposits drifted to 0.99999999999999989 "
          "while 100 cents stayed exact, the stray 'id' assignment rebinds the "
          "builtin and made it uncallable, 5 bad Money values refused and a "
          "frozen Money refused assignment, the balance was read-only and "
          "tracked the ledger row by row, savings refused a withdrawal below "
          "its minimum and a third in one month while current reached "
          "-42500 with a fee row beside it, 3 refused transfers left both "
          "ledgers identical, a 25000 transfer balanced to zero with a shared "
          "reference, 3.5% rounded half-up at 0.875 cents, 7 audit checks "
          "passed and a fabricated row failed exactly one of them, a funded "
          "account refused to close, and 4 seeded accounts round-tripped "
          "byte for byte")
    print("Demo completed successfully.")
    return 0
