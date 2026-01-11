#!/usr/bin/env python3
"""
Unit tests for the Shared Shopping List API using unittest
Tests all CRUD operations and verifies SQLite integration
"""

import unittest
import requests
import os
import sys

# Import the server manager
from server_manager import TestServerManager, check_prerequisites

# Configuration
BASE_URL = "http://localhost:8000"
TEST_TIMEOUT = 10  # seconds


class TestShoppingListAPI(unittest.TestCase):
    """Test cases for the Shopping List API"""

    test_item_id = None  # Class variable to store test item ID

    @classmethod
    def setUpClass(cls):
        """Setup server before running tests"""
        print("🧪 Starting Shared Shopping List API Tests")
        print("=" * 50)
        print(
            "Using unittest framework to test FastAPI backend with SQLite integration"
        )
        print()

        # Check prerequisites
        if not check_prerequisites("api"):
            sys.exit(1)

        # Setup server manager
        cls.server_manager = TestServerManager.for_api_tests()

        # Start server if not already running
        if not cls.server_manager.check_server_running():
            print("🚀 Starting FastAPI server...")
            success = cls.server_manager.start_api_server(timeout=30)
            if not success:
                raise RuntimeError("Failed to start API server")

            # Wait for server to be fully ready
            if not cls.server_manager.wait_for_server_boot(timeout=30):
                raise RuntimeError("Server not ready after boot")

        print("✅ Server is running and ready for tests")

        # Clear all items to start with clean state
        try:
            response = requests.delete(f"{BASE_URL}/items", timeout=TEST_TIMEOUT)
            if response.status_code != 200:
                print(
                    f"⚠️  Warning: Could not clear items, status {response.status_code}"
                )
        except Exception as e:
            print(f"⚠️  Warning: Could not clear items: {e}")

    @classmethod
    def ensure_test_item_exists(cls):
        """Ensure a test item exists for dependent tests"""
        if cls.test_item_id is None:
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
        self.ensure_test_item_exists()

        response = requests.get(
            f"{BASE_URL}/items/{TestShoppingListAPI.test_item_id}", timeout=TEST_TIMEOUT
        )
        self.assertEqual(response.status_code, 200)

        item = response.json()
        self.assertEqual(item["id"], TestShoppingListAPI.test_item_id)
        self.assertEqual(item["name"], "Test Item")

    def test_toggle_item(self):
        """Test toggling an item's completion status"""
        self.ensure_test_item_exists()

        response = requests.patch(
            f"{BASE_URL}/items/{TestShoppingListAPI.test_item_id}/toggle",
            timeout=TEST_TIMEOUT,
        )
        self.assertEqual(response.status_code, 200)

        result = response.json()
        self.assertEqual(result["id"], TestShoppingListAPI.test_item_id)
        self.assertEqual(result["completed"], True)

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

    def test_delete_item(self):
        """Test deleting an item
        Test that deleted item returns 404"""
        self.ensure_test_item_exists()
        item_id = TestShoppingListAPI.test_item_id

        response = requests.delete(f"{BASE_URL}/items/{item_id}", timeout=TEST_TIMEOUT)
        self.assertEqual(response.status_code, 200)

        result = response.json()
        self.assertIn("message", result)

        # Clear the test item ID since it's deleted
        TestShoppingListAPI.test_item_id = None

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


def run_tests():
    """Run the test suite"""
    print("🧪 Starting Shared Shopping List API Tests")
    print("=" * 50)
    print("Using unittest framework to test FastAPI backend with SQLite integration")
    print()

    # Check if required files exist
    required_files = ["app/main.py", "app/database.py", "pyproject.toml"]
    for file_path in required_files:
        if not os.path.exists(file_path):
            print(f"❌ Required file missing: {file_path}")
            sys.exit(1)

    # Run the tests
    unittest.main(verbosity=2)

    print("=" * 50)
    print("🎉 API Test suite completed!")


if __name__ == "__main__":
    run_tests()
