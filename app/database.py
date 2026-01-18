import sqlite3
import os
from contextlib import contextmanager
from typing import Generator


def get_port() -> int:
    """Get the port number from environment variable"""
    return int(os.getenv("PORT", 8000))


# Database configuration
DATABASE_PATH = os.path.join(os.path.dirname(__file__), "data", f"data_{get_port()}.db")


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
        # Create lists table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS lists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL DEFAULT 'Shopping List',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Create items table with list_id foreign key
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                list_id INTEGER NOT NULL DEFAULT 1,
                name TEXT NOT NULL,
                quantity INTEGER DEFAULT 1,
                completed BOOLEAN DEFAULT 0,
                order_index INTEGER DEFAULT 0,
                FOREIGN KEY (list_id) REFERENCES lists (id)
            )
        """
        )
        conn.commit()


def create_default_list():
    """Create a default list if none exists"""
    with get_db() as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM lists")
        count = cursor.fetchone()[0]

        if count == 0:
            conn.execute("INSERT INTO lists (name) VALUES (?)", ("Shopping List",))
            conn.commit()
            return cursor.lastrowid
        else:
            cursor = conn.execute("SELECT id FROM lists LIMIT 1")
            return cursor.fetchone()[0]


def create_sample_data():
    """Create some sample data for testing"""
    with get_db() as conn:
        # Check if we already have data
        cursor = conn.execute("SELECT COUNT(*) FROM items")
        count = cursor.fetchone()[0]

        # Only create sample data if the database is completely empty
        if count == 0:
            # Ensure we have a default list
            list_id = create_default_list()

            sample_items = [
                (list_id, "Milk", 1, False, 1),
                (list_id, "Bread", 2, False, 2),
                (list_id, "Eggs", 12, False, 3),
                (list_id, "Apples", 6, True, 4),
            ]

            conn.executemany(
                "INSERT INTO items (list_id, name, quantity, completed, order_index) VALUES (?, ?, ?, ?, ?)",
                sample_items,
            )
            conn.commit()


def reset_database():
    """Reset the database by clearing all items"""
    with get_db() as conn:
        conn.execute("DELETE FROM items")
        conn.commit()
