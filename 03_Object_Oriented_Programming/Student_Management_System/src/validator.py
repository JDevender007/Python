"""
Validation functions.
"""

import re

class Validator:

    @staticmethod
    def validate_name(name):
        return bool(name.strip())

    @staticmethod
    def validate_roll(roll):
        return bool(roll.strip())

    @staticmethod
    def validate_department(department):
        return bool(department.strip())

    @staticmethod
    def validate_year(year):
        return year.isdigit() and 1 <= int(year) <= 4

    @staticmethod
    def validate_cgpa(cgpa):
        try:
            value = float(cgpa)
            return 0 <= value <= 10
        except ValueError:
            return False

    @staticmethod
    def validate_phone(phone):
        return bool(re.fullmatch(r"\d{10}", phone))

    @staticmethod
    def validate_email(email):
        pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
        return bool(re.fullmatch(pattern, email))