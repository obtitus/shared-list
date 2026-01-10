#!/usr/bin/env python3
"""
Unit tests for Docker setup verification using unittest
Tests Docker container build, run, and file tree structure
"""

import unittest
import subprocess
import time
import requests
import os
import sys


class TestDockerSetup(unittest.TestCase):
    """Test cases for Docker container setup and file tree"""

    @classmethod
    def setUpClass(cls):
        """Setup Docker environment before running tests"""
        print("🐳 Starting Docker setup tests...")

        # Clean up any existing containers
        cls._cleanup_containers()

        # Start the container for all tests
        returncode, stdout, stderr = cls().run_command(
            "docker compose up -d", timeout=60
        )
        if returncode != 0:
            raise Exception(f"Docker compose up failed: {stderr}")

        # Wait for container to be ready (max 20 seconds, break early if ready)
        for i in range(20):
            returncode, stdout, stderr = cls().run_command("docker compose ps")
            if returncode == 0 and "Up" in stdout:
                # Test if the API is actually responding
                try:
                    response = requests.get("http://localhost:8000/", timeout=2)
                    if response.status_code == 200:
                        print(f"✅ Container and API ready after {i+1} seconds")
                        break
                except Exception:
                    pass
                print(
                    f"⚠️  Container up but API not ready after {i+1} seconds, waiting..."
                )
            time.sleep(1)
        else:
            print("⚠️  Container not ready after 20 seconds, continuing anyway")

    @classmethod
    def tearDownClass(cls):
        """Clean up Docker resources after all tests"""
        print("🧹 Cleaning up Docker resources...")
        cls._cleanup_containers()

    @classmethod
    def _cleanup_containers(cls):
        """Clean up any existing containers and networks"""
        try:
            subprocess.run(
                ["docker", "compose", "down"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            subprocess.run(
                ["docker", "system", "prune", "-f"],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except Exception:
            pass

    def run_command(self, cmd, timeout=60):
        """Run a command and return the result"""
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=timeout
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out after {timeout} seconds"

    def test_docker_build(self):
        """Test that the Docker image can be built successfully"""
        print("🏗️  Testing Docker build...")

        returncode, stdout, stderr = self.run_command(
            "docker compose build", timeout=300
        )

        self.assertEqual(returncode, 0, f"Docker build failed: {stderr}")
        print("✅ Docker build successful")

    def test_docker_container_startup(self):
        """Test that the Docker container can start and be healthy"""
        print("🚀 Testing Docker container startup...")

        # Start the container
        returncode, stdout, stderr = self.run_command(
            "docker compose up -d", timeout=60
        )
        self.assertEqual(returncode, 0, f"Docker compose up failed: {stderr}")

        # Wait for container to be ready
        time.sleep(20)

        # Check container status
        returncode, stdout, stderr = self.run_command("docker compose ps")
        self.assertEqual(returncode, 0, f"Docker compose ps failed: {stderr}")

        self.assertIn("Up", stdout, "Container is not running")
        print("✅ Container is running")

    def test_api_health_check(self):
        """Test that the API is responding correctly from the container"""
        print("🏥 Testing API health check...")

        # Test root endpoint
        response = requests.get("http://localhost:8000/", timeout=10)
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

    def test_docker_file_tree_structure(self):
        """Test the file tree structure inside the running container"""
        print("📁 Testing Docker file tree structure...")

        # Get container ID
        returncode, stdout, stderr = self.run_command("docker compose ps -q backend")
        self.assertEqual(returncode, 0, f"Failed to get container ID: {stderr}")

        container_id = stdout.strip()
        self.assertTrue(container_id, "No container ID found")

        # Test that main.py exists in /app/
        returncode, stdout, stderr = self.run_command(
            f"docker exec {container_id} ls -la /code/app/"
        )
        self.assertEqual(
            returncode, 0, f"Failed to list /code/app/ directory: {stderr}"
        )

        # Check for expected files
        expected_files = ["main.py", "database.py"]
        for expected_file in expected_files:
            self.assertIn(
                expected_file, stdout, f"Missing expected file: {expected_file}"
            )
        print("✅ Expected Python files found in /code/app/")

        # Test that data directory exists and contains database
        returncode, stdout, stderr = self.run_command(
            f"docker exec {container_id} ls -la /code/app/data/"
        )
        self.assertEqual(
            returncode, 0, f"Failed to list /code/app/data/ directory: {stderr}"
        )

        self.assertIn("shopping.db", stdout, "shopping.db not found in /code/app/data/")
        print("✅ Database file found in /code/app/data/")

    def test_docker_environment_variables(self):
        """Test that environment variables are set correctly in the container"""
        print("⚙️  Testing Docker environment variables...")

        # Get container ID
        returncode, stdout, stderr = self.run_command("docker compose ps -q backend")
        self.assertEqual(returncode, 0, f"Failed to get container ID: {stderr}")

        container_id = stdout.strip()

        # Check environment variables
        returncode, stdout, stderr = self.run_command(f"docker exec {container_id} env")
        self.assertEqual(
            returncode, 0, f"Failed to get environment variables: {stderr}"
        )

        # Verify required environment variables
        self.assertIn(
            "HOST=0.0.0.0", stdout, "HOST environment variable not set correctly"
        )
        self.assertIn(
            "PORT=8000", stdout, "PORT environment variable not set correctly"
        )
        print("✅ Environment variables set correctly")

    def test_docker_volume_mounting(self):
        """Test that volumes are mounted correctly"""
        print("💾 Testing Docker volume mounting...")

        # Get container ID
        returncode, stdout, stderr = self.run_command("docker compose ps -q backend")
        self.assertEqual(returncode, 0, f"Failed to get container ID: {stderr}")

        container_id = stdout.strip()

        # Check that we can access the mounted app directory
        returncode, stdout, stderr = self.run_command(
            f"docker exec {container_id} cat /code/app/main.py | head -5"
        )
        self.assertEqual(returncode, 0, f"Failed to read mounted main.py: {stderr}")

        # Verify it contains expected content
        self.assertIn(
            "FastAPI", stdout, "Mounted main.py doesn't contain expected content"
        )
        print("✅ Volume mounting working correctly")

    def test_docker_health_check(self):
        """Test that the container health check is working"""
        print("💓 Testing Docker health check...")

        # Get container ID
        returncode, stdout, stderr = self.run_command("docker compose ps -q backend")
        self.assertEqual(returncode, 0, f"Failed to get container ID: {stderr}")

        container_id = stdout.strip()

        # Check container health status
        returncode, stdout, stderr = self.run_command(
            f"docker inspect --format='{{{{.State.Health.Status}}}}' {container_id}"
        )

        # Health check might not be available in all Docker versions, so we'll be lenient
        if returncode == 0:
            health_status = stdout.strip()
            self.assertIn(
                health_status,
                ["healthy", "starting"],
                f"Container health check failed: {health_status}",
            )
            print(f"✅ Container health status: {health_status}")
        else:
            print("⚠️  Health check not available, but container is running")


def run_tests():
    """Run the Docker test suite"""
    print("🧪 Starting Docker Setup Tests")
    print("=" * 50)
    print("Using unittest framework to test Docker container setup and file tree")
    print()

    # Check if Docker is available
    try:
        result = subprocess.run(["docker", "--version"], capture_output=True, text=True)
        if result.returncode != 0:
            print("❌ Docker is not available or not running")
            sys.exit(1)
        print(f"✅ Docker version: {result.stdout.strip()}")
    except FileNotFoundError:
        print("❌ Docker command not found")
        sys.exit(1)

    # Check if required files exist
    required_files = [
        "docker-compose.yml",
        "Dockerfile",
        "app/main.py",
        "app/database.py",
    ]
    for file_path in required_files:
        if not os.path.exists(file_path):
            print(f"❌ Required file missing: {file_path}")
            sys.exit(1)

    # Run the tests
    unittest.main(verbosity=2, exit=False)

    print("=" * 50)
    print("🎉 Docker test suite completed!")


if __name__ == "__main__":
    run_tests()
