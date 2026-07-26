id="q2m4nl"
"""
banking_service.py

Business logic for Banking System.
"""

import secrets

from sqlalchemy import desc

from database import Base
from database import engine
from database import get_session
from models import Account
from models import Transaction

Base.metadata.create_all(bind=engine)

class BankingService:
    def __init__(self) -> None:
        self.session = get_session()

    def _generate_account_number(self) -> str:
        while True:
            account_number = str(secrets.randbelow(10**10)).zfill(10)

            exists = (
                self.session.query(Account)
                .filter(Account.account_number == account_number)
                .first()
            )

            if not exists:
                return account_number

    def create_account(
        self,
        account_holder: str,
        account_type: str,
        phone: str,
        email: str,
        balance: float = 0.0,
    ) -> None:
        account = Account(
            account_number=self._generate_account_number(),
            account_holder=account_holder,
            account_type=account_type.title(),
            balance=balance,
            phone=phone,
            email=email,
        )

        self.session.add(account)
        self.session.commit()

        print("\nAccount created successfully.")
        print(f"Account Number : {account.account_number}")

    def view_accounts(self) -> None:
        accounts = (
            self.session.query(Account)
            .order_by(Account.account_holder)
            .all()
        )

        if not accounts:
            print("\nNo accounts found.")
            return

        for account in accounts:
            print("-" * 50)
            print(f"ID              : {account.id}")
            print(f"Account Number  : {account.account_number}")
            print(f"Account Holder  : {account.account_holder}")
            print(f"Account Type    : {account.account_type}")
            print(f"Balance         : ₹{account.balance:.2f}")
            print(f"Phone           : {account.phone}")
            print(f"Email           : {account.email}")
            print(f"Created At      : {account.created_at}")

    def search_account(self, keyword: str) -> None:
        account = (
            self.session.query(Account)
            .filter(
                (Account.account_number == keyword)
                | (Account.account_holder.ilike(f"%{keyword}%"))
                | (Account.phone == keyword)
                | (Account.email.ilike(f"%{keyword}%"))
            )
            .first()
        )

        if not account:
            print("\nAccount not found.")
            return

        print("-" * 50)
        print(f"ID              : {account.id}")
        print(f"Account Number  : {account.account_number}")
        print(f"Account Holder  : {account.account_holder}")
        print(f"Account Type    : {account.account_type}")
        print(f"Balance         : ₹{account.balance:.2f}")
        print(f"Phone           : {account.phone}")
        print(f"Email           : {account.email}")
        print(f"Created At      : {account.created_at}")

    def deposit_money(self, account_number: str, amount: float) -> None:
        account = (
            self.session.query(Account)
            .filter(Account.account_number == account_number)
            .first()
        )

        if not account:
            print("\nAccount not found.")
            return

        account.balance += amount

        transaction = Transaction(
            account_id=account.id,
            transaction_type="Deposit",
            amount=amount,
        )

        self.session.add(transaction)
        self.session.commit()

        print("\nMoney deposited successfully.")
        print(f"New Balance : ₹{account.balance:.2f}")

    def withdraw_money(self, account_number: str, amount: float) -> None:
        account = (
            self.session.query(Account)
            .filter(Account.account_number == account_number)
            .first()
        )

        if not account:
            print("\nAccount not found.")
            return

        if amount > account.balance:
            print("\nInsufficient balance.")
            return

        account.balance -= amount

        transaction = Transaction(
            account_id=account.id,
            transaction_type="Withdraw",
            amount=amount,
        )

        self.session.add(transaction)
        self.session.commit()

        print("\nMoney withdrawn successfully.")
        print(f"Remaining Balance : ₹{account.balance:.2f}")

    def update_account(
        self,
        account_number: str,
        account_holder: str,
        account_type: str,
        phone: str,
        email: str,
    ) -> None:
        account = (
            self.session.query(Account)
            .filter(Account.account_number == account_number)
            .first()
        )

        if not account:
            print("\nAccount not found.")
            return

        account.account_holder = account_holder
        account.account_type = account_type.title()
        account.phone = phone
        account.email = email

        self.session.commit()

        print("\nAccount updated successfully.")

    def close_account(self, account_number: str) -> None:
        account = (
            self.session.query(Account)
            .filter(Account.account_number == account_number)
            .first()
        )

        if not account:
            print("\nAccount not found.")
            return

        self.session.delete(account)
        self.session.commit()

        print("\nAccount closed successfully.")

    def show_balance(self, account_number: str) -> None:
        account = (
            self.session.query(Account)
            .filter(Account.account_number == account_number)
            .first()
        )

        if not account:
            print("\nAccount not found.")
            return

        print(f"\nAccount Holder : {account.account_holder}")
        print(f"Account Number : {account.account_number}")
        print(f"Balance        : ₹{account.balance:.2f}")

    def transaction_history(self, account_number: str) -> None:
        account = (
            self.session.query(Account)
            .filter(Account.account_number == account_number)
            .first()
        )

        if not account:
            print("\nAccount not found.")
            return

        transactions = (
            self.session.query(Transaction)
            .filter(Transaction.account_id == account.id)
            .order_by(desc(Transaction.created_at))
            .all()
        )

        if not transactions:
            print("\nNo transactions found.")
            return

        print(f"\nTransaction History for {account.account_holder}")
        print("-" * 50)

        for transaction in transactions:
            print(f"Type   : {transaction.transaction_type}")
            print(f"Amount : ₹{transaction.amount:.2f}")
            print(f"Date   : {transaction.created_at}")
            print("-" * 50)

    def close(self) -> None:
        self.session.close()