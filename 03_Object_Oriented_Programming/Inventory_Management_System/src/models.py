"""
Database models for Inventory Management System.
"""

from datetime import datetime

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import Integer
from sqlalchemy import String

from database import Base

class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    item_name = Column(String(100), unique=True, nullable=False)
    category = Column(String(50), nullable=False)
    quantity = Column(Integer, nullable=False, default=0)
    price = Column(Float, nullable=False, default=0.0)
    supplier = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return (
            f"<Item("
            f"id={self.id}, "
            f"item_name='{self.item_name}', "
            f"category='{self.category}', "
            f"quantity={self.quantity}, "
            f"price={self.price})>"
        )