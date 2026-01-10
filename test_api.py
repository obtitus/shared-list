#!/usr/bin/env python3
"""
Unit tests for the Shared Shopping List API using unittest
Tests all CRUD operations and verifies SQLite integration
"""

import unittest
import requests
import time
import subprocess
import os
import sys

# Configuration
BASE_URL = "http://localhost:8000"
TEST_TIMEOUT = 10  # seconds


class TestShoppingListAPI(unittest.TestCase):
    """Test cases for the Shopping List API"""

    @classmethod
    def setUpClass(cls):
        """Start the server before running tests"""
        print("🚀 Starting FastAPI server...")
        try:
            # Start server in background
            cls.server_process = subprocess.Popen(
                ["uv", "run", "python", "app/main.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Wait for server to start
            time.sleep(3)

            # Check if server started successfully
            if cls.server_process.poll() is not None:
                stdout, stderr = cls.server_process.communicate()
                print("❌ Server failed to start:")
                print(f"STDOUT: {stdout}")
                print(f"STDERR: {stderr}")
                raise Exception("Server failed to start")

            print("✅ Server started successfully")
        except Exception as e:
            print(f"❌ Failed to start server: {e}")
            raise

    @classmethod
    def tearDownClass(cls):
        """Stop the server after all tests"""
        if hasattr(cls, "server_process") and cls.server_process:
            print("🛑 Stopping server...")
            try:
                cls.server_process.terminate()
                cls.server_process.wait(timeout=5)
                print("✅ Server stopped")
            except subprocess.TimeoutExpired:
                cls.server_process.kill()
                print("⚠️  Server killed (timeout)")
            except Exception as e:
                print(f"❌ Error stopping server: {e}")

    def test_root_endpoint(self):
        """Test the root endpoint"""
        response = requests.get(f"{BASE_URL}/", timeout=TEST_TIMEOUT)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["message"], "Shared Shopping List API")

    def test_get_items_initial(self):
        """Test getting initial items (should have sample data)"""
        response = requests.get(f"{BASE_URL}/items", timeout=TEST_TIMEOUT)
        self.assertEqual(response.status_code, 200)

        items = response.json()
        self.assertIsInstance(items, list)
        self.assertGreaterEqual(len(items), 4)  # Should have sample data

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
        self.test_item_id = created_item["id"]

    def test_get_specific_item(self):
        """Test getting a specific item by ID"""
        if not hasattr(self, "test_item_id"):
            self.skipTest("No test item created")

        response = requests.get(
            f"{BASE_URL}/items/{self.test_item_id}", timeout=TEST_TIMEOUT
        )
        self.assertEqual(response.status_code, 200)

        item = response.json()
        self.assertEqual(item["id"], self.test_item_id)
        self.assertEqual(item["name"], "Test Item")

    def test_toggle_item(self):
        """Test toggling an item's completion status"""
        if not hasattr(self, "test_item_id"):
            self.skipTest("No test item created")

        response = requests.patch(
            f"{BASE_URL}/items/{self.test_item_id}/toggle", timeout=TEST_TIMEOUT
        )
        self.assertEqual(response.status_code, 200)

        result = response.json()
        self.assertEqual(result["id"], self.test_item_id)
        self.assertEqual(result["completed"], True)

    def test_update_item(self):
        """Test updating an existing item"""
        if not hasattr(self, "test_item_id"):
            self.skipTest("No test item created")

        updated_item = {"name": "Updated Test Item", "quantity": 5, "completed": True}

        response = requests.put(
            f"{BASE_URL}/items/{self.test_item_id}",
            json=updated_item,
            timeout=TEST_TIMEOUT,
        )
        self.assertEqual(response.status_code, 200)

        updated = response.json()
        self.assertEqual(updated["name"], "Updated Test Item")
        self.assertEqual(updated["quantity"], 5)
        self.assertEqual(updated["completed"], True)

    def test_delete_item(self):
        """Test deleting an item"""
        if not hasattr(self, "test_item_id"):
            self.skipTest("No test item created")

        response = requests.delete(
            f"{BASE_URL}/items/{self.test_item_id}", timeout=TEST_TIMEOUT
        )
        self.assertEqual(response.status_code, 200)

        result = response.json()
        self.assertIn("message", result)

    def test_item_deleted_verification(self):
        """Test that deleted item returns 404"""
        if not hasattr(self, "test_item_id"):
            self.skipTest("No test item created")

        response = requests.get(
            f"{BASE_URL}/items/{self.test_item_id}", timeout=TEST_TIMEOUT
        )
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
    unittest.main(verbosity=2, exit=False)

    print("=" * 50)
    print("🎉 Test suite completed!")


if __name__ == "__main__":
    run_tests()
