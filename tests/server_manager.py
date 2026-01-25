#!/usr/bin/env python3
"""
Server Manager for Test Suite
Provides uniform server management across all test types:
- API tests: uv run app/main.py
- Docker tests: docker compose up -d
- PWA tests: uv run app/main.py (if needed)
"""

import os
import subprocess
import time
import requests
import signal
from typing import Optional
import logging

# Create logger
logger = logging.getLogger("test." + __name__)


class ServerManager:
    """Manages server lifecycle for different test types"""

    def __init__(
        self,
        base_url: str = "http://localhost:",
        port: int = 8000,
        server_type: str = "api",
    ):
        self.base_url = base_url + str(port)
        self.port = port
        self.server_process: Optional[subprocess.Popen] = None
        self.server_docker_started = False
        self.docker_env = None  # Store Docker environment variables
        self.server_type = server_type

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

        return False

    def start_api_server(self, timeout: int = 30) -> bool:
        """Start the API server using uv run app/main.py"""
        if self.check_server_running():
            logger.info("✅ API server already running")
            return True

        logger.info("🚀 Starting API server with uv run...")
        try:
            # Start server in background with custom port
            env = os.environ.copy()
            env["PORT"] = str(self.port)
            self.server_process = subprocess.Popen(
                ["uv", "run", "python", "app/main.py"], env=env
            )

        except Exception as e:
            logger.error(f"❌ Failed to start API server: {e}")
            self.stop_server()
            return False

        return True

    def start_docker_server(self, timeout: int = 120) -> bool:
        """Start the Docker server using docker compose up -d"""
        if self.check_server_running():
            logger.info("✅ Server already running")
            return True

        logger.info("🐳 Starting Docker server...")
        try:
            # Clean up any existing containers first
            self._cleanup_docker_containers()

            # Start Docker container with custom port and unique name
            env = os.environ.copy()
            env["PORT"] = str(self.port)
            env["HOST_PORT"] = str(self.port)  # For docker-compose port mapping
            env["COMPOSE_PROJECT_NAME"] = f"test-{self.port}"  # Unique project name

            # Store the Docker environment for cleanup
            self.docker_env = env

            result = subprocess.run(
                ["docker", "compose", "up", "-d"],
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )

            if result.returncode != 0:
                logger.error(f"❌ Docker compose up failed: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("❌ Docker compose up timed out")
            self.stop_server()
            return False
        except Exception as e:
            logger.error(f"❌ Failed to start Docker server: {e}")
            self.stop_server()
            return False

        return True

    def wait_for_server_boot(self, timeout: int = 30) -> bool:
        """Wait for server to fully boot and be ready to handle requests"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Test that the API endpoints are working
                response = requests.get(f"{self.base_url}/items", timeout=5)
                if response.status_code == 200:
                    items = response.json()
                    if isinstance(items, list):
                        logger.info("✅ Server fully booted and ready")
                        return True
            except requests.exceptions.RequestException:
                pass

            time.sleep(1)

        logger.error("❌ Server not fully ready after timeout")
        return False

    def stop_server(self):
        """Stop the running server"""

        logger.info("🛑 Stopping server...")
        try:
            if self.server_process is not None:
                # First try graceful shutdown
                self.server_process.terminate()

                try:
                    self.server_process.wait(timeout=10)  # Increased timeout
                    logger.info("✅ API server stopped gracefully")
                except subprocess.TimeoutExpired:
                    logger.warning("⚠️  Server didn't stop gracefully, force killing...")
                    if self.server_process and self.server_process.pid:
                        try:
                            os.killpg(
                                os.getpgid(self.server_process.pid), signal.SIGKILL
                            )
                            self.server_process.wait(timeout=5)
                            logger.info("✅ API server force killed")
                        except (OSError, subprocess.TimeoutExpired) as e:
                            logger.error(f"❌ Failed to kill server process: {e}")

            if self.docker_env is not None:
                # For Docker, use enhanced cleanup with proper environment
                self._cleanup_docker_containers(self.docker_env)
                logger.info("✅ Docker server stopped")
                self.docker_env = None

            # Verify server is actually down by checking if port is free
            start_time = time.time()
            while time.time() - start_time < 30:
                if not self.check_server_running(timeout=1):
                    logger.info("✅ Server confirmed down")
                    break
                time.sleep(1)
            else:
                logger.warning(
                    "⚠️ Server still appears to be running after stop attempt"
                )

        except Exception as e:
            logger.error(f"❌ Error stopping server: {e}")
        finally:
            self.server_process = None

    def _cleanup_docker_containers(self, env=None):
        """Clean up any existing Docker containers"""
        try:
            # Use provided environment or stored Docker environment
            cleanup_env = env or self.docker_env or os.environ.copy()

            # Stop and remove containers with our project name (force removal)
            subprocess.run(
                [
                    "docker",
                    "compose",
                    "down",
                    "--volumes",
                    "--remove-orphans",
                    "--timeout",
                    "10",
                ],
                capture_output=True,
                text=True,
                timeout=60,
                env=cleanup_env,
            )
        except Exception as e:
            logger.warning(f"⚠️ Docker cleanup encountered an issue: {e}")

    def __enter__(self):
        """Context manager entry"""
        if self.check_server_running():
            logger.info("✅ Server already running on enter")
        else:
            logger.info("🚀 Starting server on enter...")
            if self.server_type == "docker":
                self.start_docker_server()
            else:
                self.start_api_server()

        self.wait_for_server_boot()

    def __exit__(self, exc_type=None, exc_val=None, exc_tb=None):
        """Context manager exit"""
        self.stop_server()


def check_prerequisites(test_type: str) -> bool:
    """Check if prerequisites are met for the test type"""
    if test_type == "docker":
        # Check Docker availability
        try:
            result = subprocess.run(
                ["docker", "--version"], capture_output=True, text=True
            )
            if result.returncode != 0:
                logger.error("❌ Docker is not available or not running")
                return False
            logger.info(f"✅ Docker version: {result.stdout.strip()}")
        except FileNotFoundError:
            logger.error("❌ Docker command not found")
            return False

    # Check required files
    required_files = []
    if test_type in ["api", "pwa"]:
        required_files.extend(["app/main.py", "app/database.py"])
    if test_type == "docker":
        required_files.extend(["docker-compose.yml", "Dockerfile"])

    for file_path in required_files:
        if not os.path.exists(file_path):
            logger.error(f"❌ Required file missing: {file_path}")
            return False

    return True


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    # Example usage
    if not (check_prerequisites("docker")):
        raise OSError("docker not available")

    if not (check_prerequisites("api")):
        raise OSError("api not available")

    now = time.time()
    with ServerManager(port=8000, server_type="docker") as server:
        logger.info("✅ Server is running for testing")

    logger.info(
        "Docker starting/stopping took {:.3g} seconds".format(time.time() - now)
    )

    now = time.time()
    with ServerManager(port=8000, server_type="api") as server:
        logger.info("✅ Server is running for testing")
    logger.info("API starting/stopping took {:.3g} seconds".format(time.time() - now))
