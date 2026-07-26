"""
expense_service.py

CRUD operations for expenses.
"""

from database import SessionLocal
from database import Base
from database import engine

from models import Expense

Base.metadata.create_all(bind=engine)

class ExpenseService:

    def __init__(self):

        self.db = SessionLocal()

    def add_expense(
        self,
        title,
        category,
        amount,
        description,
        expense_date
    ):

        expense = Expense(
            title=title,
            category=category,
            amount=amount,
            description=description,
            expense_date=expense_date
        )

        self.db.add(expense)
        self.db.commit()

        print("\nExpense added successfully.")

    def view_expenses(self):

        expenses = self.db.query(Expense).all()

        if not expenses:
            print("\nNo expenses found.")
            return

        print("\n==============================")

        for expense in expenses:

            print(
                f"""
ID          : {expense.id}
Title       : {expense.title}
Category    : {expense.category}
Amount      : ₹{expense.amount:.2f}
Date        : {expense.expense_date}
Description : {expense.description}
------------------------------
"""
            )

    def search_expense(self, keyword):

        expenses = (
            self.db.query(Expense)
            .filter(
                Expense.title.ilike(f"%{keyword}%")
            )
            .all()
        )

        if not expenses:
            print("\nNo matching expense found.")
            return

        for expense in expenses:

            print(
                expense.id,
                expense.title,
                expense.amount
            )

    def update_expense(
        self,
        expense_id,
        title,
        category,
        amount,
        description
    ):
        expense = (
            self.db.query(Expense)
            .filter(
                Expense.id == expense_id
            )
            .first()
        )

        if expense is None:
            print("Expense not found.")
            return

        expense.title = title
        expense.category = category
        expense.amount = amount
        expense.description = description

        self.db.commit()

        print("\nExpense updated successfully.")

    def delete_expense(self, expense_id):

        expense = (
            self.db.query(Expense)
            .filter(
                Expense.id == expense_id
            )
            .first()
        )

        if expense is None:
            print("Expense not found.")
            return

        self.db.delete(expense)
        self.db.commit()

        print("\nExpense deleted successfully.")

    def close(self):

        self.db.close()