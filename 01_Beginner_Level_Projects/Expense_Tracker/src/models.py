"""
models.py

Database models for Expense Tracker.
"""

from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Float
from sqlalchemy import Date

from datetime import date

from database import Base

class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)

    title = Column(
        String(100),
        nullable=False
    )

    category = Column(
        String(50),
        nullable=False
    )

    amount = Column(
        Float,
        nullable=False
    )

    expense_date = Column(
        Date,
        default=date.today
    )

    description = Column(
        String(255)
    )

    def __repr__(self):
        return (
            f"<Expense("
            f"id={self.id}, "
            f"title='{self.title}', "
            f"category='{self.category}', "
            f"amount={self.amount})>"
        )