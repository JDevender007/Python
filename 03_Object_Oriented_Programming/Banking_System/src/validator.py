"""
validator.py

Input validation for Banking System.
"""

import re

class Validator:
    @staticmethod
    def validate_name(name: str) -> bool:
        return bool(name.strip())

    @staticmethod
    def validate_account_type(account_type: str) -> bool:
        allowed_types = {"savings", "current", "salary"}
        return account_type.strip().lower() in allowed_types

    @staticmethod
    def validate_phone(phone: str) -> bool:
        return bool(re.fullmatch(r"\d{10}", phone))

    @staticmethod
    def validate_email(email: str) -> bool:
        pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
        return bool(re.fullmatch(pattern, email))

    @staticmethod
    def validate_amount(amount: str) -> bool:
        try:
            value = float(amount)
            return value > 0
        except ValueError:
            return False

    @staticmethod
    def validate_account_number(account_number: str) -> bool:
        return account_number.strip().isdigit()

    @staticmethod
    def validate_choice(choice: str) -> bool:
        return choice.strip().isdigit()