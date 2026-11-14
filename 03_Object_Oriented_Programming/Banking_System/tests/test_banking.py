"""Tests for Banking_System: money, the ledger, the hooks, the bank, the CLI."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import main as cli                                        # noqa: E402
from banking import (                                     # noqa: E402
    DATA_FILE,
    KINDS,
    LEGACY_HEAD,
    Account,
    AccountClosed,
    AccountNotFound,
    Bank,
    BankingError,
    CurrentAccount,
    DataError,
    InsufficientFunds,
    Money,
    MoneyError,
    SavingsAccount,
    Transaction,
    account_from_dict,
    check_date,
    interest_on,
    load_bank,
    month_of,
    round_half_up,
    run_demo,
    save_bank,
)


# --------------------------------------------------------------------------- #
# Money construction
# --------------------------------------------------------------------------- #
def test_money_holds_cents():
    assert Money(1250).cents == 1250


def test_money_zero():
    assert Money.zero() == Money(0)


@pytest.mark.parametrize("bad", [0.1, 1.5, "100", None, [1], (1,)])
def test_money_refuses_a_non_integer(bad):
    with pytest.raises(MoneyError, match="integer number of cents"):
        Money(bad)


def test_money_refuses_a_boolean():
    with pytest.raises(MoneyError, match="integer number of cents"):
        Money(True)


def test_money_refuses_an_absurd_amount():
    with pytest.raises(MoneyError, match="outside the supported range"):
        Money(10 ** 16)


def test_money_is_frozen():
    with pytest.raises(Exception):
        Money(100).cents = 200                            # type: ignore[misc]


def test_money_is_hashable():
    assert len({Money(100), Money(100), Money(200)}) == 2


# --------------------------------------------------------------------------- #
# Money parsing
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("text,cents", [
    ("12.34", 1234),
    ("12.3", 1230),
    ("12", 1200),
    ("0.05", 5),
    ("-0.05", -5),
    ("Rs 1,234.56", 123456),
    ("$5.00", 500),
    ("\u20b9 7.25", 725),
    ("  9.99  ", 999),
    ("+1.00", 100),
])
def test_money_from_str(text, cents):
    assert Money.from_str(text) == Money(cents)


@pytest.mark.parametrize("bad", ["1.234", "0.001", "abc", "", "  ", "nan",
                                 "inf", "--5", "1..2"])
def test_money_from_str_refuses_bad_shapes(bad):
    with pytest.raises(MoneyError):
        Money.from_str(bad)


def test_money_from_str_refuses_non_text():
    with pytest.raises(MoneyError, match="must be text"):
        Money.from_str(1234)


# --------------------------------------------------------------------------- #
# Money arithmetic
# --------------------------------------------------------------------------- #
def test_money_adds():
    assert Money(100) + Money(250) == Money(350)


def test_money_subtracts():
    assert Money(100) - Money(250) == Money(-150)


def test_money_negates():
    assert -Money(100) == Money(-100)


def test_money_absolute():
    assert abs(Money(-100)) == Money(100)


def test_money_multiplies_by_an_integer():
    assert Money(250) * 3 == Money(750)


def test_money_multiplies_from_the_left():
    assert 3 * Money(250) == Money(750)


def test_money_refuses_multiplying_by_a_float():
    with pytest.raises(TypeError):
        Money(250) * 1.5


def test_money_refuses_adding_an_integer():
    with pytest.raises(TypeError):
        Money(250) + 100


def test_money_sums_with_sum():
    assert sum([Money(100), Money(250), Money(-50)]) == Money(300)


def test_money_sum_of_nothing_is_an_int():
    assert sum([]) == 0


def test_money_orders():
    assert Money(100) < Money(200)
    assert Money(200) > Money(100)
    assert Money(100) <= Money(100)
    assert Money(100) >= Money(100)


def test_money_refuses_comparing_with_an_integer():
    with pytest.raises(TypeError):
        Money(100) < 200


def test_money_sorts():
    assert sorted([Money(300), Money(100), Money(200)]) == \
        [Money(100), Money(200), Money(300)]


def test_money_reports_its_sign():
    assert Money(-1).is_negative and not Money(1).is_negative
    assert Money(0).is_zero and not Money(1).is_zero


# --------------------------------------------------------------------------- #
# Money display
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("cents,text", [
    (0, "Rs 0.00"),
    (5, "Rs 0.05"),
    (100, "Rs 1.00"),
    (123456, "Rs 1,234.56"),
    (-5, "-Rs 0.05"),
    (-123456, "-Rs 1,234.56"),
])
def test_money_format(cents, text):
    assert Money(cents).format() == text


def test_money_str_is_its_format():
    assert str(Money(1250)) == Money(1250).format()


def test_money_to_json_is_cents():
    assert Money(1250).to_json() == 1250


# --------------------------------------------------------------------------- #
# Rounding
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("numerator,denominator,expected", [
    (1, 2, 1),
    (3, 2, 2),
    (0, 5, 0),
    (5, 10, 1),
    (4, 10, 0),
    (875, 10000, 0),
])
def test_round_half_up(numerator, denominator, expected):
    assert round_half_up(numerator, denominator) == expected


def test_round_half_up_of_a_negative():
    assert round_half_up(-1, 2) == -1


def test_round_half_up_refuses_a_zero_denominator():
    with pytest.raises(BankingError, match="denominator"):
        round_half_up(1, 0)


def test_round_is_not_round_half_up():
    assert round(0.5) == 0
    assert round_half_up(1, 2) == 1


def test_interest_on_ten_percent():
    assert interest_on(Money(100000), 1000) == Money(10000)


def test_interest_on_three_and_a_half_percent():
    assert interest_on(Money(100000), 350) == Money(3500)


def test_interest_on_a_half_cent_rounds_up():
    assert interest_on(Money(25), 350) == Money(1)


def test_interest_on_less_than_half_a_cent_rounds_down():
    assert interest_on(Money(14), 350) == Money(0)


def test_interest_on_zero_is_zero():
    assert interest_on(Money(0), 350) == Money(0)


def test_interest_on_a_negative_balance():
    assert interest_on(Money(-100000), 350) == Money(-3500)


def test_interest_refuses_a_non_integer_rate():
    with pytest.raises(MoneyError, match="basis points"):
        interest_on(Money(100), 3.5)


def test_interest_refuses_a_negative_rate():
    with pytest.raises(MoneyError, match="basis points"):
        interest_on(Money(100), -1)


def test_interest_refuses_a_rate_above_one_hundred_percent():
    with pytest.raises(MoneyError, match="basis points"):
        interest_on(Money(100), 100001)


# --------------------------------------------------------------------------- #
# Dates
# --------------------------------------------------------------------------- #
def test_check_date_accepts_iso():
    assert check_date("2026-02-28") == "2026-02-28"


@pytest.mark.parametrize("bad", ["2026-2-28", "2026-02-30", "2026/02/28",
                                 "28-02-2026", "2026-02", "20260228", ""])
def test_check_date_refuses_non_canonical_dates(bad):
    with pytest.raises(DataError):
        check_date(bad)


def test_check_date_refuses_non_text():
    with pytest.raises(DataError, match="must be text"):
        check_date(20260228)


def test_month_of():
    assert month_of("2026-02-10") == "2026-02"


def test_month_of_refuses_a_bad_date():
    with pytest.raises(DataError):
        month_of("2026-13-01")


# --------------------------------------------------------------------------- #
# Transactions
# --------------------------------------------------------------------------- #
def test_a_deposit_transaction_is_positive():
    entry = Transaction("deposit", Money(2500), "2026-02-01", "cash")
    assert entry.is_credit and entry.amount == Money(2500)


def test_a_withdrawal_transaction_is_negative():
    entry = Transaction("withdrawal", Money(-2500), "2026-02-01")
    assert not entry.is_credit


@pytest.mark.parametrize("kind,sign", [("withdrawal", 1), ("fee", 1),
                                       ("transfer_out", 1),
                                       ("deposit", -1),
                                       ("interest", -1),
                                       ("transfer_in", -1)])
def test_a_debit_must_be_negative_and_a_credit_positive(kind, sign):
    with pytest.raises(DataError, match="must be"):
        Transaction(kind, Money(100 * sign), "2026-02-01")


def test_a_transaction_refuses_an_unknown_kind():
    with pytest.raises(DataError, match="ledger kind"):
        Transaction("gift", Money(100), "2026-02-01")


def test_a_transaction_refuses_zero():
    with pytest.raises(DataError, match="says nothing"):
        Transaction("deposit", Money(0), "2026-02-01")


def test_a_transaction_refuses_a_non_money_amount():
    with pytest.raises(DataError, match="must be Money"):
        Transaction("deposit", 100, "2026-02-01")


def test_a_transaction_refuses_a_bad_date():
    with pytest.raises(DataError):
        Transaction("deposit", Money(100), "2026-2-1")


def test_a_transaction_refuses_a_non_text_memo():
    with pytest.raises(DataError, match="memo"):
        Transaction("deposit", Money(100), "2026-02-01", 7)


def test_a_transaction_refuses_a_non_text_reference():
    with pytest.raises(DataError, match="reference"):
        Transaction("deposit", Money(100), "2026-02-01", "m", 7)


def test_a_transaction_line_mentions_kind_and_amount():
    entry = Transaction("deposit", Money(2500), "2026-02-01", "cash")
    line = entry.line()
    assert "deposit" in line and "Rs 25.00" in line and "2026-02-01" in line


def test_a_transaction_dict_omits_an_absent_reference():
    entry = Transaction("deposit", Money(2500), "2026-02-01")
    assert "reference" not in entry.to_dict()


def test_a_transaction_dict_keeps_a_reference():
    entry = Transaction("transfer_in", Money(2500), "2026-02-01", "x", "TR-1")
    assert entry.to_dict()["reference"] == "TR-1"


# --------------------------------------------------------------------------- #
# The base account
# --------------------------------------------------------------------------- #
def test_a_new_account_holds_its_opening_balance():
    account = Account("AC-1000", "Test", "2026-01-01", Money(5000))
    assert account.balance == Money(5000)
    assert len(account) == 0


def test_an_account_refuses_an_empty_number():
    with pytest.raises(DataError, match="account number"):
        Account("  ", "Test", "2026-01-01")


def test_an_account_refuses_an_empty_holder():
    with pytest.raises(DataError, match="holder"):
        Account("AC-1", "   ", "2026-01-01")


def test_an_account_refuses_a_negative_opening_balance():
    with pytest.raises(DataError, match="must not be negative"):
        Account("AC-1", "Test", "2026-01-01", Money(-1))


def test_an_account_refuses_a_non_money_opening():
    with pytest.raises(DataError, match="must be Money"):
        Account("AC-1", "Test", "2026-01-01", 5000)


def test_an_account_trims_its_holder():
    assert Account("AC-1", "  Test  ", "2026-01-01").holder == "Test"


def test_an_account_deposit_returns_the_entry():
    account = Account("AC-1", "Test", "2026-01-01", Money(100))
    entry = account.deposit(Money(250), "2026-01-02", "cash")
    assert entry.kind == "deposit" and entry.amount == Money(250)


def test_an_account_deposit_moves_the_balance():
    account = Account("AC-1", "Test", "2026-01-01", Money(100))
    account.deposit(Money(250), "2026-01-02")
    assert account.balance == Money(350)


def test_an_account_refuses_a_zero_deposit():
    account = Account("AC-1", "Test", "2026-01-01", Money(100))
    with pytest.raises(BankingError, match="deposit must be positive"):
        account.deposit(Money(0), "2026-01-02")


def test_an_account_refuses_a_negative_deposit():
    account = Account("AC-1", "Test", "2026-01-01", Money(100))
    with pytest.raises(BankingError, match="deposit must be positive"):
        account.deposit(Money(-5), "2026-01-02")


def test_an_account_withdrawal_returns_one_row():
    account = Account("AC-1", "Test", "2026-01-01", Money(1000))
    rows = account.withdraw(Money(400), "2026-01-02")
    assert len(rows) == 1 and rows[0].amount == Money(-400)
    assert account.balance == Money(600)


def test_an_account_refuses_to_overdraw():
    account = Account("AC-1", "Test", "2026-01-01", Money(1000))
    with pytest.raises(InsufficientFunds, match="cannot withdraw"):
        account.withdraw(Money(1001), "2026-01-02")
    assert account.balance == Money(1000) and len(account) == 0


def test_an_account_refuses_a_zero_withdrawal():
    account = Account("AC-1", "Test", "2026-01-01", Money(1000))
    with pytest.raises(BankingError, match="withdrawal must be positive"):
        account.withdraw(Money(0), "2026-01-02")


def test_the_balance_property_is_read_only():
    account = Account("AC-1", "Test", "2026-01-01", Money(1000))
    with pytest.raises(AttributeError):
        account.balance = Money(1)                        # type: ignore[misc]


def test_the_balance_follows_the_ledger():
    account = Account("AC-1", "Test", "2026-01-01", Money(1000))
    account.deposit(Money(500), "2026-01-02")
    assert account.balance == Money(1500)
    account._ledger.pop()
    assert account.balance == Money(1000)


def test_an_account_is_iterable_over_its_ledger():
    account = Account("AC-1", "Test", "2026-01-01", Money(1000))
    account.deposit(Money(500), "2026-01-02")
    assert [entry.kind for entry in account] == ["deposit"]


def test_an_account_contains_a_reference():
    account = Account("AC-1", "Test", "2026-01-01", Money(1000))
    account.withdraw(Money(100), "2026-01-02", "", "TR-9")
    assert "TR-9" in account and "TR-8" not in account


def test_an_account_closes_at_zero():
    account = Account("AC-1", "Test", "2026-01-01", Money(0))
    account.close("2026-01-02")
    assert not account.is_open and account.closed_on == "2026-01-02"


def test_an_account_refuses_to_close_with_money_in_it():
    account = Account("AC-1", "Test", "2026-01-01", Money(100))
    with pytest.raises(BankingError, match="still holds"):
        account.close("2026-01-02")


def test_an_account_refuses_to_close_twice():
    account = Account("AC-1", "Test", "2026-01-01", Money(0))
    account.close("2026-01-02")
    with pytest.raises(AccountClosed, match="already closed"):
        account.close("2026-01-03")


def test_a_closed_account_refuses_a_deposit():
    account = Account("AC-1", "Test", "2026-01-01", Money(0))
    account.close("2026-01-02")
    with pytest.raises(AccountClosed):
        account.deposit(Money(100), "2026-01-03")


def test_a_closed_account_refuses_a_withdrawal():
    account = Account("AC-1", "Test", "2026-01-01", Money(0))
    account.close("2026-01-02")
    with pytest.raises(AccountClosed):
        account.withdraw(Money(100), "2026-01-03")


def test_an_account_statement_lists_the_ledger():
    account = Account("AC-1", "Test", "2026-01-01", Money(1000))
    account.deposit(Money(500), "2026-01-02", "cash")
    lines = account.statement()
    assert lines[0].startswith("AC-1")
    assert any("deposit" in line for line in lines)
    assert lines[-1].strip().startswith("balance")


def test_an_account_repr_names_it():
    account = Account("AC-1", "Test", "2026-01-01", Money(1000))
    assert "AC-1" in repr(account) and "Rs 10.00" in repr(account)


# --------------------------------------------------------------------------- #
# Savings
# --------------------------------------------------------------------------- #
def test_a_savings_account_defaults_are_permissive():
    account = SavingsAccount("AC-1", "Test", "2026-01-01", Money(100))
    assert account.minimum == Money(0)
    assert account.monthly_withdrawal_limit == 3


def test_a_savings_account_refuses_a_negative_minimum():
    with pytest.raises(DataError, match="must not be negative"):
        SavingsAccount("AC-1", "Test", "2026-01-01", Money(100),
                       minimum=Money(-1))


def test_a_savings_account_refuses_a_non_money_minimum():
    with pytest.raises(DataError, match="must be Money"):
        SavingsAccount("AC-1", "Test", "2026-01-01", Money(100), minimum=100)


def test_a_savings_account_refuses_a_non_integer_limit():
    with pytest.raises(DataError, match="whole number"):
        SavingsAccount("AC-1", "Test", "2026-01-01", Money(100),
                       monthly_withdrawal_limit=2.0)


def test_a_savings_account_refuses_a_boolean_limit():
    with pytest.raises(DataError, match="whole number"):
        SavingsAccount("AC-1", "Test", "2026-01-01", Money(100),
                       monthly_withdrawal_limit=True)


def test_a_savings_account_refuses_a_negative_limit():
    with pytest.raises(DataError, match="must not be negative"):
        SavingsAccount("AC-1", "Test", "2026-01-01", Money(100),
                       monthly_withdrawal_limit=-1)


def test_a_savings_account_refuses_to_dip_below_its_minimum():
    account = SavingsAccount("AC-1", "Test", "2026-01-01", Money(10000),
                             minimum=Money(5000))
    with pytest.raises(InsufficientFunds, match="must keep"):
        account.withdraw(Money(6000), "2026-01-02")
    assert account.balance == Money(10000)


def test_a_savings_account_allows_a_withdrawal_down_to_the_minimum():
    account = SavingsAccount("AC-1", "Test", "2026-01-01", Money(10000),
                             minimum=Money(5000))
    account.withdraw(Money(5000), "2026-01-02")
    assert account.balance == Money(5000)


def test_a_savings_account_allows_its_monthly_limit():
    account = SavingsAccount("AC-1", "Test", "2026-01-01", Money(10000),
                             monthly_withdrawal_limit=2)
    account.withdraw(Money(100), "2026-01-02")
    account.withdraw(Money(100), "2026-01-03")
    assert account.withdrawals_in("2026-01-20") == 2


def test_a_savings_account_refuses_one_past_its_limit():
    account = SavingsAccount("AC-1", "Test", "2026-01-01", Money(10000),
                             monthly_withdrawal_limit=2)
    account.withdraw(Money(100), "2026-01-02")
    account.withdraw(Money(100), "2026-01-03")
    with pytest.raises(InsufficientFunds, match="limit is 2"):
        account.withdraw(Money(100), "2026-01-04")
    assert account.balance == Money(9800)


def test_a_savings_account_limit_resets_in_a_new_month():
    account = SavingsAccount("AC-1", "Test", "2026-01-01", Money(10000),
                             monthly_withdrawal_limit=1)
    account.withdraw(Money(100), "2026-01-02")
    account.withdraw(Money(100), "2026-02-01")
    assert account.withdrawals_in("2026-01-31") == 1
    assert account.withdrawals_in("2026-02-28") == 1


def test_a_savings_account_zero_limit_refuses_everything():
    account = SavingsAccount("AC-1", "Test", "2026-01-01", Money(10000),
                             monthly_withdrawal_limit=0)
    with pytest.raises(InsufficientFunds, match="limit is 0"):
        account.withdraw(Money(1), "2026-01-02")


def test_withdrawals_in_counts_only_withdrawals():
    account = SavingsAccount("AC-1", "Test", "2026-01-01", Money(10000),
                             minimum=Money(0), monthly_withdrawal_limit=5)
    account.deposit(Money(100), "2026-01-02")
    account.withdraw(Money(100), "2026-01-03")
    assert account.withdrawals_in("2026-01-31") == 1


def test_savings_interest_is_credited():
    account = SavingsAccount("AC-1", "Test", "2026-01-01", Money(100000))
    entry = account.apply_interest(350, "2026-01-31")
    assert entry.amount == Money(3500)
    assert account.balance == Money(103500)


def test_savings_interest_refuses_a_zero_credit():
    account = SavingsAccount("AC-1", "Test", "2026-01-01", Money(1))
    with pytest.raises(BankingError, match="credits nothing"):
        account.apply_interest(350, "2026-01-31")


def test_savings_interest_refuses_a_closed_account():
    account = SavingsAccount("AC-1", "Test", "2026-01-01", Money(0))
    account.close("2026-01-31")
    with pytest.raises(AccountClosed):
        account.apply_interest(350, "2026-01-31")


def test_savings_dict_records_its_rules():
    account = SavingsAccount("AC-1", "Test", "2026-01-01", Money(100),
                             minimum=Money(50), monthly_withdrawal_limit=2)
    payload = account.to_dict()
    assert payload["kind"] == "savings"
    assert payload["minimum_cents"] == 50
    assert payload["monthly_withdrawal_limit"] == 2
    assert payload["opening_cents"] == 100


# --------------------------------------------------------------------------- #
# Current
# --------------------------------------------------------------------------- #
def test_a_current_account_defaults_are_strict():
    account = CurrentAccount("AC-1", "Test", "2026-01-01", Money(100))
    assert account.overdraft == Money(0) and account.fee == Money(0)


def test_a_current_account_refuses_a_negative_overdraft():
    with pytest.raises(DataError, match="must not be negative"):
        CurrentAccount("AC-1", "T", "2026-01-01", Money(0),
                       overdraft=Money(-1))


def test_a_current_account_refuses_a_non_money_fee():
    with pytest.raises(DataError, match="must be Money"):
        CurrentAccount("AC-1", "T", "2026-01-01", Money(0), fee=250)


def test_a_current_account_refuses_a_negative_fee():
    with pytest.raises(DataError, match="must not be negative"):
        CurrentAccount("AC-1", "T", "2026-01-01", Money(0), fee=Money(-1))


def test_a_current_account_withdraws_into_its_overdraft():
    account = CurrentAccount("AC-1", "Test", "2026-01-01", Money(1000),
                             overdraft=Money(5000))
    account.withdraw(Money(5000), "2026-01-02")
    assert account.balance == Money(-4000)


def test_a_current_account_refuses_past_its_overdraft():
    account = CurrentAccount("AC-1", "Test", "2026-01-01", Money(1000),
                             overdraft=Money(5000))
    with pytest.raises(InsufficientFunds, match="can reach"):
        account.withdraw(Money(6001), "2026-01-02")


def test_a_current_account_posts_two_rows_with_a_fee():
    account = CurrentAccount("AC-1", "Test", "2026-01-01", Money(10000),
                             overdraft=Money(50000), fee=Money(2500))
    rows = account.withdraw(Money(5000), "2026-01-02")
    assert [row.kind for row in rows] == ["withdrawal", "fee"]
    assert account.balance == Money(2500)


def test_a_current_account_fee_is_part_of_the_check():
    account = CurrentAccount("AC-1", "Test", "2026-01-01", Money(0),
                             overdraft=Money(5000), fee=Money(2500))
    with pytest.raises(InsufficientFunds):
        account.withdraw(Money(3000), "2026-01-02")
    account.withdraw(Money(2500), "2026-01-02")
    assert account.balance == Money(-5000)


def test_a_current_account_without_a_fee_posts_one_row():
    account = CurrentAccount("AC-1", "Test", "2026-01-01", Money(10000),
                             overdraft=Money(5000))
    assert len(account.withdraw(Money(1000), "2026-01-02")) == 1


def test_a_current_dict_records_its_rules():
    account = CurrentAccount("AC-1", "Test", "2026-01-01", Money(100),
                             overdraft=Money(500), fee=Money(25))
    payload = account.to_dict()
    assert payload["kind"] == "current"
    assert payload["overdraft_cents"] == 500
    assert payload["fee_cents"] == 25


# --------------------------------------------------------------------------- #
# The bank
# --------------------------------------------------------------------------- #
def test_a_new_bank_is_empty():
    bank = Bank("Test Bank")
    assert len(bank) == 0 and bank.total == Money(0)
    assert bank.accounts == ()


def test_a_bank_needs_a_name():
    with pytest.raises(DataError, match="needs a name"):
        Bank("   ")


def test_opening_an_account_numbers_it():
    bank = Bank()
    assert bank.open("savings", "A", "2026-01-01").number == "AC-0001"
    assert bank.open("current", "B", "2026-01-01").number == "AC-0002"


def test_opening_an_account_stores_it():
    bank = Bank()
    account = bank.open("savings", "A", "2026-01-01", Money(100))
    assert len(bank) == 1 and bank.get(account.number) is account


def test_a_bank_refuses_an_unknown_kind():
    with pytest.raises(DataError, match="not an account kind"):
        Bank().open("chequing", "A", "2026-01-01")


def test_a_bank_get_refuses_an_unknown_number():
    with pytest.raises(AccountNotFound, match="AC-9999"):
        Bank().get("AC-9999")


def test_a_bank_indexes_by_number():
    bank = Bank()
    account = bank.open("savings", "A", "2026-01-01")
    assert bank[account.number] is account


def test_a_bank_contains_numbers_and_accounts():
    bank = Bank()
    account = bank.open("savings", "A", "2026-01-01")
    assert account.number in bank and account in bank
    assert "AC-9999" not in bank


def test_a_bank_iterates_in_number_order():
    bank = Bank()
    bank.open("savings", "A", "2026-01-01")
    bank.open("savings", "B", "2026-01-01")
    assert [account.number for account in bank] == ["AC-0001", "AC-0002"]


def test_a_bank_add_refuses_a_duplicate_number():
    bank = Bank()
    account = bank.open("savings", "A", "2026-01-01")
    with pytest.raises(DataError, match="already exists"):
        bank.add(account)


def test_a_bank_add_refuses_a_non_account():
    with pytest.raises(DataError, match="only an Account"):
        Bank().add({"number": "AC-0001"})


def test_a_bank_total_sums_the_balances():
    bank = Bank()
    bank.open("savings", "A", "2026-01-01", Money(1000))
    bank.open("current", "B", "2026-01-01", Money(2500))
    assert bank.total == Money(3500)


def test_a_bank_finds_by_number():
    bank = Bank()
    account = bank.open("savings", "Asha Rao", "2026-01-01")
    assert bank.find("0001") == [account]


def test_a_bank_finds_by_holder_case_insensitively():
    bank = Bank()
    account = bank.open("savings", "Asha Rao", "2026-01-01")
    assert bank.find("asha") == [account]


def test_a_bank_find_returns_nothing_for_no_match():
    assert Bank().find("nothing") == []


def test_a_bank_find_refuses_a_blank_needle():
    with pytest.raises(BankingError, match="needs something"):
        Bank().find("  ")


def test_a_bank_repr_names_it():
    bank = Bank("Ledger")
    assert "Ledger" in repr(bank) and "0" in repr(bank)


# --------------------------------------------------------------------------- #
# Transfers
# --------------------------------------------------------------------------- #
def test_a_transfer_writes_two_balanced_rows():
    bank = Bank()
    left = bank.open("savings", "A", "2026-01-01", Money(1000))
    right = bank.open("savings", "B", "2026-01-01", Money(0))
    out, incoming = bank.transfer(left.number, right.number, Money(400),
                                  "2026-01-02")
    assert out.amount == Money(-400) and incoming.amount == Money(400)
    assert out.reference == incoming.reference
    assert left.balance == Money(600) and right.balance == Money(400)


def test_a_transfer_needs_two_different_accounts():
    bank = Bank()
    account = bank.open("savings", "A", "2026-01-01", Money(1000))
    with pytest.raises(BankingError, match="two different"):
        bank.transfer(account.number, account.number, Money(100), "2026-01-02")


@pytest.mark.parametrize("amount", [Money(0), Money(-100)])
def test_a_transfer_refuses_a_non_positive_amount(amount):
    bank = Bank()
    left = bank.open("savings", "A", "2026-01-01", Money(1000))
    right = bank.open("savings", "B", "2026-01-01", Money(1000))
    with pytest.raises(BankingError, match="must be positive"):
        bank.transfer(left.number, right.number, amount, "2026-01-02")


def test_a_transfer_refuses_a_non_money_amount():
    bank = Bank()
    left = bank.open("savings", "A", "2026-01-01", Money(1000))
    right = bank.open("savings", "B", "2026-01-01", Money(1000))
    with pytest.raises(DataError, match="must be Money"):
        bank.transfer(left.number, right.number, 100, "2026-01-02")


def test_a_transfer_refuses_a_bad_date():
    bank = Bank()
    left = bank.open("savings", "A", "2026-01-01", Money(1000))
    right = bank.open("savings", "B", "2026-01-01", Money(1000))
    with pytest.raises(DataError):
        bank.transfer(left.number, right.number, Money(100), "2026-1-2")


def test_a_refused_transfer_leaves_both_ledgers_untouched():
    bank = Bank()
    left = bank.open("savings", "A", "2026-01-01", Money(1000),
                     minimum=Money(500))
    right = bank.open("savings", "B", "2026-01-01", Money(0))
    before = (left.ledger, right.ledger, left.balance, right.balance)
    with pytest.raises(InsufficientFunds):
        bank.transfer(left.number, right.number, Money(600), "2026-01-02")
    assert (left.ledger, right.ledger, left.balance, right.balance) == before


def test_a_transfer_to_a_closed_account_is_refused():
    bank = Bank()
    left = bank.open("savings", "A", "2026-01-01", Money(1000))
    right = bank.open("savings", "B", "2026-01-01", Money(0))
    bank.close(right.number, "2026-01-02")
    with pytest.raises(AccountClosed):
        bank.transfer(left.number, right.number, Money(100), "2026-01-03")
    assert left.balance == Money(1000) and len(left) == 0


def test_a_transfer_from_a_closed_account_is_refused():
    bank = Bank()
    left = bank.open("savings", "A", "2026-01-01", Money(0))
    right = bank.open("savings", "B", "2026-01-01", Money(0))
    bank.close(left.number, "2026-01-02")
    with pytest.raises(AccountClosed):
        bank.transfer(left.number, right.number, Money(100), "2026-01-03")


def test_a_transfer_charges_no_fee_on_a_current_account():
    bank = Bank()
    left = bank.open("savings", "A", "2026-01-01", Money(10000))
    right = bank.open("current", "B", "2026-01-01", Money(0),
                      overdraft=Money(0), fee=Money(2500))
    bank.transfer(left.number, right.number, Money(1000), "2026-01-02")
    assert right.balance == Money(1000) and len(right) == 1


def test_a_transfer_counts_toward_the_savings_limit():
    bank = Bank()
    left = bank.open("savings", "A", "2026-01-01", Money(10000),
                     minimum=Money(0), monthly_withdrawal_limit=1)
    right = bank.open("savings", "B", "2026-01-01", Money(0))
    bank.transfer(left.number, right.number, Money(100), "2026-01-02")
    with pytest.raises(InsufficientFunds, match="limit is 1"):
        bank.transfer(left.number, right.number, Money(100), "2026-01-03")


def test_a_bank_closes_an_empty_account():
    bank = Bank()
    account = bank.open("savings", "A", "2026-01-01")
    bank.close(account.number, "2026-01-02")
    assert not account.is_open


def test_a_bank_close_refuses_an_unknown_account():
    with pytest.raises(AccountNotFound):
        Bank().close("AC-0009", "2026-01-02")


# --------------------------------------------------------------------------- #
# Audit
# --------------------------------------------------------------------------- #
def test_a_new_bank_passes_every_check():
    bank = Bank()
    bank.open("savings", "A", "2026-01-01", Money(1000),
              minimum=Money(500))
    checks = bank.audit()
    assert len(checks) == 7
    assert all(passed for _, passed in checks)
    assert bank.problems() == []


def test_the_audit_names_its_checks():
    names = [name for name, _ in Bank().audit()]
    assert "every transfer balances to zero" in names
    assert "closed accounts hold nothing" in names


def test_the_audit_catches_a_savings_dip():
    bank = Bank()
    account = bank.open("savings", "A", "2026-01-01", Money(1000),
                        minimum=Money(500))
    account._ledger.append(
        Transaction("withdrawal", Money(-800), "2026-01-02", "fabricated"))
    assert bank.problems() == [
        "savings accounts never fell below their minimum"]


def test_the_audit_catches_an_overdrawn_current_account():
    bank = Bank()
    account = bank.open("current", "A", "2026-01-01", Money(0),
                        overdraft=Money(1000))
    account._ledger.append(
        Transaction("withdrawal", Money(-1001), "2026-01-02", "fabricated"))
    assert "current accounts never passed their overdraft" in bank.problems()


def test_the_audit_catches_an_unbalanced_transfer():
    bank = Bank()
    account = bank.open("savings", "A", "2026-01-01", Money(1000),
                        minimum=Money(0))
    account._ledger.append(
        Transaction("transfer_out", Money(-100), "2026-01-02", "x", "TR-1"))
    assert "every transfer balances to zero" in bank.problems()


def test_the_audit_catches_a_closed_account_holding_money():
    bank = Bank()
    account = bank.open("savings", "A", "2026-01-01", Money(0))
    account.close("2026-01-02")
    account.opening = Money(100)
    assert "closed accounts hold nothing" in bank.problems()


def test_the_audit_catches_a_malformed_entry():
    bank = Bank()
    account = bank.open("savings", "A", "2026-01-01", Money(1000),
                        minimum=Money(0))
    account._ledger.append(
        Transaction("deposit", Money(100), "2026-01-02"))
    account._ledger[-1] = object()
    assert "every ledger entry is a signed, non-zero amount" in \
        bank.problems()


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #
def test_a_bank_round_trips_through_dict():
    bank = Bank("Test")
    left = bank.open("savings", "A", "2026-01-01", Money(1000),
                     minimum=Money(500), monthly_withdrawal_limit=2)
    right = bank.open("current", "B", "2026-01-02", Money(0),
                      overdraft=Money(5000), fee=Money(250))
    bank.transfer(left.number, right.number, Money(200), "2026-01-03", "x")
    copy = Bank.from_dict(bank.to_dict())
    assert copy.to_dict() == bank.to_dict()
    assert copy.total == bank.total
    assert copy.audit() == bank.audit()


def test_a_bank_dict_records_the_sequence():
    bank = Bank()
    bank.open("savings", "A", "2026-01-01")
    assert bank.to_dict()["sequence"] == 1


def test_a_bank_from_dict_refuses_a_non_object():
    with pytest.raises(DataError, match="must be an object"):
        Bank.from_dict([])


def test_a_bank_from_dict_refuses_an_unknown_key():
    with pytest.raises(DataError, match="unknown bank keys"):
        Bank.from_dict({"name": "x", "accounts": [], "extra": 1})


def test_a_bank_from_dict_requires_its_keys():
    with pytest.raises(DataError, match="missing 'accounts'"):
        Bank.from_dict({"name": "x"})


def test_a_bank_from_dict_refuses_a_non_list_of_accounts():
    with pytest.raises(DataError, match="must be a list"):
        Bank.from_dict({"name": "x", "accounts": {}})


def test_a_bank_from_dict_refuses_a_bad_sequence():
    with pytest.raises(DataError, match="whole number"):
        Bank.from_dict({"name": "x", "accounts": [], "sequence": "4"})


def test_a_bank_from_dict_refuses_a_sequence_below_the_account_count():
    row = {"number": "AC-0001", "kind": "savings", "holder": "A",
           "opened": "2026-01-01", "opening_cents": 0}
    with pytest.raises(DataError, match="cannot be smaller"):
        Bank.from_dict({"name": "x", "accounts": [row], "sequence": 0})


def test_an_account_from_dict_refuses_an_unknown_key():
    with pytest.raises(DataError, match="unknown account keys"):
        account_from_dict({"number": "AC-1", "kind": "savings",
                           "holder": "A", "opened": "2026-01-01",
                           "opening_cents": 0, "colour": "red"})


def test_an_account_from_dict_requires_its_keys():
    with pytest.raises(DataError, match="missing 'opening_cents'"):
        account_from_dict({"number": "AC-1", "kind": "savings",
                           "holder": "A", "opened": "2026-01-01"})


def test_an_account_from_dict_refuses_a_non_integer_opening():
    with pytest.raises(DataError, match="whole number"):
        account_from_dict({"number": "AC-1", "kind": "savings",
                           "holder": "A", "opened": "2026-01-01",
                           "opening_cents": "0"})


def test_an_account_from_dict_refuses_an_unknown_kind():
    with pytest.raises(DataError, match="not an account kind"):
        account_from_dict({"number": "AC-1", "kind": "loan", "holder": "A",
                           "opened": "2026-01-01", "opening_cents": 0})


def test_an_account_from_dict_refuses_a_non_object_ledger_entry():
    with pytest.raises(DataError, match="ledger entry must be an object"):
        account_from_dict({"number": "AC-1", "kind": "savings", "holder": "A",
                           "opened": "2026-01-01", "opening_cents": 0,
                           "ledger": [[]]})


def test_an_account_from_dict_refuses_an_unknown_ledger_key():
    with pytest.raises(DataError, match="unknown ledger keys"):
        account_from_dict({"number": "AC-1", "kind": "savings", "holder": "A",
                           "opened": "2026-01-01", "opening_cents": 0,
                           "ledger": [{"kind": "deposit", "cents": 100,
                                       "when": "2026-01-02", "note": "x"}]})


def test_an_account_from_dict_requires_its_ledger_keys():
    with pytest.raises(DataError, match="missing 'cents'"):
        account_from_dict({"number": "AC-1", "kind": "savings", "holder": "A",
                           "opened": "2026-01-01", "opening_cents": 0,
                           "ledger": [{"kind": "deposit",
                                       "when": "2026-01-02"}]})


def test_the_data_file_is_named_for_its_purpose():
    assert DATA_FILE.name == "bank.json"
    assert DATA_FILE.parent.name == "data"


def test_the_seeded_bank_loads_and_passes_its_audit():
    bank = load_bank()
    assert len(bank) == 4
    assert bank.total == Money(220000)
    assert bank.problems() == []


def test_the_seeded_accounts_have_the_pinned_balances():
    bank = load_bank()
    balances = {account.number: account.balance for account in bank}
    assert balances == {"AC-0001": Money(105000),
                        "AC-0002": Money(80000),
                        "AC-0003": Money(35000),
                        "AC-0004": Money(0)}


def test_the_seeded_transfer_reference_matches():
    bank = load_bank()
    left = bank.get("AC-0001")
    right = bank.get("AC-0003")
    out = [entry for entry in left if entry.kind == "transfer_out"][0]
    incoming = [entry for entry in right if entry.kind == "transfer_in"][0]
    assert out.reference == incoming.reference


def test_the_seeded_closed_account_is_closed():
    assert not load_bank().get("AC-0004").is_open


def test_load_bank_refuses_a_missing_file(tmp_path):
    with pytest.raises(DataError, match="not found"):
        load_bank(tmp_path / "nope.json")


def test_load_bank_refuses_invalid_json(tmp_path):
    path = tmp_path / "bank.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(DataError, match="not valid JSON"):
        load_bank(path)


def test_save_bank_writes_a_readable_file(tmp_path):
    bank = load_bank()
    target = tmp_path / "out.json"
    save_bank(target, bank)
    assert load_bank(target).to_dict() == bank.to_dict()


def test_save_bank_creates_directories(tmp_path):
    target = tmp_path / "a" / "b" / "bank.json"
    save_bank(target, Bank())
    assert target.is_file()


def test_save_bank_ends_with_a_newline(tmp_path):
    target = tmp_path / "out.json"
    save_bank(target, Bank())
    assert target.read_text(encoding="utf-8").endswith("}\n")


def test_save_bank_is_byte_identical_on_a_second_save(tmp_path):
    target = tmp_path / "out.json"
    bank = load_bank()
    save_bank(target, bank)
    first = target.read_bytes()
    save_bank(target, load_bank(target))
    assert target.read_bytes() == first


def test_every_ledger_kind_is_known():
    assert set(KINDS) == {"opening", "deposit", "withdrawal", "fee",
                          "interest", "transfer_in", "transfer_out"}


def test_the_legacy_head_is_the_stray_assignment():
    assert LEGACY_HEAD == 'id="q2m4nl"'


# --------------------------------------------------------------------------- #
# Demo and CLI
# --------------------------------------------------------------------------- #
def test_demo_returns_zero(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out
    assert "Demo completed successfully." in out


def test_demo_is_deterministic(capsys):
    run_demo()
    first = capsys.readouterr().out
    run_demo()
    assert capsys.readouterr().out == first


def test_demo_shows_the_float_drift(capsys):
    run_demo()
    assert "0.99999999999999989" in capsys.readouterr().out


def test_demo_shows_the_shadowed_builtin(capsys):
    run_demo()
    assert "not callable" in capsys.readouterr().out


def test_demo_prints_no_non_ascii(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert all(ord(character) < 128 for character in out)


def test_cli_demo(capsys):
    assert cli.main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_demo_quiet(capsys):
    assert cli.main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_lists_the_seeded_accounts(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "AC-0001" in out and "4 accounts" in out
    assert "2,200.00" in out


def test_cli_balance(capsys):
    assert cli.main(["--balance", "AC-0002"]) == 0
    out = capsys.readouterr().out
    assert "Bilal Khan" in out and "800.00" in out


def test_cli_balance_of_an_unknown_account_exits_two(capsys):
    assert cli.main(["--balance", "AC-9999"]) == 2
    assert "no account" in capsys.readouterr().err


def test_cli_statement_lists_entries(capsys):
    assert cli.main(["--statement", "AC-0001"]) == 0
    out = capsys.readouterr().out
    assert "salary" in out and "rent" in out and "transfer_out" in out


def test_cli_audit_passes(capsys):
    assert cli.main(["--audit"]) == 0
    out = capsys.readouterr().out
    assert "7/7 checks passed" in out


def test_cli_opens_an_account(capsys):
    assert cli.main(["--open", "savings:New Person:1,000.00"]) == 0
    out = capsys.readouterr().out
    assert "AC-0005" in out and "New Person" in out and "1,000.00" in out


def test_cli_open_refuses_an_unknown_kind(capsys):
    assert cli.main(["--open", "loan:Someone"]) == 2
    assert "not one of" in capsys.readouterr().err


def test_cli_deposit(capsys):
    assert cli.main(["--deposit", "AC-0002:250.00"]) == 0
    out = capsys.readouterr().out
    assert "Rs 250.00" in out and "balance Rs 1,050.00" in out


def test_cli_withdraw(capsys):
    assert cli.main(["--withdraw", "AC-0001:150.00"]) == 0
    out = capsys.readouterr().out
    assert "1 row(s)" in out and "900.00" in out


def test_cli_withdraw_reports_two_rows_on_a_current_account(capsys):
    assert cli.main(["--withdraw", "AC-0003:100.00"]) == 0
    out = capsys.readouterr().out
    assert "2 row(s)" in out


def test_cli_withdraw_refuses_too_much(capsys):
    assert cli.main(["--withdraw", "AC-0001:99999.00"]) == 2
    assert "cannot withdraw" in capsys.readouterr().err


def test_cli_transfer(capsys):
    assert cli.main(["--transfer", "AC-0001:AC-0003:250.00"]) == 0
    out = capsys.readouterr().out
    assert "AC-0001 -> AC-0003" in out and "800.00" in out


def test_cli_transfer_refuses_a_malformed_spec(capsys):
    assert cli.main(["--transfer", "AC-0001:250.00"]) == 2
    assert "expected FROM:TO:AMOUNT" in capsys.readouterr().err


def test_cli_deposit_refuses_a_bad_amount(capsys):
    assert cli.main(["--deposit", "AC-0002:abc"]) == 2
    assert "not a number" in capsys.readouterr().err


def test_cli_deposit_refuses_a_malformed_spec(capsys):
    assert cli.main(["--deposit", "AC-0002"]) == 2
    assert "expected ACCOUNT:AMOUNT" in capsys.readouterr().err


def test_cli_legacy_mode(capsys):
    assert cli.main(["--legacy"]) == 0
    out = capsys.readouterr().out
    assert "q2m4nl" in out and "builtin id()" in out


def test_cli_json_list(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["mode"] == "list"
    assert len(payload["accounts"]) == 4
    assert payload["total"] == "Rs 2,200.00"


def test_cli_json_audit(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--audit", "--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["clean"] is True and len(payload["checks"]) == 7


def test_cli_write_saves_the_change(tmp_path, capsys):
    target = tmp_path / "saved.json"
    assert cli.main(["--deposit", "AC-0002:250.00", "--write",
                     str(target)]) == 0
    capsys.readouterr()
    assert load_bank(target).get("AC-0002").balance == Money(105000)


def test_cli_missing_file_exits_two(capsys):
    assert cli.main(["--file", "nope.json"]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--audit", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""
