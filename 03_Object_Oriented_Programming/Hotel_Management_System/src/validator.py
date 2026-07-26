"""
Input validation for Hotel Management System.
"""

import re

class Validator:

    @staticmethod
    def validate_room_number(room_number):
        return room_number.isdigit()

    @staticmethod
    def validate_room_type(room_type):
        room_type = room_type.lower()
        return room_type in [
            "single",
            "double",
            "deluxe",
            "suite",
        ]

    @staticmethod
    def validate_price(price):
        try:
            return float(price) > 0
        except ValueError:
            return False

    @staticmethod
    def validate_name(name):
        return len(name.strip()) > 0

    @staticmethod
    def validate_phone(phone):
        return bool(re.fullmatch(r"\d{10}", phone))

    @staticmethod
    def validate_email(email):
        pattern = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
        return bool(re.fullmatch(pattern, email))