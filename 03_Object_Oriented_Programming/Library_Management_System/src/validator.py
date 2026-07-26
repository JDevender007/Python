"""
Validation functions.
"""

class Validator:

    @staticmethod
    def validate_text(value: str):
        return bool(value.strip())

    @staticmethod
    def validate_quantity(value: str):
        return value.isdigit() and int(value) >= 0

    @staticmethod
    def validate_isbn(value: str):
        return len(value.strip()) >= 5