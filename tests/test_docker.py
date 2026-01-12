#!/usr/bin/env python3
"""
Unit tests for Docker setup verification using unittest
Tests Docker container build, run, and file tree structure
"""

import unittest
import requests
import os
import sys
import subprocess

# Import the server manager
from server_manager import TestServerManager, check_prerequisites


class TestDockerSetup(unittest.TestCase):
    """Test cases for Docker container setup and file tree"""

    @classmethod
    def setUpClass(cls):
        """Setup Docker environment before running tests"""
        print("🐳 Starting Docker setup tests...")

        # Check prerequisites
        if not check_prerequisites("docker"):
            sys.exit(1)

        # Setup server manager
        cls.server_manager = TestServerManager.for_docker_tests()

        # Start Docker container if not already running
        if not cls.server_manager.check_server_running():
            print("🐳 Starting Docker container...")
            success = cls.server_manager.start_docker_server(timeout=120)
            if not success:
                raise RuntimeError("Failed to start Docker container")

            # Wait for server to be fully ready
            if not cls.server_manager.wait_for_server_boot(timeout=60):
                raise RuntimeError("Docker container not ready after boot")

        print("✅ Docker container is running and ready for tests")

    @classmethod
    def tearDownClass(cls):
        """Clean up Docker resources after all tests"""
        print("🧹 Cleaning up Docker resources...")
        if hasattr(cls, "server_manager"):
            cls.server_manager.stop_server()

    def test_api_health_check(self):
        """Test that the API is responding correctly from the container"""
        print("🏥 Testing API health check...")

        # Test root endpoint
        response = requests.get("http://localhost:8000/api", timeout=10)
        self.assertEqual(response.status_code, 200, "Root endpoint failed")

        data = response.json()
        self.assertEqual(
            data["message"], "Shared Shopping List API", "Unexpected root response"
        )
        print("✅ Root endpoint working")

        # Test items endpoint
        response = requests.get("http://localhost:8000/items", timeout=10)
        self.assertEqual(response.status_code, 200, "Items endpoint failed")

        items = response.json()
        self.assertIsInstance(items, list, "Items endpoint returned non-list")
        print(f"✅ Items endpoint working, found {len(items)} items")


def run_tests():
    """Run the Docker test suite"""
    print("🧪 Starting Docker Setup Tests")
    print("=" * 50)
    print("Using unittest framework to test Docker container setup and file tree")
    print()

    # Run the tests
    unittest.main(verbosity=2)

    print("=" * 50)
    print("🎉 Docker test suite completed!")


if __name__ == "__main__":
    run_tests()
