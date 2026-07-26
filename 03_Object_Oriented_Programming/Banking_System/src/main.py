id="p4t8sw"
"""
main.py

Entry point for Banking System.
"""

from banking_service import BankingService
from utils import Utils
from validator import Validator

service = BankingService()

def create_account() -> None:
    print("\nCreate Account")

    account_holder = input("Account Holder : ").strip()
    while not Validator.validate_name(account_holder):
        print("Invalid name.")
        account_holder = input("Account Holder : ").strip()

    account_type = input("Account Type (Savings/Current/Salary) : ").strip()
    while not Validator.validate_account_type(account_type):
        print("Invalid account type.")
        account_type = input("Account Type (Savings/Current/Salary) : ").strip()

    phone = input("Phone : ").strip()
    while not Validator.validate_phone(phone):
        print("Phone must contain exactly 10 digits.")
        phone = input("Phone : ").strip()

    email = input("Email : ").strip()
    while not Validator.validate_email(email):
        print("Invalid email address.")
        email = input("Email : ").strip()

    balance = input("Initial Deposit (optional, press Enter for 0) : ").strip()
    if balance == "":
        balance_value = 0.0
    else:
        while not Validator.validate_amount(balance):
            print("Enter a valid amount greater than zero.")
            balance = input("Initial Deposit (optional, press Enter for 0) : ").strip()
            if balance == "":
                balance_value = 0.0
                break
        else:
            balance_value = float(balance)

    service.create_account(
        account_holder,
        account_type,
        phone,
        email,
        balance_value,
    )

def search_account() -> None:
    keyword = input("\nSearch Account Number, Name, Phone, Email : ").strip()
    service.search_account(keyword)

def deposit_money() -> None:
    account_number = input("\nAccount Number : ").strip()
    amount = input("Amount : ").strip()

    while not Validator.validate_amount(amount):
        print("Enter a valid amount greater than zero.")
        amount = input("Amount : ").strip()

    service.deposit_money(account_number, float(amount))

def withdraw_money() -> None:
    account_number = input("\nAccount Number : ").strip()
    amount = input("Amount : ").strip()

    while not Validator.validate_amount(amount):
        print("Enter a valid amount greater than zero.")
        amount = input("Amount : ").strip()

    service.withdraw_money(account_number, float(amount))

def update_account() -> None:
    account_number = input("\nAccount Number : ").strip()

    account_holder = input("Account Holder : ").strip()
    while not Validator.validate_name(account_holder):
        print("Invalid name.")
        account_holder = input("Account Holder : ").strip()

    account_type = input("Account Type (Savings/Current/Salary) : ").strip()
    while not Validator.validate_account_type(account_type):
        print("Invalid account type.")
        account_type = input("Account Type (Savings/Current/Salary) : ").strip()

    phone = input("Phone : ").strip()
    while not Validator.validate_phone(phone):
        print("Phone must contain exactly 10 digits.")
        phone = input("Phone : ").strip()

    email = input("Email : ").strip()
    while not Validator.validate_email(email):
        print("Invalid email address.")
        email = input("Email : ").strip()

    service.update_account(
        account_number,
        account_holder,
        account_type,
        phone,
        email,
    )

def delete_account() -> None:
    account_number = input("\nAccount Number : ").strip()
    service.close_account(account_number)

def show_balance() -> None:
    account_number = input("\nAccount Number : ").strip()
    service.show_balance(account_number)

def transaction_history() -> None:
    account_number = input("\nAccount Number : ").strip()
    service.transaction_history(account_number)

def main() -> None:
    while True:
        Utils.header()
        Utils.menu()

        choice = input("\nEnter Choice : ").strip()

        if choice == "1":
            create_account()
        elif choice == "2":
            service.view_accounts()
        elif choice == "3":
            search_account()
        elif choice == "4":
            deposit_money()
        elif choice == "5":
            withdraw_money()
        elif choice == "6":
            update_account()
        elif choice == "7":
            delete_account()
        elif choice == "8":
            show_balance()
        elif choice == "9":
            transaction_history()
        elif choice == "10":
            print("\nThank you for using Banking System.")
            service.close()
            break
        else:
            print("\nInvalid choice.")

        Utils.pause()

if __name__ == "__main__":
    main()