"""
Utility functions for Inventory Management System.
"""

class Utils:
    @staticmethod
    def header() -> None:
        print("\n" + "=" * 50)
        print("        INVENTORY MANAGEMENT SYSTEM")
        print("=" * 50)

    @staticmethod
    def menu() -> None:
        print("\n1. Add Item")
        print("2. View Items")
        print("3. Search Item")
        print("4. Update Item")
        print("5. Delete Item")
        print("6. Stock In")
        print("7. Stock Out")
        print("8. Low Stock Alert")
        print("9. Total Items")
        print("10. Exit")

    @staticmethod
    def pause() -> None:
        input("\nPress Enter to continue...")

    @staticmethod
    def line() -> None:
        print("-" * 50)