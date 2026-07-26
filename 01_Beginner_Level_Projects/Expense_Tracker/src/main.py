"""
Expense Tracker

Main Program
"""

from datetime import datetime

from expense_service import ExpenseService
from report_service import ReportService

from validator import (
    validate_title,
    validate_category,
    validate_amount,
    validate_description,
)

from utils import (
    header,
    pause,
)

expense_service = ExpenseService()
report_service = ReportService()

def menu():

    while True:

        header("EXPENSE TRACKER")

        print("1. Add Expense")
        print("2. View Expenses")
        print("3. Search Expense")
        print("4. Update Expense")
        print("5. Delete Expense")
        print("6. Total Expense")
        print("7. Category Report")
        print("8. Monthly Report")
        print("9. Exit")

        choice = input("\nEnter Choice : ")

        try:

            if choice == "1":

                title = validate_title(
                    input("Title : ")
                )

                category = validate_category(
                    input("Category : ")
                )

                amount = validate_amount(
                    input("Amount : ")
                )

                description = validate_description(
                    input("Description : ")
                )

                date = datetime.today().date()

                expense_service.add_expense(
                    title,
                    category,
                    amount,
                    description,
                    date
                )

                pause()

            elif choice == "2":

                expense_service.view_expenses()
                pause()

            elif choice == "3":

                keyword = input("Search : ")

                expense_service.search_expense(
                    keyword
                )

                pause()

            elif choice == "4":

                expense_id = int(
                    input("Expense ID : ")
                )

                title = input("Title : ")
                category = input("Category : ")
                amount = float(
                    input("Amount : ")
                )
                description = input(
                    "Description : "
                )

                expense_service.update_expense(
                    expense_id,
                    title,
                    category,
                    amount,
                    description
                )

                pause()

            elif choice == "5":

                expense_id = int(
                    input("Expense ID : ")
                )

                expense_service.delete_expense(
                    expense_id
                )

                pause()

            elif choice == "6":

                report_service.total_expense()

                pause()

            elif choice == "7":

                report_service.category_report()

                pause()

            elif choice == "8":

                report_service.monthly_report()

                pause()

            elif choice == "9":

                expense_service.close()
                report_service.close()

                print("\nGoodbye!")
                break

            else:

                print("\nInvalid choice.")
                pause()

        except Exception as error:

            print(f"\nError : {error}")
            pause()

if __name__ == "__main__":

    menu()