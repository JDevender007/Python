"""
validator.py

Input validation functions.
"""

def validate_title(title):
    title = title.strip()

    if not title:
        raise ValueError("Title cannot be empty.")

    return title

def validate_category(category):
    category = category.strip()

    if not category:
        raise ValueError("Category cannot be empty.")

    return category

def validate_amount(amount):

    try:
        amount = float(amount)

        if amount <= 0:
            raise ValueError

        return amount

    except ValueError:
        raise ValueError(
            "Amount must be greater than zero."
        )

def validate_description(description):

    return description.strip()