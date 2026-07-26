"""
Application entry point.
"""

from library_service import LibraryService
from utils import Utils

service = LibraryService()

while True:

    Utils.header()
    Utils.menu()

    choice = input("\nEnter Choice : ")

    if choice == "1":

        title = input("Title : ")
        author = input("Author : ")
        isbn = input("ISBN : ")
        quantity = int(input("Quantity : "))

        service.add_book(
            title,
            author,
            isbn,
            quantity,
        )

    elif choice == "2":
        service.view_books()

    elif choice == "3":
        service.search_book(input("Keyword : "))

    elif choice == "4":

        service.update_book(
            int(input("Book ID : ")),
            input("Title : "),
            input("Author : "),
            input("ISBN : "),
            int(input("Quantity : ")),
        )

    elif choice == "5":
        service.delete_book(int(input("Book ID : ")))

    elif choice == "6":
        service.issue_book(int(input("Book ID : ")))

    elif choice == "7":
        service.return_book(int(input("Book ID : ")))

    elif choice == "8":
        service.issued_books()

    elif choice == "9":
        service.total_books()

    elif choice == "10":
        print("\nGoodbye!")
        break

    else:
        print("\nInvalid choice.")

    Utils.pause()