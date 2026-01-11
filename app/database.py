import sqlite3
import os
from contextlib import contextmanager
from typing import Generator

# Database configuration
DATABASE_PATH = os.path.join(os.path.dirname(__file__), "data", "shopping.db")


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for database connections"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # This enables column access by name
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Initialize the database with required tables"""
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                quantity INTEGER DEFAULT 1,
                completed BOOLEAN DEFAULT 0
            )
        """
        )
        conn.commit()


def create_sample_data():
    """Create some sample data for testing"""
    with get_db() as conn:
        # Check if we already have data
        cursor = conn.execute("SELECT COUNT(*) FROM items")
        count = cursor.fetchone()[0]

        # Only create sample data if the database is completely empty
        if count == 0:
            sample_items = [
                ("Milk", 1, False),
                ("Bread", 2, False),
                ("Eggs", 12, False),
                ("Apples", 6, True),
            ]

            conn.executemany(
                "INSERT INTO items (name, quantity, completed) VALUES (?, ?, ?)",
                sample_items,
            )
            conn.commit()


def reset_database():
    """Reset the database by clearing all items"""
    with get_db() as conn:
        conn.execute("DELETE FROM items")
        conn.commit()
