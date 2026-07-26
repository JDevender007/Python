"""
Business logic for Inventory Management System.
"""

from sqlalchemy import asc

from database import Base
from database import engine
from database import get_session
from models import Item

Base.metadata.create_all(bind=engine)

class InventoryService:
    def __init__(self) -> None:
        self.session = get_session()

    def add_item(
        self,
        item_name: str,
        category: str,
        quantity: int,
        price: float,
        supplier: str,
    ) -> None:
        existing_item = (
            self.session.query(Item)
            .filter(Item.item_name == item_name)
            .first()
        )

        if existing_item:
            print("\nItem already exists.")
            return

        item = Item(
            item_name=item_name,
            category=category.title(),
            quantity=quantity,
            price=price,
            supplier=supplier,
        )

        self.session.add(item)
        self.session.commit()

        print("\nItem added successfully.")

    def view_items(self) -> None:
        items = (
            self.session.query(Item)
            .order_by(Item.item_name)
            .all()
        )

        if not items:
            print("\nNo items found.")
            return

        for item in items:
            print("-" * 50)
            print(f"ID         : {item.id}")
            print(f"Item Name  : {item.item_name}")
            print(f"Category   : {item.category}")
            print(f"Quantity   : {item.quantity}")
            print(f"Price      : ₹{item.price:.2f}")
            print(f"Supplier   : {item.supplier}")
            print(f"Created At : {item.created_at}")

    def search_item(self, keyword: str) -> None:
        item = (
            self.session.query(Item)
            .filter(
                (Item.item_name.ilike(f"%{keyword}%"))
                | (Item.category.ilike(f"%{keyword}%"))
                | (Item.supplier.ilike(f"%{keyword}%"))
            )
            .first()
        )

        if not item:
            print("\nItem not found.")
            return

        print("-" * 50)
        print(f"ID         : {item.id}")
        print(f"Item Name  : {item.item_name}")
        print(f"Category   : {item.category}")
        print(f"Quantity   : {item.quantity}")
        print(f"Price      : ₹{item.price:.2f}")
        print(f"Supplier   : {item.supplier}")
        print(f"Created At : {item.created_at}")

    def update_item(
        self,
        item_id: int,
        item_name: str,
        category: str,
        quantity: int,
        price: float,
        supplier: str,
    ) -> None:
        item = (
            self.session.query(Item)
            .filter(Item.id == item_id)
            .first()
        )

        if not item:
            print("\nItem not found.")
            return

        item.item_name = item_name
        item.category = category.title()
        item.quantity = quantity
        item.price = price
        item.supplier = supplier

        self.session.commit()

        print("\nItem updated successfully.")

    def delete_item(self, item_id: int) -> None:
        item = (
            self.session.query(Item)
            .filter(Item.id == item_id)
            .first()
        )

        if not item:
            print("\nItem not found.")
            return

        self.session.delete(item)
        self.session.commit()

        print("\nItem deleted successfully.")

    def stock_in(self, item_id: int, quantity: int) -> None:
        item = (
            self.session.query(Item)
            .filter(Item.id == item_id)
            .first()
        )

        if not item:
            print("\nItem not found.")
            return

        item.quantity += quantity
        self.session.commit()

        print("\nStock updated successfully.")

    def stock_out(self, item_id: int, quantity: int) -> None:
        item = (
            self.session.query(Item)
            .filter(Item.id == item_id)
            .first()
        )

        if not item:
            print("\nItem not found.")
            return

        if quantity > item.quantity:
            print("\nInsufficient stock.")
            return

        item.quantity -= quantity
        self.session.commit()

        print("\nStock reduced successfully.")

    def low_stock_alert(self, threshold: int = 5) -> None:
        items = (
            self.session.query(Item)
            .filter(Item.quantity <= threshold)
            .order_by(asc(Item.quantity))
            .all()
        )

        if not items:
            print("\nNo low stock items found.")
            return

        print("\nLow Stock Items")
        print("-" * 50)

        for item in items:
            print(f"{item.id} | {item.item_name} | Qty: {item.quantity}")

    def total_items(self) -> None:
        total = self.session.query(Item).count()
        print(f"\nTotal Items : {total}")

    def close(self) -> None:
        self.session.close()