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
    # Get limits from environment
    max_db_pages = int(os.getenv("MAX_DB_PAGES", 100))
    max_name_length = int(os.getenv("MAX_ITEM_NAME_LENGTH", 100))

    with get_db() as conn:
        # Set performance and security PRAGMAs
        conn.execute(f"PRAGMA page_size = 4096")
        conn.execute(f"PRAGMA max_page_count = {max_db_pages}")

        # Create lists table
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS lists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL DEFAULT 'Shopping List' CHECK(length(name) <= {max_name_length}),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Create items table with list_id foreign key and constraints
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                list_id INTEGER NOT NULL DEFAULT 1,
                name TEXT NOT NULL CHECK(length(name) <= {max_name_length}),
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


def db_get_items(list_id: int):
    """Get the current list details"""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT id, name, quantity, completed, order_index FROM items WHERE list_id = ? ORDER BY order_index, id",
            (list_id,),
        )
        items = [dict(row) for row in cursor.fetchall()]

    return items


def assign_unique_order_indices(list_id: int):
    """Assign unique order_index values to items in the list"""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT id FROM items WHERE list_id = ? ORDER BY order_index",
            (list_id,),
        )
        items = cursor.fetchall()

        for index, item in enumerate(items):
            conn.execute(
                "UPDATE items SET order_index = ? WHERE id = ?",
                (index + 1, item["id"]),
            )
        conn.commit()

        # Return the updated list of items
    return db_get_items(list_id)
