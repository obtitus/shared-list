#!/usr/bin/env python3
"""
Server Manager for Test Suite
Provides uniform server management across all test types:
- API tests: uv run app/main.py
- Docker tests: docker compose up -d
- PWA tests: uv run app/main.py (if needed)
"""

import subprocess
import time
import requests
import os
import sys
import signal
from typing import Optional
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class ServerManager:
    """Manages server lifecycle for different test types"""

    def __init__(self, base_url: str = "http://localhost:8000", port: int = 8000):
        self.base_url = base_url
        self.port = port
        self.server_process: Optional[subprocess.Popen] = None
        self.server_docker_started = False

    def check_server_running(self, timeout: int = 5) -> bool:
        """Check if server is already running on the specified port"""
        try:
            response = requests.get(f"{self.base_url}/api", timeout=timeout)
            if response.status_code == 200:
                data = response.json()
                if data.get("message") == "Shared Shopping List API":
                    return True
        except requests.exceptions.RequestException:
            pass

        logging.info("⚠️  Server not detected on port")
        return False

    def start_api_server(self, timeout: int = 30) -> bool:
        """Start the API server using uv run app/main.py"""
        if self.check_server_running():
            logging.info("✅ API server already running")
            return True

        logging.info("🚀 Starting API server with uv run...")
        try:
            # Start server in background
            self.server_process = subprocess.Popen(
                ["uv", "run", "python", "app/main.py"]
            )

            # Wait for server to start
            start_time = time.time()
            while time.time() - start_time < timeout:
                if self.check_server_running(timeout=2):
                    logging.info("✅ API server started successfully")
                    return True
                time.sleep(0.25)

            self.stop_server()
            return False

        except Exception as e:
            logging.error(f"❌ Failed to start API server: {e}")
            self.stop_server()
            return False

    def start_docker_server(self, timeout: int = 120) -> bool:
        """Start the Docker server using docker compose up -d"""
        if self.check_server_running():
            logging.info("✅ Server already running")
            return True

        logging.info("🐳 Starting Docker server...")
        try:
            # Clean up any existing containers first
            self._cleanup_docker_containers()

            # Start Docker container
            result = subprocess.run(
                ["docker", "compose", "up", "-d"],
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if result.returncode != 0:
                logging.error(f"❌ Docker compose up failed: {result.stderr}")
                return False

            self.server_docker_started = True

            # Wait for container and API to be ready
            start_time = time.time()
            while time.time() - start_time < timeout:
                if self.check_server_running(timeout=2):
                    logging.info("✅ Docker server started successfully")
                    return True
                time.sleep(0.25)

            logging.error("❌ Docker server not ready after timeout")
            self.stop_server()
            return False

        except subprocess.TimeoutExpired:
            logging.error("❌ Docker compose up timed out")
            self.stop_server()
            return False
        except Exception as e:
            logging.error(f"❌ Failed to start Docker server: {e}")
            self.stop_server()
            return False

    def wait_for_server_boot(self, timeout: int = 30) -> bool:
        """Wait for server to fully boot and be ready to handle requests"""
        if not self.check_server_running():
            logging.warning("⚠️  Server is not running")
            return False

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Test that the API endpoints are working
                response = requests.get(f"{self.base_url}/items", timeout=5)
                if response.status_code == 200:
                    items = response.json()
                    if isinstance(items, list):
                        logging.info("✅ Server fully booted and ready")
                        return True
            except requests.exceptions.RequestException:
                pass

            time.sleep(1)

        logging.error("❌ Server not fully ready after timeout")
        return False

    def stop_server(self):
        """Stop the running server"""

        logging.info("🛑 Stopping server...")
        try:
            if self.server_process is not None:
                # First try graceful shutdown
                self.server_process.terminate()

                try:
                    self.server_process.wait(timeout=10)  # Increased timeout
                    logging.info("✅ API server stopped gracefully")
                except subprocess.TimeoutExpired:
                    logging.warning(
                        "⚠️  Server didn't stop gracefully, force killing..."
                    )
                    if self.server_process and self.server_process.pid:
                        try:
                            os.killpg(
                                os.getpgid(self.server_process.pid), signal.SIGKILL
                            )
                            self.server_process.wait(timeout=5)
                            logging.info("✅ API server force killed")
                        except (OSError, subprocess.TimeoutExpired) as e:
                            logging.error(f"❌ Failed to kill server process: {e}")

            if self.server_docker_started:
                # For Docker, use docker compose down
                subprocess.run(
                    ["docker", "compose", "down"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                logging.info("✅ Docker server stopped")
                self.server_docker_started = False

            # Verify server is actually down by checking if port is free
            start_time = time.time()
            while time.time() - start_time < 30:
                if not self.check_server_running(timeout=1):
                    logging.info("✅ Server confirmed down")
                    break
                time.sleep(1)
            else:
                logging.warning(
                    "⚠️ Server still appears to be running after stop attempt"
                )

        except Exception as e:
            logging.error(f"❌ Error stopping server: {e}")
        finally:
            self.server_process = None

    def _cleanup_docker_containers(self):
        """Clean up any existing Docker containers"""
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

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        print("__exit__")
        self.stop_server()


class TestServerManager:
    """Factory class for creating appropriate server managers for different test types"""

    @staticmethod
    def for_api_tests() -> ServerManager:
        """Create server manager for API tests"""
        return ServerManager()

    @staticmethod
    def for_docker_tests() -> ServerManager:
        """Create server manager for Docker tests"""
        return ServerManager()

    @staticmethod
    def for_pwa_tests() -> ServerManager:
        """Create server manager for PWA tests"""
        return ServerManager()


def ensure_server_available(
    server_type: str = "api", timeout: int = 30
) -> ServerManager:
    """
    Ensure server is available for tests

    Args:
        server_type: Type of server ("api" or "docker")
        timeout: Maximum time to wait for server to start

    Returns:
        ServerManager instance
    """
    manager = (
        TestServerManager.for_api_tests()
        if server_type == "api"
        else TestServerManager.for_docker_tests()
    )

    if server_type == "api":
        success = manager.start_api_server(timeout)
    elif server_type == "docker":
        success = manager.start_docker_server(timeout)
    else:
        raise ValueError(f"Unknown server type: {server_type}")

    if not success:
        raise RuntimeError(f"Failed to start {server_type} server")

    if not manager.wait_for_server_boot(timeout):
        raise RuntimeError("Server not ready after boot timeout")

    return manager


def check_prerequisites(test_type: str) -> bool:
    """Check if prerequisites are met for the test type"""
    if test_type == "docker":
        # Check Docker availability
        try:
            result = subprocess.run(
                ["docker", "--version"], capture_output=True, text=True
            )
            if result.returncode != 0:
                logging.error("❌ Docker is not available or not running")
                return False
            logging.info(f"✅ Docker version: {result.stdout.strip()}")
        except FileNotFoundError:
            logging.error("❌ Docker command not found")
            return False

    # Check required files
    required_files = []
    if test_type in ["api", "pwa"]:
        required_files.extend(["app/main.py", "app/database.py"])
    if test_type == "docker":
        required_files.extend(["docker-compose.yml", "Dockerfile"])

    for file_path in required_files:
        if not os.path.exists(file_path):
            logging.error(f"❌ Required file missing: {file_path}")
            return False

    return True


if __name__ == "__main__":
    # Example usage

    if len(sys.argv) > 1:
        server_type = sys.argv[1]
        if server_type not in ["api", "docker"]:
            print("Usage: python server_manager.py [api|docker]")
            sys.exit(1)

        if not check_prerequisites(server_type):
            sys.exit(1)

        try:
            with ensure_server_available(server_type) as manager:
                print(f"✅ {server_type.upper()} server is running and ready!")

                time.sleep(10)
                print("\n🛑 Stopping server...")
        except RuntimeError as e:
            print(f"❌ {e}")
            sys.exit(1)
    else:
        print("Usage: python server_manager.py [api|docker]")
        sys.exit(1)
