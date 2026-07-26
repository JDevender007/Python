"""
Database models.
"""

from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String

from database import Base

class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)

    title = Column(String(150), nullable=False)

    author = Column(String(100), nullable=False)

    isbn = Column(String(20), unique=True, nullable=False)

    quantity = Column(Integer, nullable=False)

    available = Column(Integer, nullable=False)

    issued = Column(Boolean, default=False)

    def __repr__(self):
        return f"<Book {self.title}>"