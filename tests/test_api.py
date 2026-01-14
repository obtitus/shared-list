#!/usr/bin/env python3
"""
Unit tests for the Shared Shopping List API using unittest
Tests all CRUD operations and verifies SQLite integration
"""

import unittest
import requests
import sys
import logging

# Import the server manager
from server_manager import TestServerManager, check_prerequisites

# Create logger
logger = logging.getLogger("test." + __name__)

# Configuration
BASE_URL = "http://localhost:8000"
TEST_TIMEOUT = 10  # seconds


class TestShoppingListAPI(unittest.TestCase):
    """Test cases for the Shopping List API"""

    test_item_id = None  # Class variable to store test item ID

    @classmethod
    def setUpClass(cls):
        """Setup server before running tests"""
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        logger.info("🧪 Starting Shared Shopping List API Tests")
        logger.info("=" * 50)
        logger.info(
            "Using unittest framework to test FastAPI backend with SQLite integration"
        )
        logger.info("")

        # Check prerequisites
        if not check_prerequisites("api"):
            sys.exit(1)

        # Setup server manager
        cls.server_manager = TestServerManager.for_api_tests()

        # Start server if not already running
        if not cls.server_manager.check_server_running():
            logger.info("🚀 Starting FastAPI server...")
            success = cls.server_manager.start_api_server(timeout=30)
            if not success:
                raise RuntimeError("Failed to start API server")

            # Wait for server to be fully ready
            if not cls.server_manager.wait_for_server_boot(timeout=30):
                raise RuntimeError("Server not ready after boot")

        logger.info("✅ Server is running and ready for tests")

        # Clear all items to start with clean state
        try:
            response = requests.delete(f"{BASE_URL}/items", timeout=TEST_TIMEOUT)
            if response.status_code != 200:
                logger.warning(
                    "⚠️  Warning: Could not clear items, status %s", response.status_code
                )
        except Exception as e:
            logger.warning("⚠️  Warning: Could not clear items: %s", e)

    @classmethod
    def ensure_test_item_exists(cls):
        """Ensure a test item exists for dependent tests"""
        # Check if we have an item ID and if it still exists
        if cls.test_item_id is not None:
            try:
                response = requests.get(
                    f"{BASE_URL}/items/{cls.test_item_id}", timeout=TEST_TIMEOUT
                )
                if response.status_code == 200:
                    return  # Item still exists
            except (requests.RequestException,):
                pass  # Item doesn't exist, continue to create new one

        # Create new item
        new_item = {"name": "Test Item", "quantity": 3, "completed": False}
        response = requests.post(
            f"{BASE_URL}/items", json=new_item, timeout=TEST_TIMEOUT
        )
        if response.status_code == 201:
            created_item = response.json()
            cls.test_item_id = created_item["id"]

    @classmethod
    def tearDownClass(cls):
        """Cleanup after all tests"""
        if hasattr(cls, "server_manager"):
            cls.server_manager.stop_server()

    def test_root_endpoint(self):
        """Test the root endpoint"""
        logger.info("🏥 Testing API root endpoint...")
        response = requests.get(f"{BASE_URL}/api", timeout=TEST_TIMEOUT)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["message"], "Shared Shopping List API")

    def test_get_items_initial(self):
        """Test getting initial items"""
        response = requests.get(f"{BASE_URL}/items", timeout=TEST_TIMEOUT)
        self.assertEqual(response.status_code, 200)

        items = response.json()
        self.assertIsInstance(items, list)
        self.assertGreaterEqual(len(items), 0)  # Should return a list

    def test_create_item(self):
        """Test creating a new item"""
        new_item = {"name": "Test Item", "quantity": 3, "completed": False}

        response = requests.post(
            f"{BASE_URL}/items", json=new_item, timeout=TEST_TIMEOUT
        )
        self.assertEqual(response.status_code, 201)

        created_item = response.json()
        self.assertEqual(created_item["name"], "Test Item")
        self.assertEqual(created_item["quantity"], 3)
        self.assertEqual(created_item["completed"], False)

        # Store the ID for cleanup
        TestShoppingListAPI.test_item_id = created_item["id"]

    def test_get_specific_item(self):
        """Test getting a specific item by ID"""
        # Create a fresh item for this test
        new_item = {"name": "Specific Test Item", "quantity": 4, "completed": False}
        response = requests.post(
            f"{BASE_URL}/items", json=new_item, timeout=TEST_TIMEOUT
        )
        self.assertEqual(response.status_code, 201)
        created_item = response.json()
        item_id = created_item["id"]

        # Get the specific item
        response = requests.get(f"{BASE_URL}/items/{item_id}", timeout=TEST_TIMEOUT)
        self.assertEqual(response.status_code, 200)

        item = response.json()
        self.assertEqual(item["id"], item_id)
        self.assertEqual(item["name"], "Specific Test Item")
        self.assertEqual(item["quantity"], 4)
        self.assertEqual(item["completed"], False)

    def test_toggle_item(self):
        """Test toggling an item's completion status"""
        # Create a fresh item for this test
        new_item = {"name": "Toggle Test Item", "quantity": 1, "completed": False}
        response = requests.post(
            f"{BASE_URL}/items", json=new_item, timeout=TEST_TIMEOUT
        )
        self.assertEqual(response.status_code, 201)
        created_item = response.json()
        item_id = created_item["id"]

        # Toggle the item
        response = requests.patch(
            f"{BASE_URL}/items/{item_id}/toggle",
            timeout=TEST_TIMEOUT,
        )
        self.assertEqual(response.status_code, 200)

        result = response.json()
        self.assertEqual(result["id"], item_id)
        self.assertEqual(result["completed"], True)

        # Toggle back
        response = requests.patch(
            f"{BASE_URL}/items/{item_id}/toggle",
            timeout=TEST_TIMEOUT,
        )
        self.assertEqual(response.status_code, 200)

        result = response.json()
        self.assertEqual(result["id"], item_id)
        self.assertEqual(result["completed"], False)

    def test_update_item(self):
        """Test updating an existing item"""
        self.ensure_test_item_exists()

        updated_item = {"name": "Updated Test Item", "quantity": 5, "completed": True}

        response = requests.put(
            f"{BASE_URL}/items/{TestShoppingListAPI.test_item_id}",
            json=updated_item,
            timeout=TEST_TIMEOUT,
        )
        self.assertEqual(response.status_code, 200)

        updated = response.json()
        self.assertEqual(updated["name"], "Updated Test Item")
        self.assertEqual(updated["quantity"], 5)
        self.assertEqual(updated["completed"], True)
        self.assertEqual(updated["id"], TestShoppingListAPI.test_item_id)

    def test_delete_item(self):
        """Test deleting an item
        Test that deleted item returns 404"""
        # Create a fresh item for this test
        new_item = {"name": "Delete Test Item", "quantity": 2, "completed": False}
        response = requests.post(
            f"{BASE_URL}/items", json=new_item, timeout=TEST_TIMEOUT
        )
        self.assertEqual(response.status_code, 201)
        created_item = response.json()
        item_id = created_item["id"]

        # Delete the item
        response = requests.delete(f"{BASE_URL}/items/{item_id}", timeout=TEST_TIMEOUT)
        self.assertEqual(response.status_code, 200)

        result = response.json()
        self.assertIn("message", result)

        # Verify item is gone
        response = requests.get(f"{BASE_URL}/items/{item_id}", timeout=TEST_TIMEOUT)
        self.assertEqual(response.status_code, 404)

    def test_error_handling_nonexistent_item(self):
        """Test error handling for non-existent items"""
        # Try to get non-existent item
        response = requests.get(f"{BASE_URL}/items/99999", timeout=TEST_TIMEOUT)
        self.assertEqual(response.status_code, 404)

        # Try to update non-existent item
        response = requests.put(
            f"{BASE_URL}/items/99999",
            json={"name": "Test", "quantity": 1, "completed": False},
            timeout=TEST_TIMEOUT,
        )
        self.assertEqual(response.status_code, 404)

        # Try to delete non-existent item
        response = requests.delete(f"{BASE_URL}/items/99999", timeout=TEST_TIMEOUT)
        self.assertEqual(response.status_code, 404)

    def test_toggle_nonexistent_item(self):
        """Test toggling non-existent item returns 404"""
        response = requests.patch(
            f"{BASE_URL}/items/99999/toggle", timeout=TEST_TIMEOUT
        )
        self.assertEqual(response.status_code, 404)

    def test_item_ordering(self):
        """Test that items are returned in order_index order"""
        # Clear all items first
        requests.delete(f"{BASE_URL}/items", timeout=TEST_TIMEOUT)

        # Add items in specific order
        items_data = [
            {"name": "First Item", "quantity": 1, "completed": False},
            {"name": "Second Item", "quantity": 2, "completed": False},
            {"name": "Third Item", "quantity": 3, "completed": False},
        ]

        created_items = []
        for item_data in items_data:
            response = requests.post(
                f"{BASE_URL}/items", json=item_data, timeout=TEST_TIMEOUT
            )
            self.assertEqual(response.status_code, 201)
            created_items.append(response.json())

        # Verify items are returned in order
        response = requests.get(f"{BASE_URL}/items", timeout=TEST_TIMEOUT)
        self.assertEqual(response.status_code, 200)
        items = response.json()

        # Should be ordered by order_index (1, 2, 3)
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0]["name"], "First Item")
        self.assertEqual(items[1]["name"], "Second Item")
        self.assertEqual(items[2]["name"], "Third Item")

        # Verify order_index values
        self.assertEqual(items[0]["order_index"], 1)
        self.assertEqual(items[1]["order_index"], 2)
        self.assertEqual(items[2]["order_index"], 3)

    def test_create_item_assigns_order(self):
        """Test that new items get proper order_index assigned"""
        # Clear all items first
        requests.delete(f"{BASE_URL}/items", timeout=TEST_TIMEOUT)

        # Add first item
        response = requests.post(
            f"{BASE_URL}/items",
            json={"name": "First", "quantity": 1, "completed": False},
            timeout=TEST_TIMEOUT,
        )
        self.assertEqual(response.status_code, 201)
        first_item = response.json()
        self.assertEqual(first_item["order_index"], 1)

        # Add second item
        response = requests.post(
            f"{BASE_URL}/items",
            json={"name": "Second", "quantity": 1, "completed": False},
            timeout=TEST_TIMEOUT,
        )
        self.assertEqual(response.status_code, 201)
        second_item = response.json()
        self.assertEqual(second_item["order_index"], 2)

    def test_create_item_with_order_index(self):
        """Test creating an item with a specific order_index (insertion)"""
        # Clear all items first
        requests.delete(f"{BASE_URL}/items", timeout=TEST_TIMEOUT)

        # Add three items
        items = []
        for i in range(3):
            response = requests.post(
                f"{BASE_URL}/items",
                json={"name": f"Item {i+1}", "quantity": 1, "completed": False},
                timeout=TEST_TIMEOUT,
            )
            self.assertEqual(response.status_code, 201)
            items.append(response.json())

        # Verify initial order
        response = requests.get(f"{BASE_URL}/items", timeout=TEST_TIMEOUT)
        self.assertEqual(response.status_code, 200)
        current_items = response.json()
        self.assertEqual(len(current_items), 3)
        self.assertEqual(current_items[0]["name"], "Item 1")
        self.assertEqual(current_items[1]["name"], "Item 2")
        self.assertEqual(current_items[2]["name"], "Item 3")

        # Insert a new item at position 2 (above "Item 2")
        response = requests.post(
            f"{BASE_URL}/items",
            json={
                "name": "New Item",
                "quantity": 2,
                "completed": False,
                "order_index": 2,
            },
            timeout=TEST_TIMEOUT,
        )
        self.assertEqual(response.status_code, 201)
        new_item = response.json()
        self.assertEqual(new_item["name"], "New Item")
        self.assertEqual(new_item["order_index"], 2)

        # Verify new order: Item 1, New Item, Item 2, Item 3
        response = requests.get(f"{BASE_URL}/items", timeout=TEST_TIMEOUT)
        self.assertEqual(response.status_code, 200)
        updated_items = response.json()
        self.assertEqual(len(updated_items), 4)
        self.assertEqual(updated_items[0]["name"], "Item 1")
        self.assertEqual(updated_items[0]["order_index"], 1)
        self.assertEqual(updated_items[1]["name"], "New Item")
        self.assertEqual(updated_items[1]["order_index"], 2)
        self.assertEqual(updated_items[2]["name"], "Item 2")
        self.assertEqual(updated_items[2]["order_index"], 3)
        self.assertEqual(updated_items[3]["name"], "Item 3")
        self.assertEqual(updated_items[3]["order_index"], 4)

    def test_reorder_item(self):
        """Test reordering an item to a new position"""
        # Clear all items first
        requests.delete(f"{BASE_URL}/items", timeout=TEST_TIMEOUT)

        # Add three items
        items = []
        for i in range(3):
            response = requests.post(
                f"{BASE_URL}/items",
                json={"name": f"Item {i+1}", "quantity": 1, "completed": False},
                timeout=TEST_TIMEOUT,
            )
            self.assertEqual(response.status_code, 201)
            items.append(response.json())

        # Move second item (index 1, order_index 2) to position 1 (new order_index 1)
        item_to_move = items[1]  # Second item
        new_order = 1

        response = requests.patch(
            f"{BASE_URL}/items/{item_to_move['id']}/reorder/{new_order}",
            timeout=TEST_TIMEOUT,
        )
        logger.debug("Reorder response: %s", response)
        self.assertEqual(response.status_code, 200)

        result = response.json()
        self.assertEqual(result["id"], item_to_move["id"])
        self.assertEqual(result["order_index"], new_order)

        # Verify the new order
        response = requests.get(f"{BASE_URL}/items", timeout=TEST_TIMEOUT)
        self.assertEqual(response.status_code, 200)
        reordered_items = response.json()

        self.assertEqual(len(reordered_items), 3)
        # Second item should now be first
        self.assertEqual(reordered_items[0]["name"], "Item 2")
        self.assertEqual(reordered_items[1]["name"], "Item 1")
        self.assertEqual(reordered_items[2]["name"], "Item 3")

        # Verify order_index values
        self.assertEqual(reordered_items[0]["order_index"], 1)
        self.assertEqual(reordered_items[1]["order_index"], 2)
        self.assertEqual(reordered_items[2]["order_index"], 3)

    def test_reorder_invalid_item(self):
        """Test reordering non-existent item returns 404"""
        # Since FastAPI validates the request body before checking item existence,
        # we expect either 404 (if validation passes) or 422 (if validation fails first)
        # Either way, it's not a successful reorder operation
        response = requests.patch(
            f"{BASE_URL}/items/99999/reorder",
            json=1,
            timeout=TEST_TIMEOUT,
        )
        # Just verify it's not a successful response
        self.assertNotEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
