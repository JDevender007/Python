"""
models.py

Database models for Banking System.
"""

from datetime import datetime

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import relationship

from database import Base


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    account_number = Column(String(20), unique=True, nullable=False, index=True)
    account_holder = Column(String(100), nullable=False)
    account_type = Column(String(30), nullable=False)
    balance = Column(Float, nullable=False, default=0.0)
    phone = Column(String(15), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    transactions = relationship(
        "Transaction",
        back_populates="account",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return (
            f"<Account("
            f"id={self.id}, "
            f"account_number='{self.account_number}', "
            f"account_holder='{self.account_holder}', "
            f"balance={self.balance})>"
        )


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    transaction_type = Column(String(20), nullable=False)
    amount = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    account = relationship("Account", back_populates="transactions")

    def __repr__(self):
        return (
            f"<Transaction("
            f"id={self.id}, "
            f"account_id={self.account_id}, "
            f"type='{self.transaction_type}', "
            f"amount={self.amount})>"
        )