import struct
import os
FORMAT = "i30s20sf"
RECORD_SIZE = struct.calcsize(FORMAT)
FILE_NAME = "books.dat"
def pack_record(book_id, title, author, price):
    title = title.strip().encode()[:30].ljust(30)
    author = author.strip().encode()[:20].ljust(20)
    return struct.pack(FORMAT, book_id, title, author, price)
def unpack_record(record):
    book_id, title, author, price = struct.unpack(FORMAT, record)
    return {
        "id": book_id,
        "title": title.decode().strip(),
        "author": author.decode().strip(),
        "price": price
    }
def add_book():
    book_id = int(input("Enter the book id: "))
    title = input("Enter the book title: ")
    author = input("Enter the book author: ")
    price = float(input("Enter the book price: "))
    record = pack_record(book_id, title, author, price)
    with open(FILE_NAME, "ab") as file:
        file.write(record)
    print("Book added successfully")
def view_books():
    if not os.path.exists(FILE_NAME):
        print("No books found")
        return
    with open(FILE_NAME, "rb") as file:
        print("\n=== Book List ===\n")
        found = False
        while True:
            record = file.read(RECORD_SIZE)
            if not record:
                break
            if len(record) != RECORD_SIZE:
                continue
            book = unpack_record(record)
            found = True
            print(
                f'ID: {book["id"]}, '
                f'Title: {book["title"]}, '
                f'Author: {book["author"]}, '
                f'Price: {book["price"]:.2f}'
            )
        if not found:
            print("No books found")
def search_book():
    if not os.path.exists(FILE_NAME):
        print("No books found")
        return
    search = input("Enter the book title to search: ").lower()
    found = False
    with open(FILE_NAME, "rb") as file:
        while True:
            record = file.read(RECORD_SIZE)
            if not record:
                break
            if len(record) != RECORD_SIZE:
                continue
            book = unpack_record(record)
            if search in book["title"].lower():
                found = True
                print("\nBook found")
                print(f'ID: {book["id"]}')
                print(f'Title: {book["title"]}')
                print(f'Author: {book["author"]}')
                print(f'Price: {book["price"]:.2f}')
    if not found:
        print("Book not found")
def delete_book():
    if not os.path.exists(FILE_NAME):
        print("No books found")
        return
    delete_id = int(input("Enter the book id to delete: "))
    found = False
    with open(FILE_NAME, "rb") as file:
        records = file.readlines()
    with open(FILE_NAME, "wb") as file:
        for record in records:
            if len(record) != RECORD_SIZE:
                continue
            book = unpack_record(record)
            if book["id"] == delete_id:
                found = True
            else:
                file.write(record)
    if found:
        print("Book deleted successfully")
    else:
        print("Book not found")