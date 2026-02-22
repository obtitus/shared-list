#!/usr/bin/env python3
"""
Unit tests for Docker setup verification using unittest
Tests Docker container build, run, and file tree structure
"""

import os
import sys
import unittest
import requests
import logging

# Import the server manager
from server_manager import ServerManager, check_prerequisites

# Create logger
logger = logging.getLogger("test." + os.path.basename(__file__))

# Configuration
PORT = 8011


class TestDockerSetup(unittest.TestCase):
    """Test cases for Docker container setup and file tree"""

    @classmethod
    def setUpClass(cls):
        """Setup server before running tests"""
        # Check prerequisites
        if not check_prerequisites("docker"):
            sys.exit(1)

        # Setup server manager
        cls.server_manager = ServerManager(port=PORT, server_type="docker")
        cls.server_manager.__enter__()
        cls.BASE_URL = cls.server_manager.base_url
        logger.info(f"🌐 Server is running {cls.BASE_URL}")

    @classmethod
    def tearDownClass(cls):
        """Cleanup after all tests"""
        if hasattr(cls, "server_manager"):
            cls.server_manager.__exit__()

    def test_api_health_check(self):
        """Test that the API is responding correctly from the container"""
        logger.info("🏥 Testing API health check...")

        # Test root endpoint
        response = requests.get(f"{self.BASE_URL}/api", timeout=10)
        self.assertEqual(response.status_code, 200, "Root endpoint failed")

        data = response.json()
        self.assertEqual(data["message"], "Shared Shopping List API", "Unexpected root response")
        logger.info("✅ Root endpoint working")

        # Test items endpoint
        response = requests.get(f"{self.BASE_URL}/items", timeout=10)
        self.assertEqual(response.status_code, 200, "Items endpoint failed")

        data = response.json()
        self.assertIn("items", data, "Items endpoint missing 'items' key")
        self.assertIn("repaired", data, "Items endpoint missing 'repaired' key")
        self.assertIsInstance(data["items"], list, "Items endpoint returned non-list for 'items'")
        self.assertIsInstance(data["repaired"], bool, "Items endpoint returned non-bool for 'repaired'")
        logger.info("✅ Items endpoint working, found %d items", len(data["items"]))


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s[%(levelname)s] - %(name)s\t%(message)s",
    )
    unittest.main(verbosity=2)
