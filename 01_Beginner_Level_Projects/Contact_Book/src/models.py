"""
Database models for Contact Book.
"""

from datetime import datetime

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import String

from database import Base

class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)

    first_name = Column(String(50), nullable=False)

    last_name = Column(String(50), nullable=False)

    phone = Column(String(15), unique=True, nullable=False)

    email = Column(String(100), unique=True, nullable=False)

    address = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return (
            f"<Contact("
            f"id={self.id}, "
            f"name={self.first_name} {self.last_name}, "
            f"phone={self.phone})>"
        )