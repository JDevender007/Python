"""
Validation functions for Contact Book.
"""

import re

class Validator:

    @staticmethod
    def validate_name(name: str) -> bool:
        return bool(name.strip())

    @staticmethod
    def validate_phone(phone: str) -> bool:
        return bool(re.fullmatch(r"\d{10}", phone))

    @staticmethod
    def validate_email(email: str) -> bool:
        pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
        return bool(re.fullmatch(pattern, email))

    @staticmethod
    def validate_address(address: str) -> bool:
        return len(address.strip()) > 0