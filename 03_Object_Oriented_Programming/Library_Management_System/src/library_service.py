"""
Business logic.
"""

from sqlalchemy import or_

from database import Base
from database import engine
from database import get_session
from models import Book

Base.metadata.create_all(bind=engine)

class LibraryService:

    def __init__(self):
        self.session = get_session()

    def add_book(self, title, author, isbn, quantity):

        book = Book(
            title=title,
            author=author,
            isbn=isbn,
            quantity=quantity,
            available=quantity,
        )

        self.session.add(book)
        self.session.commit()

        print("\nBook added successfully.")

    def view_books(self):

        books = self.session.query(Book).all()

        if not books:
            print("\nNo books found.")
            return

        for book in books:
            print("-" * 50)
            print(f"ID        : {book.id}")
            print(f"Title     : {book.title}")
            print(f"Author    : {book.author}")
            print(f"ISBN      : {book.isbn}")
            print(f"Quantity  : {book.quantity}")
            print(f"Available : {book.available}")

    def search_book(self, keyword):

        books = (
            self.session.query(Book)
            .filter(
                or_(
                    Book.title.ilike(f"%{keyword}%"),
                    Book.author.ilike(f"%{keyword}%"),
                    Book.isbn.ilike(f"%{keyword}%"),
                )
            )
            .all()
        )

        if not books:
            print("\nBook not found.")
            return

        for book in books:
            print("-" * 50)
            print(f"{book.id} | {book.title} | {book.author}")

    def update_book(self, book_id, title, author, isbn, quantity):

        book = self.session.query(Book).get(book_id)

        if not book:
            print("\nBook not found.")
            return

        issued = book.quantity - book.available

        book.title = title
        book.author = author
        book.isbn = isbn
        book.quantity = quantity
        book.available = max(quantity - issued, 0)

        self.session.commit()

        print("\nBook updated.")

    def delete_book(self, book_id):

        book = self.session.query(Book).get(book_id)

        if not book:
            print("\nBook not found.")
            return

        self.session.delete(book)
        self.session.commit()

        print("\nBook deleted.")

    def issue_book(self, book_id):

        book = self.session.query(Book).get(book_id)

        if not book:
            print("\nBook not found.")
            return

        if book.available <= 0:
            print("\nBook unavailable.")
            return

        book.available -= 1

        if book.available != book.quantity:
            book.issued = True

        self.session.commit()

        print("\nBook issued.")

    def return_book(self, book_id):

        book = self.session.query(Book).get(book_id)

        if not book:
            print("\nBook not found.")
            return

        if book.available >= book.quantity:
            print("\nAll books already returned.")
            return

        book.available += 1

        if book.available == book.quantity:
            book.issued = False

        self.session.commit()

        print("\nBook returned.")

    def issued_books(self):

        books = self.session.query(Book).filter(Book.issued == True).all()

        if not books:
            print("\nNo issued books.")
            return

        for book in books:
            print(f"{book.id} | {book.title}")

    def total_books(self):

        total = self.session.query(Book).count()

        print(f"\nTotal Books : {total}")