id="k5b7rt"
"""
utils.py

Utility functions for Banking System.
"""

class Utils:
    @staticmethod
    def header() -> None:
        print("\n" + "=" * 50)
        print("                BANKING SYSTEM")
        print("=" * 50)

    @staticmethod
    def menu() -> None:
        print("\n1. Create Account")
        print("2. View Accounts")
        print("3. Search Account")
        print("4. Deposit Money")
        print("5. Withdraw Money")
        print("6. Update Account")
        print("7. Close Account")
        print("8. Show Balance")
        print("9. Transaction History")
        print("10. Exit")

    @staticmethod
    def pause() -> None:
        input("\nPress Enter to continue...")

    @staticmethod
    def line() -> None:
        print("-" * 50)