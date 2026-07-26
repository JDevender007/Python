"""
Input validation for Inventory Management System.
"""

import re

class Validator:
    @staticmethod
    def validate_name(name: str) -> bool:
        return bool(name.strip())

    @staticmethod
    def validate_category(category: str) -> bool:
        return bool(category.strip())

    @staticmethod
    def validate_quantity(quantity: str) -> bool:
        return quantity.isdigit() and int(quantity) >= 0

    @staticmethod
    def validate_price(price: str) -> bool:
        try:
            value = float(price)
            return value >= 0
        except ValueError:
            return False

    @staticmethod
    def validate_supplier(supplier: str) -> bool:
        return bool(supplier.strip())

    @staticmethod
    def validate_choice(choice: str) -> bool:
        return choice.strip().isdigit()