"""
Entry point for Inventory Management System.
"""

from inventory_service import InventoryService
from validator import Validator
from utils import Utils

service = InventoryService()

def add_item() -> None:
    print("\nAdd Item")

    item_name = input("Item Name : ").strip()
    while not Validator.validate_name(item_name):
        print("Invalid item name.")
        item_name = input("Item Name : ").strip()

    category = input("Category : ").strip()
    while not Validator.validate_category(category):
        print("Invalid category.")
        category = input("Category : ").strip()

    quantity = input("Quantity : ").strip()
    while not Validator.validate_quantity(quantity):
        print("Quantity must be a non-negative integer.")
        quantity = input("Quantity : ").strip()

    price = input("Price : ").strip()
    while not Validator.validate_price(price):
        print("Price must be a valid non-negative number.")
        price = input("Price : ").strip()

    supplier = input("Supplier : ").strip()
    while not Validator.validate_supplier(supplier):
        print("Invalid supplier name.")
        supplier = input("Supplier : ").strip()

    service.add_item(
        item_name,
        category,
        int(quantity),
        float(price),
        supplier,
    )

def update_item() -> None:
    item_id = int(input("\nItem ID : "))

    item_name = input("Item Name : ").strip()
    while not Validator.validate_name(item_name):
        print("Invalid item name.")
        item_name = input("Item Name : ").strip()

    category = input("Category : ").strip()
    while not Validator.validate_category(category):
        print("Invalid category.")
        category = input("Category : ").strip()

    quantity = input("Quantity : ").strip()
    while not Validator.validate_quantity(quantity):
        print("Quantity must be a non-negative integer.")
        quantity = input("Quantity : ").strip()

    price = input("Price : ").strip()
    while not Validator.validate_price(price):
        print("Price must be a valid non-negative number.")
        price = input("Price : ").strip()

    supplier = input("Supplier : ").strip()
    while not Validator.validate_supplier(supplier):
        print("Invalid supplier name.")
        supplier = input("Supplier : ").strip()

    service.update_item(
        item_id,
        item_name,
        category,
        int(quantity),
        float(price),
        supplier,
    )

def search_item() -> None:
    keyword = input("\nSearch : ").strip()
    service.search_item(keyword)

def stock_in() -> None:
    item_id = int(input("\nItem ID : "))
    quantity = input("Quantity to add : ").strip()

    while not Validator.validate_quantity(quantity):
        print("Enter a valid non-negative integer.")
        quantity = input("Quantity to add : ").strip()

    service.stock_in(item_id, int(quantity))

def stock_out() -> None:
    item_id = int(input("\nItem ID : "))
    quantity = input("Quantity to remove : ").strip()

    while not Validator.validate_quantity(quantity):
        print("Enter a valid non-negative integer.")
        quantity = input("Quantity to remove : ").strip()

    service.stock_out(item_id, int(quantity))

def main() -> None:
    while True:
        Utils.header()
        Utils.menu()

        choice = input("\nEnter Choice : ").strip()

        if choice == "1":
            add_item()
        elif choice == "2":
            service.view_items()
        elif choice == "3":
            search_item()
        elif choice == "4":
            update_item()
        elif choice == "5":
            item_id = int(input("\nItem ID : "))
            service.delete_item(item_id)
        elif choice == "6":
            stock_in()
        elif choice == "7":
            stock_out()
        elif choice == "8":
            service.low_stock_alert()
        elif choice == "9":
            service.total_items()
        elif choice == "10":
            print("\nThank you for using Inventory Management System.")
            service.close()
            break
        else:
            print("\nInvalid choice.")

        Utils.pause()

if __name__ == "__main__":
    main()