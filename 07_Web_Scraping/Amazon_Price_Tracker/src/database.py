from __future__ import annotations

import sqlite3

from src.config import DATABASE_FILE
from src.logger import logger


class Database:

    def __init__(self):

        self.connection = sqlite3.connect(DATABASE_FILE)

        self.connection.row_factory = sqlite3.Row

        self.create_tables()

    def create_tables(self):

        cursor = self.connection.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                current_price REAL DEFAULT 0,
                target_price REAL DEFAULT 0,
                lowest_price REAL DEFAULT 0,
                availability TEXT DEFAULT 'Unknown',
                last_checked TEXT,
                created_at TEXT NOT NULL
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                price REAL NOT NULL,
                checked_at TEXT NOT NULL,
                FOREIGN KEY(product_id)
                REFERENCES products(id)
                ON DELETE CASCADE
            )
            """
        )

        self.connection.commit()

        logger.info("Database tables initialized")

    def add_product(
        self,
        name,
        url,
        current_price,
        target_price,
        lowest_price,
        availability,
        timestamp,
    ):

        cursor = self.connection.cursor()

        cursor.execute(
            """
            INSERT INTO products (
                name,
                url,
                current_price,
                target_price,
                lowest_price,
                availability,
                last_checked,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                url,
                current_price,
                target_price,
                lowest_price,
                availability,
                timestamp,
                timestamp,
            ),
        )

        product_id = cursor.lastrowid

        self.connection.commit()

        logger.info(
            "Product added: %s",
            name,
        )

        return product_id

    def update_product(
        self,
        product_id,
        current_price,
        lowest_price,
        availability,
        timestamp,
    ):

        cursor = self.connection.cursor()

        cursor.execute(
            """
            UPDATE products
            SET current_price = ?,
                lowest_price = ?,
                availability = ?,
                last_checked = ?
            WHERE id = ?
            """,
            (
                current_price,
                lowest_price,
                availability,
                timestamp,
                product_id,
            ),
        )

        self.connection.commit()

    def add_price_history(
        self,
        product_id,
        price,
        timestamp,
    ):

        cursor = self.connection.cursor()

        cursor.execute(
            """
            INSERT INTO price_history (
                product_id,
                price,
                checked_at
            )
            VALUES (?, ?, ?)
            """,
            (
                product_id,
                price,
                timestamp,
            ),
        )

        self.connection.commit()

    def get_products(self):

        cursor = self.connection.cursor()

        cursor.execute(
            """
            SELECT *
            FROM products
            ORDER BY id DESC
            """
        )

        return cursor.fetchall()

    def get_product(
        self,
        product_id,
    ):

        cursor = self.connection.cursor()

        cursor.execute(
            """
            SELECT *
            FROM products
            WHERE id = ?
            """,
            (product_id,),
        )

        return cursor.fetchone()

    def get_price_history(
        self,
        product_id,
    ):

        cursor = self.connection.cursor()

        cursor.execute(
            """
            SELECT price, checked_at
            FROM price_history
            WHERE product_id = ?
            ORDER BY checked_at ASC
            """,
            (product_id,),
        )

        return cursor.fetchall()

    def delete_product(
        self,
        product_id,
    ):

        cursor = self.connection.cursor()

        cursor.execute(
            """
            DELETE FROM price_history
            WHERE product_id = ?
            """,
            (product_id,),
        )

        cursor.execute(
            """
            DELETE FROM products
            WHERE id = ?
            """,
            (product_id,),
        )

        self.connection.commit()

    def close(self):

        if self.connection:

            self.connection.close()

            logger.info("Database connection closed")
