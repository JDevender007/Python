"""
report_service.py

Expense reports.
"""

from sqlalchemy import func

from database import SessionLocal
from models import Expense

class ReportService:

    def __init__(self):

        self.db = SessionLocal()

    def total_expense(self):

        total = (
            self.db.query(
                func.sum(Expense.amount)
            )
            .scalar()
        )

        if total is None:
            total = 0

        print(f"\nTotal Expense : ₹{total:.2f}")

    def category_report(self):

        results = (
            self.db.query(
                Expense.category,
                func.sum(Expense.amount)
            )
            .group_by(Expense.category)
            .all()
        )

        if not results:
            print("\nNo expenses found.")
            return

        print("\n========== Category Report ==========\n")

        for category, total in results:

            print(
                f"{category:<20} ₹{total:.2f}"
            )

    def monthly_report(self):

        results = (
            self.db.query(
                func.strftime(
                    "%Y-%m",
                    Expense.expense_date
                ),
                func.sum(Expense.amount)
            )
            .group_by(
                func.strftime(
                    "%Y-%m",
                    Expense.expense_date
                )
            )
            .all()
        )

        if not results:
            print("\nNo expenses found.")
            return

        print("\n========== Monthly Report ==========\n")

        for month, total in results:

            print(
                f"{month:<15} ₹{total:.2f}"
            )

    def close(self):

        self.db.close()